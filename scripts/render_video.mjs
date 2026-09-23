#!/usr/bin/env node
/**
 * render_video.mjs —— html-explainer 的确定性 HTML→MP4 渲染器。
 *
 * 【血统】
 *  - 画面契约（HTML + GSAP 单文件场景、1920×1080、系统字体）来自 html-video
 *    的帧形态；但它用「实时录制 + 裁引导期」，天然带一整类坑（__hvUnfreeze
 *    起播、Google Fonts 6s 超时、字体 swap 中途换脸、leadInMs 不稳）。
 *  - 本渲染器改用 anything2explainer / Remotion 同款的**确定性逐帧渲染**：
 *    暂停时间轴 → seek 到 t → 截图。没有任何实时录制环节，上述坑整类消除。
 *
 * 【每帧渲染管线】
 *   1. tl.pause(t, false)    GSAP 时间轴同步渲染到 t（inline style 立即生效；false = 放行回调）
 *   2. getAnimations() seek   CSS @keyframes 动画也确定性对齐（currentTime = t*1000）
 *   3. __mgSubUpdate(t)       渲染器注入的字幕层按本场景块表硬切
 *   4. __mgProgressUpdate()   渲染器注入的全局进度条按 (globalT/total) 填充
 *   5. 双 rAF + screenshot    保证合成器已把本帧样式画出来再截图
 *
 * 【时长口径（继承并修正两级时钟）】
 *   - 场景时长 = 该段 MP3 的**容器时长**（tts_build.py 已裁首尾静音并回填），
 *     段间 gap 由 timeline_build.py 显式插入 —— 音画天然对齐。
 *   - 总帧数 = round(total × fps)，按场景累计舍入，不逐场景独立舍入。
 *
 * 用法（项目目录 = 含 project.json 的目录）：
 *   node render_video.mjs <projectDir> [--out out/<slug>.mp4]
 *        [--preview 30] [--fps 30] [--concurrency 3] [--jpeg]
 *        [--scale 1] [--keep-frames] [--mux-only] [--only <场景id,场景id>]
 *
 *   --mux-only：跳过截图，用 render/frames 里已有的帧直接重新合成
 *               （改合参 / 换音轨后不用重渲 20 分钟）
 *
 *   --only coda：改完某一场的文案/动效后，只重渲这一场的帧，其余帧保持不动。
 *               仅当被改场景是**最后一场**时安全；若它在中间且时长变了，
 *               其后场景的帧号会整体前移，必须整片重渲。
 *               变短后记得删掉尾部的过期帧，否则成片会拖长（脚本会提示实际帧数）。
 *
 * 环境解析顺序：
 *   浏览器  env BROWSER_PATH → Chrome → Edge → playwright 自带 chromium
 *   ffmpeg  env FFMPEG_PATH → PATH 上的 ffmpeg → python -c imageio_ffmpeg（venv）
 *   python  env PY → PATH python（用来问 imageio-ffmpeg 要静态 ffmpeg）
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, '..');
const require = createRequire(path.join(SKILL_ROOT, 'node', 'package.json'));

// ---------- 工具 ----------
const log = (msg) => process.stderr.write(`[render] ${msg}\n`);
const die = (msg) => { process.stderr.write(`[render] ✗ ${msg}\n`); process.exit(1); };

function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--out') a.out = argv[++i];
    else if (t === '--preview') a.preview = parseFloat(argv[++i]);
    else if (t === '--fps') a.fps = parseFloat(argv[++i]);
    else if (t === '--concurrency') a.concurrency = parseInt(argv[++i], 10);
    else if (t === '--jpeg') a.jpeg = true;
    else if (t === '--jpeg-quality') a.jpegQuality = parseInt(argv[++i], 10);
    else if (t === '--png-fast') a.pngFast = true;
    else if (t === '--crf') a.crf = parseInt(argv[++i], 10);
    else if (t === '--preset') a.preset = argv[++i];
    else if (t === '--scale') a.scale = parseFloat(argv[++i]);
    else if (t === '--keep-frames') a.keepFrames = true;
    else if (t === '--mux-only') a.muxOnly = true;
    else if (t === '--only') a.only = String(argv[++i] || '').split(',').map((s) => s.trim()).filter(Boolean);
    else if (t === '--browser') a.browser = argv[++i];
    else if (!t.startsWith('--')) a._.push(t);
  }
  return a;
}

// ---------- ffmpeg 解析（PATH → imageio-ffmpeg 静态二进制） ----------
function resolveFfmpeg() {
  if (process.env.FFMPEG_PATH && fs.existsSync(process.env.FFMPEG_PATH)) return process.env.FFMPEG_PATH;
  const isWin = process.platform === 'win32';
  const name = isWin ? 'ffmpeg.exe' : 'ffmpeg';
  for (const d of (process.env.PATH || '').split(path.delimiter)) {
    if (!d) continue;
    const p = path.join(d, name);
    try { if (fs.existsSync(p)) return p; } catch { /* ignore */ }
  }
  // 回退：问 python 的 imageio_ffmpeg 要（WorkBuddy 托管 venv 里有静态 ffmpeg）
  const pyCandidates = [process.env.PY, 'python3', 'python'].filter(Boolean);
  for (const py of pyCandidates) {
    try {
      const out = execFileSync(py, ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
        { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
      if (out && fs.existsSync(out)) return out;
    } catch { /* next */ }
  }
  return null;
}

// ---------- 浏览器解析（Chrome → Edge → playwright chromium） ----------
function resolveBrowserExec() {
  if (process.env.BROWSER_PATH && fs.existsSync(process.env.BROWSER_PATH)) return process.env.BROWSER_PATH;
  const candidates = [];
  if (process.platform === 'win32') {
    for (const p of [
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
      path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe'),
      'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    ]) if (p) candidates.push(p);
  } else if (process.platform === 'darwin') {
    candidates.push('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      '/Applications/Chromium.app/Contents/MacOS/Chromium');
  } else {
    candidates.push('/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
      '/usr/bin/microsoft-edge');
  }
  for (const p of candidates) { try { if (fs.existsSync(p)) return p; } catch { /* ignore */ } }
  return null; // 走 playwright 自带 chromium（需 npx playwright install chromium）
}

// ---------- 注入页面的字幕层 / 进度条（渲染器全权管理，帧作者零负担） ----------
const OVERLAY_CSS = `
  #mg-subs { position: fixed; inset: 0; pointer-events: none; z-index: 900; }
  #mg-subs .mg-sub {
    position: absolute; left: 50%; bottom: 96px; transform: translateX(-50%);
    white-space: nowrap; text-align: center;
    font-family: 'Microsoft YaHei', 'PingFang SC', 'Noto Sans CJK SC', 'Source Han Sans SC', sans-serif;
    font-weight: 700; font-size: 44px; line-height: 1.2; color: #FFFFFF;
    text-shadow:
      4px 0 0 #000, -4px 0 0 #000, 0 4px 0 #000, 0 -4px 0 #000,
      2.4px 2.4px 0 #000, -2.4px 2.4px 0 #000, 2.4px -2.4px 0 #000, -2.4px -2.4px 0 #000,
      1.2px 1.2px 0 #000, -1.2px 1.2px 0 #000, 1.2px -1.2px 0 #000, -1.2px -1.2px 0 #000,
      3.2px 1.06px 0 #000, -3.2px 1.06px 0 #000, 3.2px -1.06px 0 #000, -3.2px -1.06px 0 #000,
      1.06px 3.2px 0 #000, -1.06px 3.2px 0 #000, 1.06px -3.2px 0 #000, -1.06px -3.2px 0 #000,
      2.83px 2.83px 0 #000, -2.83px 2.83px 0 #000, 2.83px -2.83px 0 #000, -2.83px -2.83px 0 #000;
  }
  #mg-progress { position: fixed; left: 0; right: 0; bottom: 0; height: 12px;
    z-index: 901; pointer-events: none; background: rgba(255,255,255,.10); }
  #mg-progress .mg-bar { height: 100%; width: 0%;
    background: var(--accent, #E4AE29); box-shadow: 0 0 12px var(--accent-glow, rgba(228,174,41,.55)); }
  #mg-progress .mg-tick { position: absolute; top: 0; width: 2px; height: 100%;
    background: rgba(255,255,255,.38); }
`;

function overlaySetupJs(blocks, fps, withProgress, chapterTicks) {
  const blocksJs = JSON.stringify(blocks || []);
  const ticksJs = JSON.stringify(chapterTicks || []);
  return `(function () {
  var css = document.createElement('style'); css.textContent = ${JSON.stringify(OVERLAY_CSS)};
  document.head.appendChild(css);

  var subEl = document.createElement('div'); subEl.id = 'mg-subs';
  var subNode = document.createElement('div'); subNode.className = 'mg-sub';
  subNode.style.display = 'none'; subEl.appendChild(subNode);
  document.body.appendChild(subEl);

  var proEl = null, bar = null;
  ${withProgress ? `
  proEl = document.createElement('div'); proEl.id = 'mg-progress';
  bar = document.createElement('div'); bar.className = 'mg-bar'; proEl.appendChild(bar);
  ${ticksJs}.forEach(function (p) {
    var t = document.createElement('div'); t.className = 'mg-tick'; t.style.left = (p * 100) + '%';
    proEl.appendChild(t);
  });
  document.body.appendChild(proEl);` : ''}

  var BLOCKS = ${blocksJs}, FPS = ${fps}, cur = -1;
  window.__mgSubUpdate = function (t) {
    var f = t * FPS, idx = -1;
    for (var i = 0; i < BLOCKS.length; i++) {
      if (f >= BLOCKS[i].from - 1 && f <= BLOCKS[i].to) { idx = i; break; }
    }
    if (idx !== cur) {
      if (cur >= 0) subNode.style.display = 'none';
      if (idx >= 0) {
        subNode.textContent = BLOCKS[idx].text;
        subNode.style.fontSize = (BLOCKS[idx].size || 44) + 'px';
        subNode.style.display = 'block';
      }
      cur = idx;
    }
  };
  window.__mgProgressUpdate = function (p) {
    if (bar) bar.style.width = (Math.max(0, Math.min(1, p)) * 100).toFixed(3) + '%';
  };
})();`;
}

// 每帧 seek：GSAP + CSS @keyframes + 字幕 + 进度条 + 双 rAF。
// ★ 必须是**真正的函数**，不能写成字符串形式的箭头函数定义 ——
//   playwright 对字符串只做表达式求值：`async (o) => {...}` 会被当成函数字面量
//   **返回而不执行**（返回不可序列化 → undefined），导致每帧都是静止首帧。
//   这个坑极隐蔽：不报错、截图仍在写盘，成片却是"只有背景色 + CSS 动画"。
const frameSeek = async (o) => {
  const { t, globalT, total } = o;
  let tl = window.__tl || null;
  if (!tl && window.__timelines) {
    for (const k in window.__timelines) { if (window.__timelines[k]) { tl = window.__timelines[k]; break; } }
  }
  if (!tl) throw new Error('no GSAP timeline found (window.__tl)');
  // ★ pause(atTime, suppressEvents)：第二参 GSAP 默认 true，会**掐掉本次 seek 触发的回调**
  //   （onUpdate / onStart / onComplete）。此时用 onUpdate 写 textContent 做的数字滚动
  //   在渲染器下永远停在初值——不报错、截图照写、成片数字不动。必须显式传 false。
  //   实测见 lessons.md #27。
  tl.pause(t, false);                // GSAP：seek 即同步渲染 + 放行回调
  if (document.getAnimations) {      // CSS @keyframes：也确定性对齐
    document.getAnimations().forEach((a) => {
      try { a.pause(); a.currentTime = Math.round(t * 1000); } catch (e) { /* ignore */ }
    });
  }
  if (window.__mgSubUpdate) window.__mgSubUpdate(t);
  if (window.__mgProgressUpdate) window.__mgProgressUpdate(total ? (globalT / total) : 0);
  await new Promise((r) => { requestAnimationFrame(() => { requestAnimationFrame(r); }); });
  return tl.time();
};

// ---------- 截图：三种模式（这一层是本渲染器最容易踩的性能坑） ----------
// PNG（playwright 默认）对**照片满幅帧**极慢：实测 1920×1080 照片帧 582ms/张，
// 而纯色帧只要 45ms —— 差 13 倍。因为 PNG 是无损 deflate，高熵照片内容既压不小
// 也压不快，且这段编码在**浏览器进程内串行**：并发 1/3/6 路实测总吞吐
// 1.80 / 1.86 / 1.87 帧/秒 —— 挂并发等于白挂，`--concurrency` 对帧数毫无帮助。
//   ★ --png-fast：走 CDP 的 optimizeForSpeed（zlib 最快档、不做自适应滤波），
//     实测 132ms/张，仍是**逐像素无损**（对 playwright PNG：PSNR 99dB、最大差 0），
//     代价是体积 +22%。照片多的片子选它。
//   ★ --jpeg：q82 41ms/张（13×）；q95 52ms/张，PSNR 41.7dB（已低于 x264 crf18
//     自身的失真水平，成片看不出），体积仅 1/5。要极致速度就它。
async function captureFrame({ page, cdp, outPath, args, W, H }) {
  if (cdp) {
    const opts = { format: 'png', optimizeForSpeed: true, captureBeyondViewport: false };
    const sc = args.scale || 1;
    if (sc !== 1) opts.clip = { x: 0, y: 0, width: W, height: H, scale: sc };
    const r = await cdp.send('Page.captureScreenshot', opts);
    fs.writeFileSync(outPath, Buffer.from(r.data, 'base64'));
    return;
  }
  await page.screenshot({
    path: outPath,
    type: args.jpeg ? 'jpeg' : 'png',
    quality: args.jpeg ? (args.jpegQuality || 82) : undefined,
  });
}

// ---------- 主流程 ----------
async function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectDir = path.resolve(args._[0] || '.');
  const pjPath = path.join(projectDir, 'project.json');
  if (!fs.existsSync(pjPath)) die(`没有 project.json：${pjPath}`);
  const pj = JSON.parse(fs.readFileSync(pjPath, 'utf8'));

  const fps = args.fps || pj.fps || 30;
  const W = pj.width || 1920, H = pj.height || 1080;
  const order = pj.order || [];
  if (!order.length) die('project.json 里没有 order（场景顺序）');

  const layoutPath = path.join(projectDir, 'layout.json');
  if (!fs.existsSync(layoutPath)) die(`没有 layout.json（先跑 timeline_build.py）：${layoutPath}`);
  const layout = JSON.parse(fs.readFileSync(layoutPath, 'utf8'));

  let subs = { fps, segments: [] };
  const subsPath = path.join(projectDir, 'subs.json');
  if (fs.existsSync(subsPath)) subs = JSON.parse(fs.readFileSync(subsPath, 'utf8'));

  // 缺帧 HTML 的场景直接报错（别静默跳过）
  for (const id of order) {
    if (!fs.existsSync(path.join(projectDir, 'frames', `${id}.html`)))
      die(`缺场景帧：frames/${id}.html`);
  }

  // 渲染范围：正常全片；--preview N 只渲前 N 秒
  const totalSec = order.reduce((s, id) => s + (layout[id]?.duration_sec || 0), 0)
    + (pj.gap || 0) * (order.length - 1);
  const preview = args.preview && args.preview > 0 ? Math.min(args.preview, totalSec) : null;
  const renderSec = preview != null ? preview : totalSec;
  const totalFrames = Math.max(1, Math.round(renderSec * fps));

  // 各场景的全局起止帧（累计舍入，保证全局对齐）
  const scenes = [];
  let cursorSec = 0;
  for (const id of order) {
    const dur = layout[id]?.duration_sec || 0;
    const gf = Math.round(cursorSec * fps);
    const gfEnd = Math.min(totalFrames, Math.round((cursorSec + dur + (pj.gap || 0)) * fps));
    const n = Math.max(0, gfEnd - gf);
    if (n > 0) scenes.push({ id, gf, n, globalStart: cursorSec, dur });
    cursorSec += dur + (pj.gap || 0);
  }

  const framesDir = path.join(projectDir, 'render', 'frames');
  fs.mkdirSync(framesDir, { recursive: true });

  const outDir = path.join(projectDir, 'out');
  fs.mkdirSync(outDir, { recursive: true });
  const slug = pj.slug || 'video';
  const outPath = args.out || path.join(outDir, preview != null ? 'preview.mp4' : `${slug}.mp4`);

  const ffmpeg = resolveFfmpeg();
  if (!ffmpeg) die('找不到 ffmpeg：装到 PATH，或设 FFMPEG_PATH，或 python 装好 imageio-ffmpeg');

  // ---------- playwright ----------
  let chromium;
  try { ({ chromium } = require('playwright-core')); }
  catch { die(`playwright-core 缺失：在技能目录 node/ 下 npm install playwright-core（见 setup_env.sh）`); }

  const browserExec = args.browser || resolveBrowserExec();
  const launchOpts = { viewport: { width: W, height: H }, deviceScaleFactor: args.scale || 1 };
  if (browserExec) { launchOpts.executablePath = browserExec; log(`浏览器：${browserExec}`); }
  else log('浏览器：用 playwright 自带 chromium（首次需 npx playwright install chromium）');

  log(`项目：${projectDir}`);
  log(`场景 ${scenes.length} 个 · 总时长 ${renderSec.toFixed(2)}s · ${totalFrames} 帧 @${fps}fps`);
  const shotMode = args.pngFast ? 'PNG 速度优先（CDP，无损）'
    : args.jpeg ? `JPEG q${args.jpegQuality || 82}` : 'PNG 精细模式';
  log(`画布 ${W}x${H} · ${shotMode} · 并发 ${args.concurrency || 3}`);

  let browser = null;
  if (!args.muxOnly) {
    browser = await chromium.launch(launchOpts);
  } else {
    // 只重新合成：不启动浏览器，直接用 render/frames 里已有的帧
    const have = fs.existsSync(framesDir) ? fs.readdirSync(framesDir).filter(f => /^f_\d+\.(png|jpg)$/.test(f)).length : 0;
    log(`--mux-only：跳过截图，用现有 ${have}/${totalFrames} 帧重新合成`);
    if (have === 0) die('render/frames 里没有帧，无法只合成');
    if (have < totalFrames) log(`⚠ 帧数不足（${have}/${totalFrames}），成片会短于 layout`);
  }

  // 章节刻度（可选：project.json.chapters = [{title, startSegment}]）
  const chapterTicks = (pj.chapters || [])
    .map(c => { const i = order.indexOf(c.startSegment); return i > 0 ? (Math.round((layout[order[0]] ? 0 : 0) + order.slice(0, i).reduce((s, x) => s + (layout[x]?.duration_sec || 0) + (pj.gap || 0), 0)) / renderSec) : null; })
    .filter(x => x != null);

  // ---------- 逐场景渲染（可并发多个 page） ----------
  const errors = [];
  let doneFrames = 0;
  const t0 = Date.now();

  async function renderScene(sc) {
    // ★ viewport 必须逐 page 指定（launch 的 viewport 不继承到 newPage）
    const page = await browser.newPage({ viewport: { width: W, height: H } });
    // --png-fast：走 CDP 截图（见 captureFrame 注释）
    const cdp = args.pngFast ? await page.context().newCDPSession(page) : null;
    const htmlPath = path.join(projectDir, 'frames', `${sc.id}.html`);
    try {
      // __MG_RENDER__ 必须在任何页面脚本之前置位（帧据此跳过自动起播）
      await page.addInitScript(`window.__MG_RENDER__ = true;`);
      await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'domcontentloaded' });

      // 字体等待：系统字体即时就绪；@font-face 有 5s 硬顶（防 CDN 卡死整片）
      await page.evaluate(`new Promise(function (resolve) {
        var cap = setTimeout(resolve, 5000);
        try {
          var links = Array.prototype.slice.call(document.querySelectorAll('link[rel="stylesheet"]'));
          Promise.all(links.map(function (l) {
            return new Promise(function (r) {
              l.addEventListener('load', r, { once: true });
              l.addEventListener('error', r, { once: true });
              try { if (l.sheet) r(); } catch (e) {}
            });
          })).then(function () {
            var step = function () { requestAnimationFrame(function () { requestAnimationFrame(resolve); }); };
            if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
              document.fonts.ready.then(function () { clearTimeout(cap); step(); });
            } else { clearTimeout(cap); step(); }
          });
        } catch (e) { clearTimeout(cap); resolve(); }
      })`);

      // 找时间轴（找不到 → 契约违规，报错而不是渲静止首帧）
      const hasTl = await page.evaluate(`Boolean(window.__tl || (window.__timelines && Object.keys(window.__timelines).length))`);
      if (!hasTl) throw new Error('帧里没有 GSAP 时间轴（window.__tl）—— 见 frame-contract.md');

      // 注入字幕层 + 进度条
      const seg = (subs.segments || []).find(s => s.id === sc.id);
      const blocks = (seg?.blocks || []).map(b => ({ from: b.from, to: b.to, text: b.text, size: b.size }));
      await page.evaluate(overlaySetupJs(blocks, fps, pj.progress !== false, chapterTicks));

      // 逐帧 seek + 截图
      for (let i = 0; i < sc.n; i++) {
        const t = i / fps;
        const globalT = sc.globalStart + t;
        await page.evaluate(frameSeek, { t, globalT, total: renderSec });
        const framePath = path.join(framesDir, `f_${String(sc.gf + i + 1).padStart(6, '0')}.${args.jpeg ? 'jpg' : 'png'}`);
        await captureFrame({ page, cdp, outPath: framePath, args, W, H });
        doneFrames++;
        if (doneFrames % 300 === 0)
          log(`进度 ${doneFrames}/${totalFrames} 帧 · ${(doneFrames / ((Date.now() - t0) / 1000)).toFixed(1)} 帧/秒`);
      }
      log(`✓ 场景 ${sc.id}：${sc.n} 帧`);
    } catch (e) {
      errors.push(`场景 ${sc.id}: ${e.message}`);
    } finally {
      await page.close();
    }
  }

  // 场景级并发（默认 3；帧级不需要——同 page 顺序 seek）
  if (!args.muxOnly) {
    // --only a,b：只重渲指定场景的帧（其余场景的帧保持不动）。
    // ★ 只允许改「帧号全在片尾、不影响其他场景偏移」的场景（通常是最后一场）；
    //   若被改场景变短，其后所有场景的帧号都会前移，必须整片重渲。
    const only = args.only && args.only.length ? args.only : null;
    if (only) {
      const unknown = only.filter((id) => !scenes.some((s) => s.id === id));
      if (unknown.length) die(`--only 里这些场景不存在：${unknown.join(', ')}`);
      const firstIdx = Math.min(...only.map((id) => order.indexOf(id)));
      if (firstIdx < order.length - 1)
        log(`⚠ --only 包含非末场场景（${order[firstIdx]}）——若其时长变化，其后场景帧号会整体前移，请整片重渲`);
      log(`--only：只渲 ${only.join(', ')}，跳过其余 ${scenes.length - new Set(only).size} 个场景`);
    }
    const queue = only ? scenes.filter((s) => only.includes(s.id)) : [...scenes];
    const conc = Math.max(1, Math.min(args.concurrency || 3, queue.length));
    const workers = Array.from({ length: conc }, () => (async () => {
      while (queue.length && !errors.length) { const sc = queue.shift(); await renderScene(sc); }
    })());
    await Promise.all(workers);
    await browser.close();
    if (errors.length) die(`渲染失败：\n  ${errors.join('\n  ')}`);

    log(`截图完成：${doneFrames} 帧，耗时 ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  }

  // ---------- ffmpeg 合成 ----------
  const audioPath = path.join(projectDir, 'audio', 'narration-full.mp3');
  const hasAudio = fs.existsSync(audioPath);
  const ext = args.jpeg ? 'jpg' : 'png';
  const cmd = [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-framerate', String(fps), '-i', path.join(framesDir, `f_%06d.${ext}`),
  ];
  if (hasAudio) cmd.push('-i', audioPath);
  // 中间帧格式与最终编码质量**解耦**：--jpeg 只换帧容器，不代表要降码率。
  // （旧行为里 --jpeg 连带降成 crf23/veryfast，是"草稿"语义；成片用 --crf 18 覆盖。）
  const crf = args.crf != null ? args.crf : (args.jpeg ? 23 : 18);
  const preset = args.preset || (args.jpeg ? 'veryfast' : 'medium');
  cmd.push(
    '-c:v', 'libx264', '-preset', preset,
    '-crf', String(crf), '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
  );
  log(`编码：libx264 · preset ${preset} · crf ${crf}`);
  if (hasAudio) {
    cmd.push('-c:a', 'aac', '-b:a', '160k');
    // 音轨短于视频时补静音，而不是用 -shortest 砍掉视频尾部。
    // layout 的 video_duration_sec 含片尾留白（末块字幕的收尾余韵），
    // -shortest 会按音轨长度截视频，把这段留白连同最后一块字幕一起切掉
    // （实测：片尾字幕从设计的 1.5s 缩到 1.16s）。改用 apad 补静音 + -t 锁视频长度。
    cmd.push('-af', 'apad', '-t', renderSec.toFixed(3));
  }
  cmd.push(outPath);

  log(hasAudio ? `合成：${totalFrames} 帧 + ${audioPath}` : '合成：无音轨（配音还没生成）');
  execFileSync(ffmpeg, cmd, { stdio: 'inherit' });

  log(`✓ 成片：${outPath}`);
  log(`  帧目录：${framesDir}（--keep-frames 未指定且为完整渲时，保留供 QC）`);

  if (!args.keepFrames && preview != null) {
    // 预览模式顺手清掉草稿帧，避免占盘；完整渲保留（QC/封面要用）
    for (const f of fs.readdirSync(framesDir)) fs.unlinkSync(path.join(framesDir, f));
  }
}

main().catch(e => die(e.stack || String(e)));
