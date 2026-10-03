#!/usr/bin/env node
/**
 * render_video.mjs —— html-explainer 的确定性 HTML→MP4 渲染器（v2.0）
 *
 * 【血统】
 *  - 画面契约（HTML + GSAP 单文件场景、系统字体）来自 html-video 的帧形态；
 *    但它用「实时录制 + 裁引导期」，天然带一整类坑（__hvUnfreeze 起播、Google Fonts
 *    6s 超时、字体 swap 中途换脸、leadInMs 不稳）。本渲染器改用**确定性逐帧渲染**：
 *    暂停时间轴 → seek 到 t → 截图，上述坑整类消除。
 *
 * 【每帧渲染管线】
 *   1. tl.pause(t, false)    GSAP 时间轴同步渲染到 t（false = 放行回调）
 *   2. getAnimations() seek   CSS @keyframes 也确定性对齐
 *   3. __mgSubUpdate(t)       注入的字幕层按块表硬切
 *   4. __mgProgressUpdate()   注入的进度条按 (globalT/total) 填充
 *   5. 双 rAF + screenshot    保证合成器已画出本帧
 *   6. （可选）快门运动模糊：同一帧在快门区间里 seek 多次、各截一张，
 *      交给 scripts/blur_integrate.py 在**线性光**下积分 —— 这才是真的运动模糊。
 *
 * 【v2.0 新增（全部向后兼容，默认行为不变）】
 *   · --quality 1080p|2k|4k  与 --fps 30|60 自由组合；--profile 给成套预设
 *   · --shutter <度>          真实的快门积分（0=关，保持旧行为）
 *   · --workers N             **多浏览器**并行（不是多 page —— Chrome 的截图编码
 *                             在浏览器进程里，共用一个浏览器时并发是白挂的）
 *   · --resume / --recycle    断点续渲 / 定期重启浏览器（4K 长片会 OOM）
 *   · --audio <文件>          指定成片音轨（默认取 audio/narration-full.mp3）
 *   · <out>.render.json       渲染元数据（档位/快门/样本/耗时），给 QC 读
 *
 * 【时长口径（继承并修正两级时钟）】
 *   场景时长 = 该段 MP3 的**容器时长**（tts_build.py 已裁首尾静音并回填）。
 *   总帧数 = layout._total.total_frames（声明值，全片渲染时采信；--preview 才现算）。
 *   **不要**自己从 duration_sec 重算 —— 它舍入到 3 位小数，重算会在 .5 帧边界差 1，
 *   QC 会报假截断；`-t` 也必须按 totalFrames/fps 反算（同一分歧的第二个出口）。
 *
 * 用法（项目目录 = 含 project.json 的目录）
 *   node render_video.mjs <projectDir> [--out out/<slug>.mp4]
 *        [--profile draft|balanced|final|master|legacy] [--list-profiles]
 *        [--quality 1080p|2k|4k] [--fps 30|60] [--scale 1]
 *        [--shutter 180] [--samples 8] [--motion-gap 24] [--samples-min 4] [--samples-max 12]
 *        [--workers 6] [--concurrency 3] [--recycle 150] [--resume]
 *        [--preview 30] [--keep-frames] [--mux-only] [--only <场景id,场景id>]
 *        [--audio audio/narration-full.mp3]
 *        [--png-fast|--jpeg] [--jpeg-quality 95] [--crf 18] [--preset medium] [--browser <exe>]
 *
 * 环境解析顺序：
 *   浏览器  env BROWSER_PATH → Chrome → Edge → playwright 自带 chromium
 *   ffmpeg  env FFMPEG_PATH → PATH → python -c imageio_ffmpeg（托管 venv）
 *   python  env PY → PATH python（用来问 imageio-ffmpeg 要静态 ffmpeg、跑积分器）
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, '..');
const require = createRequire(path.join(SKILL_ROOT, 'node', 'package.json'));
const SELF = path.basename(fileURLToPath(import.meta.url));

// ---------- 工具 ----------
const log = (msg) => process.stderr.write(`[render] ${msg}\n`);
const die = (msg) => { process.stderr.write(`[render] ✗ ${msg}\n`); process.exit(1); };
const fmt = (n, d = 1) => Number(n).toFixed(d);

// ---------- 画质 / 帧率 / 档位 ----------
/**
 * 档位 = 一组默认值。显式传入的开关**永远覆盖**档位给的默认值。
 * 速度数字是本机（16 核 / Chrome / 1080p 纯 CSS 帧）实测的**量级**，
 * 真实耗时随帧内容（纯 CSS 图形 ↔ 满幅照片）能差 10× 以上 —— 见 references/render-profiles.md。
 */
const PROFILES = {
  legacy:   { quality: '1080p', fps: 0,  shutter: 0,   shot: 'png',      crf: 18, preset: 'medium',   workers: 0, concurrency: 3, note: '1.4.x 行为：单浏览器 + 场景级并发 + PNG（逐位复现旧成片）' },
  draft:    { quality: '1080p', fps: 30, shutter: 0,   shot: 'png-fast', crf: 20, preset: 'veryfast', workers: 6, concurrency: 3, note: '打样/迭代：无运动模糊，快' },
  balanced: { quality: '1080p', fps: 30, shutter: 180, shot: 'png-fast', crf: 18, preset: 'medium',   workers: 6, concurrency: 3, note: '默认推荐：有运动模糊、码率够、速度可接受' },
  final:    { quality: '4k',    fps: 60, shutter: 180, shot: 'png-fast', crf: 16, preset: 'slow',     workers: 8, concurrency: 3, note: '终稿：4K60 + 快门运动模糊（工作量约 1080p30 的 8–12×，并行后墙钟差距小得多）' },
  master:   { quality: '4k',    fps: 60, shutter: 180, shot: 'png',      crf: 14, preset: 'veryslow', workers: 8, concurrency: 3, note: '极限画质：PNG 精细 + 最慢编码（很慢，只在最终交付时用）' },
};
const QUALITY = { '1080p': 1080, '2k': 1440, '4k': 2160 };

