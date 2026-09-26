#!/usr/bin/env node
/**
 * cover_build.mjs —— 封面渲染器（多画幅，各一份独立排版）。
 *   169 → 1920×1080  抖音主封面（信息流/播放页）
 *    34 → 1440×1080  兼容主页 3:4 栅格（防切字）
 *   916 → 1080×1920  竖版全屏 / 小红书 / 视频号竖版（三段式，上下让开平台 UI 层）
 * ★ 默认出 169 + 34；竖版投放再加 916。**缺哪张封面帧就跳哪张**，不必三张都建。
 * ★ 出图后务必跑 check_cover.mjs 量终态几何（边距/字号/行宽/孤字/9:16 禁两栏）。
 *
 * 【为什么不用裁切】
 *   成片是 16:9。从 16:9 居中裁 3:4，只能留 3/4 的宽（丢掉两侧各 12.5%）……
 *   不对——重算：h=1080，3:4 → w=810，丢掉 1110px = 57.8% 的画面宽度。
 *   大字钩子必然被切。所以"兼容 3:4"必须是**重新排版的另一张图**，
 *   不是同一张图的裁切版。本脚本因此渲染**两份独立的 HTML**：
 *       frames/cover_169.html  → out/cover_169.png  (1920×1080)
 *       frames/cover_34.html   → out/cover_34.png   (1440×1080)
 *   两份共享同一套视觉基因（背景/配色/主视觉/钩子文案），只是构图重排。
 *
 * 【和场景帧的关系】
 *   复用 render_video.mjs 同一套底座：依赖探测链（ffmpeg/浏览器）、
 *   Playwright seek、确定性截图。差别只有三点：
 *     ① 不注入字幕层 / 进度条（封面不要字幕）
 *     ② 不逐帧，只 seek 到一个"封面时刻"（默认片尾/静置态，可 --at 指定）
 *     ③ 输出单张 PNG（可选 --jpg）
 *   封面帧同样遵守 GSAP 契约（window.__tl），所以它也能被 --at 定位到动画中间态。
 *
 * 【封面时刻怎么选】
 *   封面要"完整态"而不是入场中间态。默认 --at last：seek 到时间轴末尾
 *   （tl.duration()），即所有元素都到位的那一帧。也可以用 --at 2.4 指定绝对秒。
 *
 * 用法（项目目录 = 含 project.json 的目录）：
 *   node cover_build.mjs <projectDir> [--at last|<秒>] [--jpg] [--keep-frames]
 *        [--only 169|34] [--scale 2]
 *
 * 帧作者只要在 frames/ 下放 cover_169.html / cover_34.html 即可；
 * 缺哪个就跳过哪个（不报错），两份都在就出两张。
 *
 * 环境解析顺序（与 render_video.mjs 完全一致）：
 *   浏览器  env BROWSER_PATH → Chrome → Edge → playwright 自带 chromium
 *   ffmpeg  仅在需要后处理时用（--jpg 走 Playwright 直出，不依赖 ffmpeg）
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, '..');
const require = createRequire(path.join(SKILL_ROOT, 'node', 'package.json'));

const log = (m) => process.stderr.write(`[cover] ${m}\n`);
const die = (m) => { process.stderr.write(`[cover] ✗ ${m}\n`); process.exit(1); };

// ---------- 封面规格（改这里就能加新平台尺寸） ----------
const SPECS = {
  '169': {
    key: '169',
    label: '抖音主封面 · 16:9',
    file: 'cover_169.html',
    out: 'cover_169.png',
    width: 1920,
    height: 1080,
    note: '信息流/播放页主封面',
  },
  '34': {
    key: '34',
    label: '兼容 3:4 · 主页栅格',
    file: 'cover_34.html',
    out: 'cover_34.png',
    width: 1440,
    height: 1080,
    note: '个人主页封面栅格按 3:4 裁 —— 独立排版，防切字',
  },
  '916': {
    key: '916',
    label: '竖版 9:16 · 全屏/竖版封面',
    file: 'cover_916.html',
    out: 'cover_916.png',
    width: 1080,
    height: 1920,
    note: '抖音全屏竖版 / 小红书 / 视频号竖版封面 —— 独立排版（三段式），防上下切字',
  },
};

function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--at') a.at = argv[++i];
    else if (t === '--jpg') a.jpg = true;
    else if (t === '--only') a.only = argv[++i];
    else if (t === '--scale') a.scale = parseFloat(argv[++i]);
    else if (t === '--keep-frames') a.keepFrames = true;
    else if (t === '--browser') a.browser = argv[++i];
    else if (!t.startsWith('--')) a._.push(t);
  }
  return a;
}

// ---------- 浏览器解析（与 render_video.mjs 同一套探测链） ----------
function resolveBrowserExec() {
  if (process.env.BROWSER_PATH && fs.existsSync(process.env.BROWSER_PATH)) return process.env.BROWSER_PATH;
  const cands = [];
  if (process.platform === 'win32') {
    cands.push(
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
      path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe'),
      'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    );
  } else if (process.platform === 'darwin') {
    cands.push('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      '/Applications/Chromium.app/Contents/MacOS/Chromium');
  } else {
    cands.push('/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
      '/usr/bin/microsoft-edge');
  }
  for (const p of cands) { try { if (p && fs.existsSync(p)) return p; } catch { /* ignore */ } }
  return null;
}

