#!/usr/bin/env node
/**
 * peek_frame.mjs —— 单帧速览（不渲全片，直接给某个场景截图看设计）。
 *
 * 用途：场景构建阶段/修复阶段的「照镜子」工具。全片渲染要跑 5000 帧，
 * 而这里只对指定帧 seek 到几个时点各截一张 —— 秒级出图，先看设计对不对。
 *
 * 用法：
 *   node script/peek_frame.mjs <项目目录> <帧id> [--at 80] [--n 3] [--scale 1]
 *   node script/peek_frame.mjs . hook --at 40,80              # 指定百分比时点
 *   node script/peek_frame.mjs . --all --at 85                # 所有帧都截一张
 *
 * 产出：<项目>/render/peek/<id>@<pct>.png
 *
 * ★ 与 render_video.mjs 同款确定性 seek：__MG_RENDER__ 先置位（帧据此跳过自动起播），
 *   再 tl.pause(t, false) + 同步 CSS 动画 currentTime。**第二参必须是 false**，
 *   否则 onUpdate 类回调被静默抑制（see lessons #27）。
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 本脚本放在**项目**的 script/ 下（不是技能目录里），所以不能靠相对路径找技能根。
// 解析顺序：env → 向上找含 node/playwright-core 的目录 → ~/.workbuddy/skills/html-explainer
function resolveSkillRoot() {
  const cands = [];
  if (process.env.HTML_EXPLAINER_ROOT) cands.push(process.env.HTML_EXPLAINER_ROOT);
  let d = __dirname;
  for (let i = 0; i < 6; i++) {
    cands.push(d);
    const p = path.dirname(d);
    if (p === d) break;
    d = p;
  }
  if (process.env.USERPROFILE) cands.push(path.join(process.env.USERPROFILE, '.workbuddy', 'skills', 'html-explainer'));
  if (process.env.HOME) cands.push(path.join(process.env.HOME, '.workbuddy', 'skills', 'html-explainer'));
  for (const c of cands) {
    try {
      if (fs.existsSync(path.join(c, 'node', 'node_modules', 'playwright-core', 'package.json'))) return c;
    } catch { /* ignore */ }
  }
  return null;
}

const SKILL_ROOT = resolveSkillRoot();
const require = createRequire(SKILL_ROOT
  ? path.join(SKILL_ROOT, 'node', 'package.json')
  : path.join(__dirname, 'package.json'));

const log = (m) => process.stderr.write(`[peek] ${m}\n`);
const die = (m) => { process.stderr.write(`[peek] ✗ ${m}\n`); process.exit(1); };

function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--at') a.at = argv[++i];
    else if (t === '--n') a.n = parseInt(argv[++i], 10);
    else if (t === '--scale') a.scale = parseFloat(argv[++i]);
    else if (t === '--all') a.all = true;
    else if (!t.startsWith('--')) a._.push(t);
  }
  return a;
}

function resolveBrowserExec() {
  if (process.env.BROWSER_PATH && fs.existsSync(process.env.BROWSER_PATH)) return process.env.BROWSER_PATH;
  const cands = process.platform === 'win32' ? [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe'),
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  ] : ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge'];
  for (const p of cands) { try { if (p && fs.existsSync(p)) return p; } catch { /* ignore */ } }
  return null;
}

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

// ★ 真函数字面量（不能传字符串，否则只求值不执行 → 每帧静止且零报错）
const seek = async (o) => {
  const tl = window.__tl || (window.__timelines && Object.values(window.__timelines)[0]) || null;
  const pct = o.pct;
  let seekTo = 0, dur = null;
  if (tl && typeof tl.duration === 'function') {
    dur = tl.duration() || 0;
    seekTo = dur * (pct / 100);
    tl.pause(0, false);
    tl.pause(seekTo, false);       // ← 第二参必须 false
  }
  if (document.getAnimations) {
    document.getAnimations().forEach((a) => {
      try { a.pause(); a.currentTime = Math.round(seekTo * 1000); } catch (e) { /* ignore */ }
    });
  }
  await new Promise((r) => { requestAnimationFrame(() => { requestAnimationFrame(r); }); });
  return { seekTo, dur };
};

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectDir = path.resolve(args._[0] || '.');
  const pj = JSON.parse(fs.readFileSync(path.join(projectDir, 'project.json'), 'utf8'));
  const W = pj.width || 1920, H = pj.height || 1080;

  const framesDir = path.join(projectDir, 'frames');
  let ids = [];
  if (args.all) {
    ids = (pj.order || []).filter((id) => fs.existsSync(path.join(framesDir, `${id}.html`)));
  } else {
    const id = args._[1];
    if (!id) die('用法：node peek_frame.mjs <项目> <帧id> | <项目> --all');
    if (!fs.existsSync(path.join(framesDir, `${id}.html`))) die(`没有 frames/${id}.html`);
    ids = [id];
  }
  if (!ids.length) die('没有可截的帧');

  const pcts = args.at
    ? String(args.at).split(',').map((s) => parseFloat(s)).filter((x) => !Number.isNaN(x))
    : (args.n ? Array.from({ length: args.n }, (_, i) => Math.round(((i + 1) / (args.n + 1)) * 100)) : [85]);

  const outDir = path.join(projectDir, 'render', 'peek');
  fs.mkdirSync(outDir, { recursive: true });

  let chromium;
  try { ({ chromium } = require('playwright-core')); }
  catch { die('playwright-core 缺失：技能目录 node/ 下 npm install playwright-core'); }

  const launchOpts = {};
  const be = resolveBrowserExec();
  if (be) { launchOpts.executablePath = be; log(`浏览器：${be}`); }

  const browser = await chromium.launch(launchOpts);
  let n = 0;
  for (const id of ids) {
    const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: args.scale || 1 });
    try {
      await page.addInitScript(`window.__MG_RENDER__ = true;`);
      await page.goto(pathToFileURL(path.join(framesDir, `${id}.html`)).href, { waitUntil: 'domcontentloaded' });
      await page.evaluate(FONT_WAIT);
      for (const pct of pcts) {
        const r = await page.evaluate(seek, { pct });
        const out = path.join(outDir, `${id}@${String(pct).replace('.', '_')}.png`);
        await page.screenshot({ path: out, type: 'png', scale: 'device' });
        log(`✓ ${id} @${pct}%  seek ${r.seekTo.toFixed(2)}s / 轴长 ${r.dur == null ? '无' : r.dur.toFixed(2)}s  →  ${path.basename(out)}`);
        n++;
      }
    } catch (e) {
      log(`✗ ${id}: ${e.message}`);
    } finally {
      await page.close();
    }
  }
  await browser.close();
  log(`共 ${n} 张 → ${outDir}`);
}

main().catch((e) => die(e.stack || String(e)));