function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--out') a.out = argv[++i];
    else if (t === '--profile') a.profile = argv[++i];
    else if (t === '--list-profiles') a.listProfiles = true;
    else if (t === '--quality') a.quality = argv[++i];
    else if (t === '--preview') a.preview = parseFloat(argv[++i]);
    else if (t === '--fps') a.fps = parseFloat(argv[++i]);
    else if (t === '--shutter') a.shutter = parseFloat(argv[++i]);
    else if (t === '--samples') a.samples = parseInt(argv[++i], 10);
    else if (t === '--motion-gap') a.motionGap = parseFloat(argv[++i]);
    else if (t === '--samples-min') a.samplesMin = parseInt(argv[++i], 10);
    else if (t === '--samples-max') a.samplesMax = parseInt(argv[++i], 10);
    else if (t === '--workers') a.workers = parseInt(argv[++i], 10);
    else if (t === '--concurrency') a.concurrency = parseInt(argv[++i], 10);
    else if (t === '--recycle') a.recycle = parseInt(argv[++i], 10);
    else if (t === '--resume') a.resume = true;
    else if (t === '--jpeg') a.jpeg = true;
    else if (t === '--jpeg-quality') a.jpegQuality = parseInt(argv[++i], 10);
    else if (t === '--png-fast') a.pngFast = true;
    else if (t === '--crf') a.crf = parseInt(argv[++i], 10);
    else if (t === '--preset') a.preset = argv[++i];
    else if (t === '--scale') a.scale = parseFloat(argv[++i]);
    else if (t === '--audio') a.audio = argv[++i];
    else if (t === '--keep-frames') a.keepFrames = true;
    else if (t === '--mux-only') a.muxOnly = true;
    else if (t === '--only') a.only = String(argv[++i] || '').split(',').map((s) => s.trim()).filter(Boolean);
    else if (t === '--browser') a.browser = argv[++i];
    else if (!t.startsWith('--')) a._.push(t);
  }
  return a;
}

function printProfiles() {
  process.stderr.write('可用档位（显式开关永远覆盖档位默认值）：\n\n');
  process.stderr.write('  档位       画质    帧率   快门    截图模式   crf  preset      浏览器  说明\n');
  for (const [k, p] of Object.entries(PROFILES)) {
    process.stderr.write(`  ${k.padEnd(10)} ${p.quality.padEnd(7)} ${String(p.fps || 30).padEnd(6)} ` +
      `${String(p.shutter ? p.shutter + '°' : '关').padEnd(7)} ${p.shot.padEnd(9)} ${String(p.crf).padEnd(4)} ` +
      `${p.preset.padEnd(11)} ${String(p.workers || 1).padEnd(7)} ${p.note}\n`);
  }
  process.stderr.write(`
画质 → 分辨率（在 1920×1080 画布上放大 deviceScaleFactor）：
  1080p → 1920×1080 (1×)    2k → 2560×1440 (1.333×)    4k → 3840×2160 (2×)
  ★ 画布 viewport 恒为项目尺寸，只改 deviceScaleFactor —— 布局逐像素不变，只是采样更密。

快门（--shutter）与运动模糊：
  180° = 半个帧间隔（电影常规）。快动作超过 80px/帧 时不开快门会重影成串。
  开了快门后每一帧要截 K 张再积分，hold（静帧）只截 2 张就跳过 → 静止段几乎不额外耗时。
  页面若定义 window.__motion(t0,t1)（屏幕最远位移 px），样本数会按 --motion-gap 自适应；
  没有就固定 --samples（默认 8）。

实测耗时量级（本机 16 核、1080p 纯 CSS 图形帧、逐帧渲染）见 references/render-profiles.md。
`);
}

// ---------- 托管 python 探测（PATH 上没有 python 时的兜底） ----------
function findManagedPythons(isWin) {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  if (!home) return [];
  const roots = [
    path.join(home, '.workbuddy', 'binaries', 'python', 'envs'),
    path.join(home, '.workbuddy', 'binaries', 'python', 'versions'),
  ];
  const found = [];
  for (const root of roots) {
    let dirs = [];
    try { dirs = fs.readdirSync(root); } catch { continue; }
    for (const d of dirs) {
      const cands = isWin
        ? [path.join(root, d, 'Scripts', 'python.exe'), path.join(root, d, 'python.exe')]
        : [path.join(root, d, 'bin', 'python'), path.join(root, d, 'bin', 'python3')];
      for (const p of cands) if (fs.existsSync(p)) { found.push(p); break; }
    }
  }
  return found;
}

function resolvePython() {
  const isWin = process.platform === 'win32';
  for (const py of [process.env.PY, ...findManagedPythons(isWin), 'python3', 'python'].filter(Boolean)) {
    try {
      execFileSync(py, ['-c', 'import numpy, PIL'], { stdio: 'ignore' });
      return py;
    } catch { /* next */ }
  }
  return null;
}