// ---------- 字体就绪等待（与渲染器同款，5s 硬顶防 CDN 卡死） ----------
const FONT_WAIT = `new Promise(function (resolve) {
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
})`;

// —— 封面 seek：★必须是真正的函数字面量，不能是字符串 ——
// （字符串形式会被 Playwright 当表达式求值一次，函数体不执行、静默返回 undefined，
//   症状是封面永远停在首帧。见 lessons.md #17。）
// 封面比场景帧宽松一点：允许没有 GSAP 时间轴（纯静态封面也可以），
// 但只要有，就 seek 到指定时刻；同时同步所有 CSS 动画。
const coverSeek = async (o) => {
  const { at } = o;                       // at === null 表示"到时间轴末尾"
  let tl = window.__tl || null;
  if (!tl && window.__timelines) {
    for (const k in window.__timelines) { if (window.__timelines[k]) { tl = window.__timelines[k]; break; } }
  }
  let seekTo = 0;
  if (tl) {
    if (typeof tl.pause === 'function') tl.pause();   // 先停（防自动起播）
    const dur = (typeof tl.duration === 'function' && tl.duration()) || 0;
    seekTo = at == null ? dur : Math.min(at, dur || at);
    // ★ 必须传 suppressEvents=false：否则本次 seek 的 onUpdate/onComplete 被掐掉，
    //   用 onUpdate 写 DOM 的元素会停在初值（封面常见：数字标签）。见 lessons.md #27。
    tl.pause(seekTo, false);
  } else if (at != null) {
    seekTo = at;
  }
  if (document.getAnimations) {
    document.getAnimations().forEach((a) => {
      try { a.pause(); a.currentTime = Math.round(seekTo * 1000); } catch (e) { /* ignore */ }
    });
  }
  await new Promise((r) => { requestAnimationFrame(() => { requestAnimationFrame(r); }); });
  return { seekTo, duration: tl && typeof tl.duration === 'function' ? tl.duration() : null };
};