// ---------- ffmpeg 解析 ----------
function resolveFfmpeg() {
  if (process.env.FFMPEG_PATH && fs.existsSync(process.env.FFMPEG_PATH)) return process.env.FFMPEG_PATH;
  const isWin = process.platform === 'win32';
  const name = isWin ? 'ffmpeg.exe' : 'ffmpeg';
  for (const d of (process.env.PATH || '').split(path.delimiter)) {
    if (!d) continue;
    const p = path.join(d, name);
    try { if (fs.existsSync(p)) return p; } catch { /* ignore */ }
  }
  const pyCandidates = [process.env.PY, ...findManagedPythons(isWin), 'python3', 'python'].filter(Boolean);
  for (const py of pyCandidates) {
    try {
      const out = execFileSync(py, ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
        { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
      if (out && fs.existsSync(out)) return out;
    } catch { /* next */ }
  }
  return null;
}

// ---------- 浏览器解析 ----------
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
  return null;
}

// ---------- 注入页面的字幕层 / 进度条 ----------
const OVERLAY_CSS = `
  #mg-subs { position: fixed; inset: 0; pointer-events: none; z-index: 900; }
  #mg-subs .mg-sub {
    position: absolute; left: 50%; bottom: 96px; transform: translateX(-50%);
    white-space: nowrap; text-align: center;
    font-family: 'Microsoft YaHei', 'PingFang SC', 'Noto Sans CJK SC', 'Source Han Sans SC', sans-serif;
    font-weight: 700; font-size: 44px; line-height: 1.2; color: var(--mg-sub-fg, #FFFFFF);
    text-shadow:
      4px 0 0 var(--mg-sub-stroke, #000), -4px 0 0 var(--mg-sub-stroke, #000), 0 4px 0 var(--mg-sub-stroke, #000), 0 -4px 0 var(--mg-sub-stroke, #000),
      2.4px 2.4px 0 var(--mg-sub-stroke, #000), -2.4px 2.4px 0 var(--mg-sub-stroke, #000), 2.4px -2.4px 0 var(--mg-sub-stroke, #000), -2.4px -2.4px 0 var(--mg-sub-stroke, #000),
      1.2px 1.2px 0 var(--mg-sub-stroke, #000), -1.2px 1.2px 0 var(--mg-sub-stroke, #000), 1.2px -1.2px 0 var(--mg-sub-stroke, #000), -1.2px -1.2px 0 var(--mg-sub-stroke, #000),
      3.2px 1.06px 0 var(--mg-sub-stroke, #000), -3.2px 1.06px 0 var(--mg-sub-stroke, #000), 3.2px -1.06px 0 var(--mg-sub-stroke, #000), -3.2px -1.06px 0 var(--mg-sub-stroke, #000),
      1.06px 3.2px 0 var(--mg-sub-stroke, #000), -1.06px 3.2px 0 var(--mg-sub-stroke, #000), 1.06px -3.2px 0 var(--mg-sub-stroke, #000), -1.06px -3.2px 0 var(--mg-sub-stroke, #000),
      2.83px 2.83px 0 var(--mg-sub-stroke, #000), -2.83px 2.83px 0 var(--mg-sub-stroke, #000), 2.83px -2.83px 0 var(--mg-sub-stroke, #000), -2.83px -2.83px 0 var(--mg-sub-stroke, #000);
  }
  #mg-progress { position: fixed; left: 0; right: 0; bottom: 0; height: 12px;
    z-index: 901; pointer-events: none; background: var(--mg-track, rgba(255,255,255,.10)); }
  #mg-progress .mg-bar { height: 100%; width: 0%;
    background: var(--accent, #E4AE29); box-shadow: 0 0 12px var(--accent-glow, rgba(228,174,41,.55)); }
  #mg-progress .mg-tick { position: absolute; top: 0; width: 2px; height: 100%;
    background: var(--mg-tick, rgba(255,255,255,.38)); }
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
//   **返回而不执行**，导致每帧都是静止首帧（不报错、截图照写盘）。
const frameSeek = async (o) => {
  const { t, globalT, total } = o;
  let tl = window.__tl || null;
  if (!tl && window.__timelines) {
    for (const k in window.__timelines) { if (window.__timelines[k]) { tl = window.__timelines[k]; break; } }
  }
  if (!tl) throw new Error('no GSAP timeline found (window.__tl)');
  // ★ 第二参必须显式 false：GSAP 默认 true 会掐掉本次 seek 触发的回调，
  //   此时用 onUpdate 写 textContent 的数字滚动会永远停在初值（不报错、成片数字不动）。
  tl.pause(t, false);
  if (document.getAnimations) {
    document.getAnimations().forEach((a) => {
      try { a.pause(); a.currentTime = Math.round(t * 1000); } catch (e) { /* ignore */ }
    });
  }
  if (window.__mgSubUpdate) window.__mgSubUpdate(t);
  if (window.__mgProgressUpdate) window.__mgProgressUpdate(total ? (globalT / total) : 0);
  await new Promise((r) => { requestAnimationFrame(() => { requestAnimationFrame(r); }); });
  return tl.time();
};

// ---------- 截图：三种模式 ----------
// PNG（playwright 默认）对**照片满幅帧**极慢（实测 582ms/张 vs 纯色帧 45ms，13×），
// 因为 PNG 是无损 deflate，高熵内容既压不小也压不快。
//   --png-fast：CDP optimizeForSpeed，逐像素无损、约 4.4× 加速（体积 +22%）
//   --jpeg：q82 41ms（13×）；q95 52ms，PSNR 41.7dB（低于 x264 crf18 自身失真，成片看不出）
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
    path: outPath, type: args.jpeg ? 'jpeg' : 'png',
    quality: args.jpeg ? (args.jpegQuality || 82) : undefined,
  });
}

async function captureBytes({ page, cdp }) {
  if (cdp) {
    const r = await cdp.send('Page.captureScreenshot',
      { format: 'png', optimizeForSpeed: true, captureBeyondViewport: false });
    return Buffer.from(r.data, 'base64');
  }
  return page.screenshot({ type: 'png' });
}

const pad6 = (n) => String(n).padStart(6, '0');
const frameName = (n, ext) => `f_${pad6(n)}.${ext}`;

// ---------- 主流程 ----------
async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.listProfiles) { printProfiles(); return; }

  const projectDir = path.resolve(args._[0] || '.');
  const pjPath = path.join(projectDir, 'project.json');
  if (!fs.existsSync(pjPath)) die(`没有 project.json：${pjPath}`);
  const pj = JSON.parse(fs.readFileSync(pjPath, 'utf8'));

  // ---------- 档位解析：档位给默认，显式开关覆盖 ----------
  const profName = args.profile || 'balanced';
  const prof = PROFILES[profName];
  if (!prof) die(`没有档位 ${profName}（可选：${Object.keys(PROFILES).join(' / ')}）`);
  const useLegacy = profName === 'legacy';

  const pjW = pj.width || 1920, pjH = pj.height || 1080;
  const quality = args.quality || prof.quality;
  if (!(quality in QUALITY)) die(`--quality 只支持 ${Object.keys(QUALITY).join(' / ')}`);
  // 画布 viewport 恒为项目尺寸；只改 deviceScaleFactor（布局逐像素不变，采样更密）
  const scale = args.scale != null ? args.scale
    : (args.quality != null || prof.quality !== '1080p') ? QUALITY[quality] / pjH : (prof.scale || 1);
  const fps = args.fps || pj.fps || prof.fps || 30;
  const shutter = args.shutter != null ? args.shutter : prof.shutter;
  const useShutter = shutter > 0;
  const workers = args.workers != null ? args.workers : (prof.workers || 0);
  const useWorkers = !useLegacy && (workers > 0);
  const shotPngFast = args.pngFast || (!args.jpeg && prof.shot === 'png-fast');
  const crf = args.crf != null ? args.crf : prof.crf;
  const preset = args.preset || prof.preset;
  const outW = Math.round(pjW * scale), outH = Math.round(pjH * scale);

  const order = pj.order || [];
  if (!order.length) die('project.json 里没有 order（场景顺序）');

  const layoutPath = path.join(projectDir, 'layout.json');
  if (!fs.existsSync(layoutPath)) die(`没有 layout.json（先跑 timeline_build.py）：${layoutPath}`);
  const layout = JSON.parse(fs.readFileSync(layoutPath, 'utf8'));

  let subs = { fps, segments: [] };
  const subsPath = path.join(projectDir, 'subs.json');
  if (fs.existsSync(subsPath)) subs = JSON.parse(fs.readFileSync(subsPath, 'utf8'));

  for (const id of order) {
    if (!fs.existsSync(path.join(projectDir, 'frames', `${id}.html`)))
      die(`缺场景帧：frames/${id}.html`);
  }

  const totalSec = order.reduce((s, id) => s + (layout[id]?.duration_sec || 0), 0)
    + (pj.gap || 0) * (order.length - 1);
  const preview = args.preview && args.preview > 0 ? Math.min(args.preview, totalSec) : null;
  const renderSec = preview != null ? preview : totalSec;

  const declaredFrames = Number(layout?._total?.total_frames);
  const useDeclared = preview == null && Number.isFinite(declaredFrames) && declaredFrames > 0;
  const totalFrames = useDeclared ? declaredFrames : Math.max(1, Math.round(renderSec * fps));

  // 帧号边界必须构造性无缝：先按累计时间一次算好每场起点，再令第 i 场终点 = 第 i+1 场起点。
  // 旧写法现场重算 `cursorSec+dur+gap`，浮点上可能差一个 ULP，舍入后正好差 1 →
  // 相邻场景之间漏 1 帧 → image2 解复用器遇缺号停止解码 → 成片中段断流（且 ffmpeg 退出码 0）。
  const sceneStarts = [];
  {
    let c = 0;
    for (const id of order) {
      sceneStarts.push(c);
      c += (layout[id]?.duration_sec || 0) + (pj.gap || 0);
    }
  }
  const scenes = [];
  for (let i = 0; i < order.length; i++) {
    const id = order[i];
    const gf = Math.round(sceneStarts[i] * fps);
    const boundary = i + 1 < order.length ? Math.round(sceneStarts[i + 1] * fps) : totalFrames;
    const gfEnd = Math.min(totalFrames, boundary);
    const n = Math.max(0, gfEnd - gf);
    if (n > 0) scenes.push({ id, gf, n, globalStart: sceneStarts[i], dur: layout[id]?.duration_sec || 0 });
  }

  const framesDir = path.join(projectDir, 'render', 'frames');
  const shutterDir = path.join(projectDir, 'render', 'shutter');
  fs.mkdirSync(framesDir, { recursive: true });

  const outDir = path.join(projectDir, 'out');
  fs.mkdirSync(outDir, { recursive: true });
  const slug = pj.slug || 'video';
  // --out：相对路径按**项目目录**解析（与 --audio 一致），绝对路径原样用。
  // 这样文档里的 `--out out/<slug>.mp4` 就真的落在 <project>/out/ 下，而不是调用方的 cwd。
  const outPath = args.out
    ? (path.isAbsolute(args.out) ? args.out : path.join(projectDir, args.out))
    : path.join(outDir, preview != null ? 'preview.mp4' : `${slug}.mp4`);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });

  const ffmpeg = resolveFfmpeg();
  if (!ffmpeg) die('找不到 ffmpeg：装到 PATH，或设 FFMPEG_PATH，或 python 装好 imageio-ffmpeg');

  let chromium;
  try { ({ chromium } = require('playwright-core')); }
  catch { die(`playwright-core 缺失：在技能目录 node/ 下 npm install playwright-core（见 setup_env.sh）`); }

  const browserExec = args.browser || resolveBrowserExec();
  const launchOpts = { viewport: { width: pjW, height: pjH }, deviceScaleFactor: scale };

  log(`项目：${projectDir}`);
  log(`档位：${profName} · 场景 ${scenes.length} 个 · ${renderSec.toFixed(2)}s · ${totalFrames} 帧 @${fps}fps`);
  const shotMode = args.jpeg ? `JPEG q${args.jpegQuality || 82}`
    : shotPngFast ? 'PNG 速度优先（CDP，无损）' : 'PNG 精细模式';
  log(`画布 ${pjW}×${pjH} viewport × ${fmt(scale, 3)} = 输出 ${outW}×${outH} · ${shotMode}`);
  log(useShutter
    ? `快门：${shutter}°（真实运动模糊积分，${args.samples || 8} 样本/动帧，gap ${args.motionGap || 24}px，${args.samplesMin || 4}–${args.samplesMax || 12}）`
    : '快门：关（无运动模糊）');
  log(useWorkers
    ? `并行：${workers} 个**独立浏览器**进程级按帧步进（不是多 page —— 共用一个浏览器时并发是白挂的）`
    : `并行：单浏览器 + 场景级并发 ${args.concurrency || prof.concurrency || 3}（1.4.x 行为）`);
  if (browserExec) log(`浏览器：${browserExec}`);

  const chapterTicks = (pj.chapters || [])
    .map((c) => {
      const i = order.indexOf(c.startSegment);
      return i > 0 ? Math.round(order.slice(0, i)
        .reduce((s, x) => s + (layout[x]?.duration_sec || 0) + (pj.gap || 0), 0)) / renderSec : null;
    })
    .filter((x) => x != null);

  // ---------- 超时看门狗 ----------
  // ★ 为什么必须有：Chrome 在多实例并发下偶发挂死（tab 崩溃 / 截图 IPC 不返回）。
  //   原实现里 worker 的每个 await 都没有超时 —— 一个 worker 挂住 → Promise.all 永不
  //   settle → **整个渲染静默卡死**（实测 108 帧跑 16 分钟不结束、日志停在"帧级步进"、
  //   磁盘上留 1 帧缺号 + 几帧只有 1 个样本）。这类失败必须是**可恢复**的：
  //   超时 → 关掉这个浏览器 → 重开 → 重试同一帧。
  const SHOT_TIMEOUT_MS = Math.max(10000, Number(process.env.HX_SHOT_TIMEOUT_MS || 0) || 60000);
  const MAX_FRAME_RETRY = Math.max(1, Number(process.env.HX_FRAME_RETRY || 0) || 3);
  // 全局停顿看门狗：整条管线 X 秒没有任何新帧 → 判定为进程级挂死，直接失败退出
  // （而不是让 Promise.all 永久等待 —— 那才是原实现的致命处）
  const WATCHDOG_MS = Math.max(60000, SHOT_TIMEOUT_MS + 45000);
  const closeQuiet = (p) => { try { return withTimeout(p, 8000, 'page.close'); } catch { return Promise.resolve(); } };
  let retries = 0;
  function withTimeout(promise, ms, label) {
    let timer = null;
    const guard = new Promise((_, rej) => {
      timer = setTimeout(() => rej(new Error(`${label} 超时（${ms}ms 无响应）`)), ms);
    });
    return Promise.race([promise, guard]).finally(() => clearTimeout(timer));
  }

  const errors = [];
  let doneFrames = 0;
  let captures = 0;
  let stillFrames = 0;
  const t0 = Date.now();
  const ext = args.jpeg ? 'jpg' : 'png';

  // ---- 一个页面的准备（两种路径共用） ----
  async function setupPage(browser, id) {
    const page = await browser.newPage({ viewport: { width: pjW, height: pjH } });
    const cdp = shotPngFast ? await page.context().newCDPSession(page) : null;
    const htmlPath = path.join(projectDir, 'frames', `${id}.html`);
    await page.addInitScript(`window.__MG_RENDER__ = true;`);
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'domcontentloaded' });
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
    const hasTl = await page.evaluate(`Boolean(window.__tl || (window.__timelines && Object.keys(window.__timelines).length))`);
    if (!hasTl) throw new Error('帧里没有 GSAP 时间轴（window.__tl）—— 见 frame-contract.md');
    const seg = (subs.segments || []).find((s) => s.id === id);
    const blocks = (seg?.blocks || []).map((b) => ({ from: b.from, to: b.to, text: b.text, size: b.size }));
    await page.evaluate(overlaySetupJs(blocks, fps, pj.progress !== false, chapterTicks));
    const hasMotion = await page.evaluate(`typeof window.__motion === 'function'`);
    return { page, cdp, hasMotion };
  }

  // ---- 单帧：抓图（含快门样本） ----
  async function shotOne(ctx, sc, i) {
    const t = i / fps;
    const globalT = sc.globalStart + t;
    const n = sc.gf + i + 1;
    const finalPath = path.join(framesDir, frameName(n, ext));

    if (!useShutter) {
      await ctx.page.evaluate(frameSeek, { t, globalT, total: renderSec });
      await captureFrame({ page: ctx.page, cdp: ctx.cdp, outPath: finalPath, args, W: pjW, H: pjH });
      captures++;
      return;
    }

    // 快门开合区间（秒），以帧时刻为中心
    const openS = (shutter / 360) / fps;
    const tA = Math.max(0, t - openS / 2);
    const tB = Math.min(renderSec - 1e-6, t + openS / 2);
    let S = args.samples || 8;
    if (ctx.hasMotion) {
      try {
        const far = await ctx.page.evaluate(
          ({ a, b }) => window.__motion(a, b), { a: tA, b: tB });
        const gap = args.motionGap || 24;
        const smin = args.samplesMin || 4, smax = args.samplesMax || 12;
        if (Number.isFinite(far)) S = Math.min(smax, Math.max(smin, Math.ceil((far * scale) / gap)));
      } catch { /* 页面 __motion 抛错就用固定样本数 */ }
    }
    const times = [];
    for (let k = 0; k < S; k++) {
      times.push(Math.min(Math.max(tA + (tB - tA) * ((k + 0.5) / S), 0), renderSec - 1e-6));
    }
    const first = await (async () => { await ctx.page.evaluate(frameSeek, { t: times[0], globalT: sc.globalStart + times[0], total: renderSec }); return captureBytes({ page: ctx.page, cdp: ctx.cdp, args }); })();
    const last = await (async () => { await ctx.page.evaluate(frameSeek, { t: times[S - 1], globalT: sc.globalStart + times[S - 1], total: renderSec }); return captureBytes({ page: ctx.page, cdp: ctx.cdp, args }); })();
    captures += 2;
    if (S > 1 && first.equals(last)) {
      // hold：快门开合期间什么都没动 —— 直接落盘，剩下的样本全省
      fs.writeFileSync(finalPath, first);
      captures -= 1;   // 只算一张有效
      stillFrames++;
      return;
    }
    // 动帧：把 K 张样本写到 shutter/ 目录，积分交给 blur_integrate.py（numpy 线性光）
    const dir = path.join(shutterDir, `f_${pad6(n)}`);
    fs.rmSync(dir, { recursive: true, force: true });
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, '00.png'), first);
    for (let k = 1; k < S - 1; k++) {
      await ctx.page.evaluate(frameSeek, { t: times[k], globalT: sc.globalStart + times[k], total: renderSec });
      const b = await captureBytes({ page: ctx.page, cdp: ctx.cdp, args });
      fs.writeFileSync(path.join(dir, String(k).padStart(2, '0') + '.png'), b);
      captures++;
    }
    fs.writeFileSync(path.join(dir, String(S - 1).padStart(2, '0') + '.png'), last);
  }

  // ---------- 路径 A：1.4.x 行为（单浏览器 + 场景级并发 + 无快门） ----------
  async function renderLegacy() {
    const browser = await chromium.launch(launchOpts);
    const only = args.only && args.only.length ? args.only : null;
    if (only) {
      const unknown = only.filter((id) => !scenes.some((s) => s.id === id));
      if (unknown.length) die(`--only 里这些场景不存在：${unknown.join(', ')}`);
      const firstIdx = Math.min(...only.map((id) => order.indexOf(id)));
      if (firstIdx < order.length - 1) log(`⚠ --only 包含非末场场景（${order[firstIdx]}）——若其时长变化，其后场景帧号会整体前移，请整片重渲`);
    }
    const queue = only ? scenes.filter((s) => only.includes(s.id)) : [...scenes];
    if (only) log(`--only：只渲 ${only.join(', ')}，跳过其余 ${scenes.length - new Set(only).size} 个场景`);
    const conc = Math.max(1, Math.min(args.concurrency || prof.concurrency || 3, queue.length));
    const workersN = Array.from({ length: conc }, () => (async () => {
      while (queue.length && !errors.length) {
        const sc = queue.shift();
        let ctx = null;
        try {
          ctx = await withTimeout(setupPage(browser, sc.id), SHOT_TIMEOUT_MS, `加载场景 ${sc.id}`);
          for (let i = 0; i < sc.n; i++) {
            await withTimeout(shotOne(ctx, sc, i), SHOT_TIMEOUT_MS, `截 ${sc.id} 第 ${i + 1} 帧`);
          }
          doneFrames += sc.n;
          log(`✓ 场景 ${sc.id}：${sc.n} 帧`);
        } catch (e) {
          errors.push(`场景 ${sc.id}: ${e.message}`);
        } finally {
          if (ctx) await closeQuiet(ctx.page.close());
        }
      }
    })());
    await Promise.all(workersN);
    await browser.close();
  }

  // ---------- 路径 B：多浏览器 + 帧级步进（v2.0，可开快门） ----------
  async function renderParallel() {
    const only = args.only && args.only.length ? args.only : null;
    if (only) {
      const unknown = only.filter((id) => !scenes.some((s) => s.id === id));
      if (unknown.length) die(`--only 里这些场景不存在：${unknown.join(', ')}`);
      log(`⚠ --only 与新并行路径同时使用：只渲 ${only.join(', ')}（帧号仍按全局锚定，安全）`);
    }
    const use = only ? scenes.filter((s) => only.includes(s.id)) : scenes;

    // 展开成帧清单：{sc, i, n}
    const all = [];
    for (const sc of use) for (let i = 0; i < sc.n; i++) all.push({ sc, i, n: sc.gf + i + 1 });

    const pendingFrames = args.resume
      ? all.filter((f) => !(fs.existsSync(path.join(framesDir, frameName(f.n, ext)))
        || fs.existsSync(path.join(shutterDir, `f_${pad6(f.n)}`))))
      : all;
    if (args.resume) log(`--resume：${all.length - pendingFrames.length} 帧已在盘上，补渲 ${pendingFrames.length} 帧`);

    const nw = Math.max(1, Math.min(workers, pendingFrames.length || 1));
    log(`帧级步进：${nw} 个浏览器，每个认领 f ≡ k (mod ${nw})`);
    let next = 0;
    const take = () => (next < pendingFrames.length ? pendingFrames[next++] : null);

    const jobs = Array.from({ length: nw }, (_, k) => (async () => {
      let browser = null;
      let ctx = null;              // {page, cdp, hasMotion}
      let curScene = null;
      let mine = 0;
      const killBrowser = async () => {
        try { if (ctx) await closeQuiet(ctx.page.close()); } catch { /* ignore */ }
        ctx = null; curScene = null;
        try { if (browser) await withTimeout(browser.close(), 10000, 'browser.close'); } catch { /* ignore */ }
        browser = null;
      };
      const relaunch = async () => {
        await killBrowser();
        browser = await withTimeout(chromium.launch(launchOpts), SHOT_TIMEOUT_MS, `worker ${k} 启动浏览器`);
      };
      try {
        await relaunch();
        for (;;) {
          const f = take();
          if (!f || errors.length) break;
          if (ctx && curScene !== f.sc.id) { await closeQuiet(ctx.page.close()); ctx = null; }
          // ---- 单帧：最多 MAX_FRAME_RETRY 次；每次失败都重启浏览器 ----
          let attempt = 0;
          for (;;) {
            try {
              if (!ctx) {
                ctx = await withTimeout(setupPage(browser, f.sc.id), SHOT_TIMEOUT_MS,
                  `worker ${k} 加载场景 ${f.sc.id}`);
                curScene = f.sc.id;
              }
              await withTimeout(shotOne(ctx, f.sc, f.i), SHOT_TIMEOUT_MS,
                `worker ${k} 截 f_${pad6(f.n)}`);
              break;   // ✓ 本帧完成
            } catch (e) {
              attempt++;
              if (attempt >= MAX_FRAME_RETRY) {
                errors.push(`worker ${k}: f_${pad6(f.n)}（场景 ${f.sc.id}）连续 ${attempt} 次失败 —— ${e.message}`);
                break;
              }
              retries++;
              log(`⚠ worker ${k}：f_${pad6(f.n)} ${e.message} —— 重启浏览器后重试（${attempt}/${MAX_FRAME_RETRY - 1}）`);
              await relaunch();
              // 超时的截图可能已写出半张 / 坏样本 —— 清掉，避免污染积分
              try { fs.rmSync(path.join(framesDir, frameName(f.n, ext)), { force: true }); } catch { /* ignore */ }
              try { fs.rmSync(path.join(shutterDir, `f_${pad6(f.n)}`), { recursive: true, force: true }); } catch { /* ignore */ }
            }
          }
          if (errors.length) break;
          mine++; doneFrames++;
          if (doneFrames % 200 === 0 || doneFrames === pendingFrames.length) {
            log(`进度 ${doneFrames}/${totalFrames} 帧 · ${fmt(doneFrames / ((Date.now() - t0) / 1000), 1)} 帧/秒 · 截 ${captures} 次`
              + (retries ? ` · 重试 ${retries} 次` : ''));
          }
          if (args.recycle && mine && mine % args.recycle === 0) {
            // 长时间截 4K 的 Chrome 会越长越大，直到被系统关掉 —— 定期重开
            log(`浏览器重生（worker ${k}，已渲 ${mine} 帧）`);
            await relaunch();
          }
        }
      } catch (e) {
        errors.push(`worker ${k}: ${e.message}`);
      } finally {
        await killBrowser();
      }
    })());
    await Promise.all(jobs);
  }

  // ---------- 执行截图 ----------
  const skipCapture = args.muxOnly;
  // ★ 全局停顿看门狗：只要「X 秒内一帧都没有新产出」就判定为进程级挂死，直接失败退出。
  //   这是最后一道防线 —— 单个 await 的超时靠 withTimeout，但若挂点在被漏掉的 await 上，
  //   看门狗保证整条流水线**不会永久静默**（原实现实测能挂 16 分钟以上不报错）。
  let watchdog = null;
  if (!skipCapture) {
    let lastDone = 0, lastTick = Date.now();
    watchdog = setInterval(() => {
      if (doneFrames !== lastDone) { lastDone = doneFrames; lastTick = Date.now(); return; }
      const idle = (Date.now() - lastTick) / 1000;
      if (idle * 1000 > WATCHDOG_MS) {
        clearInterval(watchdog);
        process.stderr.write(`[render] ✗ 渲染停滞：${fmt(idle, 0)}s 内无新帧（已完成 ${doneFrames} 帧，重试 ${retries} 次）。\n`);
        process.stderr.write('[render]   多半是某个 Chrome 进程挂死。对策：调小 HX_SHOT_TIMEOUT_MS、或 --workers 降并发后重跑；\n');
        process.stderr.write('[render]   盘上已有的帧不会丢 —— 加 --resume 可直接接着跑。\n');
        process.exit(3);
      }
    }, 3000);
    if (watchdog.unref) watchdog.unref();
  }
  if (skipCapture) {
    const have = fs.existsSync(framesDir)
      ? fs.readdirSync(framesDir).filter((f) => /^f_\d+\.(png|jpg)$/.test(f)).length : 0;
    log(`--mux-only：跳过截图，用现有 ${have}/${totalFrames} 帧重新合成`);
    if (have === 0) die('render/frames 里没有帧，无法只合成');
    if (have < totalFrames) log(`⚠ 帧数不足（${have}/${totalFrames}），成片会短于 layout`);
  } else if (useWorkers) {
    await renderParallel();
  } else {
    await renderLegacy();
  }
  if (watchdog) clearInterval(watchdog);
  const shotSec = (Date.now() - t0) / 1000;

  if (errors.length) die(`渲染失败：\n  ${errors.join('\n  ')}`);
  if (!skipCapture) {
    log(`截图完成：${doneFrames} 帧 / ${captures} 次截图 / 其中 ${stillFrames} 帧是 hold（跳过了快门采样）`
      + ` · 耗时 ${fmt(shotSec)}s · ${fmt(doneFrames / shotSec, 2)} 帧/秒`);
  }

  // ---------- 积分（快门运动模糊的第 2 段，Python/numpy，多进程） ----------
  let integrateSec = 0;
  if (useShutter && !skipCapture) {
    const nPending = fs.existsSync(shutterDir)
      ? fs.readdirSync(shutterDir).filter((d) => fs.statSync(path.join(shutterDir, d)).isDirectory()).length : 0;
    if (nPending) {
      const py = resolvePython();
      if (!py) die('开了 --shutter 但没有可用的 python+numpy+PIL —— 装依赖或加 --shutter 0');
      log(`快门积分：${nPending} 帧待积分，交给 scripts/blur_integrate.py`);
      const tInt = Date.now();
      try {
        execFileSync(py, [path.join(__dirname, 'blur_integrate.py'), '--project', projectDir,
          '--workers', String(Math.max(1, Math.min(os.cpus().length - 1, 12)))], { stdio: 'inherit' });
      } catch (e) {
        die(`快门积分失败：${e.message}`);
      }
      integrateSec = (Date.now() - tInt) / 1000;
    } else {
      log('快门积分：没有动帧（全片都是 hold）—— 跳过');
    }
  }

  // ---------- 帧完整性闸门（合成前） ----------
  // ★ 为什么必须有：image2 解复用器碰到缺号会打印 I/O error 并**停止解码**，
  //   而 `-t` 仍把容器时长写成全长、ffmpeg 退出码还是 0 → 产出「标题 6:11、实际
  //   3:41 后无画面」的坏片，整条流水线一路绿灯。这是典型的**静默失败**。
  if (!skipCapture || true) {
    const missing = [];
    for (const sc of scenes) {
      for (let i = 0; i < sc.n; i++) {
        const n = sc.gf + i + 1;
        if (!fs.existsSync(path.join(framesDir, frameName(n, ext)))) missing.push({ n, id: sc.id });
      }
    }
    if (missing.length) {
      const byScene = new Map();
      for (const m of missing) {
        if (!byScene.has(m.id)) byScene.set(m.id, []);
        byScene.get(m.id).push(m.n);
      }
      die(`帧不完整：缺 ${missing.length} 帧，拒绝合成。\n` +
        `  （若不拦，会得到「容器标称 ${renderSec.toFixed(2)}s、实际中途断流」的坏片，且 ffmpeg 退出码为 0）\n` +
        [...byScene.entries()].map(([id, ns]) =>
          `  场景 ${id}：缺 ${ns.length} 帧 → ${ns.slice(0, 6).join(', ')}${ns.length > 6 ? ' …' : ''}`).join('\n') +
        `\n  修补：node ${SELF} <projectDir> --only ${[...byScene.keys()].join(',')}`);
    }
    log(`帧完整性 ✓ ${totalFrames}/${totalFrames} 帧齐备`);
  }

  // ---------- 音轨：--audio 优先，否则找 narration-full ----------
  let audioPath = null;
  if (args.audio) {
    audioPath = path.isAbsolute(args.audio) ? args.audio : path.join(projectDir, args.audio);
    if (!fs.existsSync(audioPath)) die(`--audio 指的文件不存在：${audioPath}`);
  } else {
    for (const c of ['audio/narration-full.mp3', 'audio/narration-full.m4a', 'audio/narration-full.wav']) {
      const p = path.join(projectDir, c);
      if (fs.existsSync(p)) { audioPath = p; break; }
    }
  }
  const hasAudio = !!audioPath;

  // ---------- ffmpeg 合成 ----------
  const cmd = [
    '-hide_banner', '-loglevel', 'error', '-xerror', '-y',
    '-framerate', String(fps), '-i', path.join(framesDir, `f_%06d.${ext}`),
  ];
  if (hasAudio) cmd.push('-i', audioPath);
  // 中间帧格式与最终编码质量解耦：--jpeg 只换帧容器，不代表要降码率
  cmd.push('-c:v', 'libx264', '-preset', preset, '-crf', String(crf), '-pix_fmt', 'yuv420p');
  if (outH >= 1440 || outW >= 2560) {
    // 4K/60 需要更高 level，否则部分播放器/平台拒收
    cmd.push('-profile:v', 'high', '-level', outH >= 2160 ? '5.2' : '5.1');
  }
  cmd.push('-movflags', '+faststart');
  log(`编码：libx264 · preset ${preset} · crf ${crf} · ${outW}×${outH} @${fps}fps`);
  if (hasAudio) {
    cmd.push('-c:a', 'aac', '-b:a', '192k');
    // 音轨短于视频时补静音，而不是用 -shortest 砍掉视频尾部（会切掉片尾留白和最后一块字幕）。
    // ★ -t 必须按 totalFrames 反算：采信声明帧数后 totalFrames/fps 会**大于** renderSec，
    //   用 renderSec 锁长照样把最后一帧切掉 —— 这是同一个舍入分歧的第二个出口。
    cmd.push('-af', 'apad', '-t', (totalFrames / fps).toFixed(3));
  }
  cmd.push(outPath);

  log(hasAudio ? `合成：${totalFrames} 帧 + ${path.basename(audioPath)}` : '合成：无音轨（配音还没生成）');
  execFileSync(ffmpeg, cmd, { stdio: 'inherit' });
  log(`✓ 成片：${outPath}`);

  // ---------- 元数据（给 QC / verify 读） ----------
  const meta = {
    version: '2.0.0', profile: profName, quality, fps,
    size: [outW, outH], viewport: [pjW, pjH], scale,
    shutter: useShutter ? shutter : 0,
    samples: useShutter ? (args.samples || 8) : 1,
    adaptive_samples: useShutter ? (args.samples == null) : false,
    shot_mode: args.jpeg ? 'jpeg' : (shotPngFast ? 'png-fast' : 'png'),
    parallel: useWorkers ? 'browsers' : 'scene-concurrency',
    workers: useWorkers ? workers : (args.concurrency || prof.concurrency || 3),
    crf, preset,
    frames: totalFrames, rendered: skipCapture ? null : doneFrames, captures: skipCapture ? null : captures,
    still_frames: skipCapture ? null : stillFrames,
    frame_retries: retries,
    audio: hasAudio ? path.relative(projectDir, audioPath).replace(/\\/g, '/') : null,
    seconds: { capture: round2(shotSec), integrate: round2(integrateSec), total: round2((Date.now() - t0) / 1000) },
    preview: preview != null,
  };
  // 元数据落在**成片旁边**（out/xxx.render.json）—— QC、bench、用户都按这个位置找
  const metaPath = path.join(path.dirname(outPath),
    `${path.basename(outPath, path.extname(outPath))}.render.json`);
  fs.writeFileSync(metaPath, JSON.stringify(meta, null, 1), 'utf8');
  log(`渲染元数据：${metaPath}`);
  log(`耗时：截图 ${fmt(shotSec)}s + 积分 ${fmt(integrateSec)}s = ${fmt((Date.now() - t0) / 1000)}s`);

  if (!args.keepFrames && preview != null) {
    for (const f of fs.readdirSync(framesDir)) fs.unlinkSync(path.join(framesDir, f));
  }
}

const round2 = (x) => Math.round(x * 100) / 100;

main().catch((e) => die(e.stack || String(e)));