async function renderOne(browser, projectDir, spec, opts) {
  const htmlPath = path.join(projectDir, 'frames', spec.file);
  if (!fs.existsSync(htmlPath)) return { spec, skipped: `没有 frames/${spec.file}` };

  // ★ deviceScaleFactor 必须传给 newPage（= 建 context），**不能**传给 browser.launch ——
  //   launch 不接受该选项且静默忽略，结果封面出成 1 倍图（1920×1080 而非 3840×2160）。
  //   这是 lessons #18 的同一类坑，见 #28。
  const page = await browser.newPage({
    viewport: { width: spec.width, height: spec.height },
    deviceScaleFactor: opts.scale || 2,
  });
  try {
    await page.addInitScript(`window.__MG_RENDER__ = true;`);
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'domcontentloaded' });
    await page.evaluate(FONT_WAIT);

    // 封面帧允许纯静态（无 GSAP）—— 有就 seek，没有就用文档原样
    const at = opts.at === 'last' || opts.at == null ? null : parseFloat(opts.at);
    if (Number.isNaN(at)) throw new Error(`--at 只能是 last 或秒数，收到：${opts.at}`);
    const r = await page.evaluate(coverSeek, { at });

    const outDir = path.join(projectDir, 'out');
    fs.mkdirSync(outDir, { recursive: true });
    const outName = opts.jpg ? spec.out.replace(/\.png$/, '.jpg') : spec.out;
    const outPath = path.join(outDir, outName);
    await page.screenshot({
      path: outPath,
      type: opts.jpg ? 'jpeg' : 'png',
      quality: opts.jpg ? 92 : undefined,
      scale: 'device',          // ★ 显式取设备像素，否则可能回落到 css 像素
    });
    return {
      spec, outPath,
      detail: `seek ${r.seekTo.toFixed(2)}s${r.duration != null ? ` / 轴长 ${r.duration.toFixed(2)}s` : '（无时间轴·静态）'}`,
    };
  } finally {
    await page.close();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectDir = path.resolve(args._[0] || '.');
  const pjPath = path.join(projectDir, 'project.json');
  if (!fs.existsSync(pjPath)) die(`没有 project.json：${pjPath}`);
  const pj = JSON.parse(fs.readFileSync(pjPath, 'utf8'));

  // 只渲指定规格
  let specs = Object.values(SPECS);
  if (args.only) {
    const want = String(args.only).split(',').map(s => s.trim());
    specs = want.map(k => {
      if (!SPECS[k]) die(`未知规格 --only ${k}（可用：${Object.keys(SPECS).join(' / ')}）`);
      return SPECS[k];
    });
  }

  // 有没有封面帧？一个都没有就直接说清楚怎么建
  const present = specs.filter(s => fs.existsSync(path.join(projectDir, 'frames', s.file)));
  if (!present.length) {
    die(`frames/ 下没有封面帧。封面要**单独排版**（不是从成片抽帧、更不是裁切）——\n` +
        `    复制 assets/cover-template.html，按需做这几份：\n` +
        specs.map(s => `      frames/${s.file}   → ${s.width}×${s.height}  ${s.label}`).join('\n') +
        `\n    （只需出其中一份也可以；传了哪几份就渲哪几份）`);
  }

  let chromium;
  try { ({ chromium } = require('playwright-core')); }
  catch { die('playwright-core 缺失：在技能目录 node/ 下 npm install playwright-core（见 setup_env.sh）'); }

  const browserExec = args.browser || resolveBrowserExec();
  // ★ launch 只放浏览器进程级选项；viewport/deviceScaleFactor 属于 context，必须给 newPage。
  const launchOpts = {};
  if (browserExec) { launchOpts.executablePath = browserExec; log(`浏览器：${browserExec}`); }
  else log('浏览器：用 playwright 自带 chromium（首次需 npx playwright install chromium）');

  log(`项目：${projectDir}`);
  log(`封面时刻：${args.at === 'last' || args.at == null ? '时间轴末尾（完整态）' : `绝对 ${args.at}s`}`);
  log(`输出倍率：${args.scale || 2}x（deviceScaleFactor）· ${args.jpg ? 'JPEG' : 'PNG'}`);

  const browser = await chromium.launch(launchOpts);
  const results = [], errors = [];
  for (const spec of specs) {
    try {
      const r = await renderOne(browser, projectDir, spec, args);
      if (r.skipped) log(`– 跳过 ${spec.label}：${r.skipped}`);
      else { results.push(r); log(`✓ ${spec.label}  ${spec.width}×${spec.height}  →  ${r.outPath}  (${r.detail})`); }
    } catch (e) {
      errors.push(`${spec.label}: ${e.message}`);
    }
  }
  await browser.close();

  if (errors.length) die(`封面渲染失败：\n  ${errors.join('\n  ')}`);

  // ---------- 自检：各画幅的构图禁区 ----------
  // 3:4 / 9:16 版本会被平台再裁，最要命的是「大字钩子贴边」——
  // 这里只报尺寸与体积，几何禁区靠 out/cover_report.md 的人工清单（见 references/cover-guide.md）。
  const lines = [`# 封面自检 · ${pj.slug || 'video'}`, ''];
  for (const r of results) {
    const st = fs.statSync(r.outPath);
    lines.push(`- **${r.spec.label}** \`${path.basename(r.outPath)}\` ${r.spec.width}×${r.spec.height} · ${(st.size / 1024).toFixed(0)}KB · ${r.spec.note}`);
  }
  lines.push('', '> 各份封面共享同一视觉基因、各自独立排版（不是裁切关系）。',
    '> 上传前核对：① 大字钩子距边 ≥96px（3:4 ≥110px；9:16 左右 ≥90px、且上边 ≥180px / 下边 ≥160px 让开平台 UI 层）',
    '> ② 钩子在任何画幅下都不被切 ③ 16:9 版主体偏左/右留出信息流裁切余量',
    '> ④ 封面文字与视频首帧钩子一致（观众预期） ⑤ 9:16 版的横排多列要改竖排堆叠（窄画幅放不下两栏）');
  const repPath = path.join(projectDir, 'out', 'cover_report.md');
  fs.writeFileSync(repPath, lines.join('\n'), 'utf-8');
  log(`✓ 自检：${repPath}`);
  log(`★ 提醒：3:4 / 9:16 都是独立排版，上传时按画幅各选一次；` +
      `若平台只允许一张、且主页栅格按 3:4 裁，用 3:4 版（16:9 会被切两侧）；` +
      `竖版视频/全屏场景用 9:16 版。`);
}

main().catch(e => die(e.stack || String(e)));
