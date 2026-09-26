#!/usr/bin/env node
/**
 * check_cover.mjs —— 封面终态几何实测（三画幅通用）
 *
 * 为什么需要它：`cover-guide.md` 的自检清单要求「钩子字号 / 边距 / 每行字数 /
 * 是否左右两栏」逐条过，但这些都是**渲染后才知道的量**。肉眼看得出的只有明显问题，
 * 差 20px 的贴边、多出一个字的孤行，肉眼经常放过。这个脚本用真实浏览器把
 * 终态几何量出来，一次判完。
 *
 * 用法：
 *   node <skill>/scripts/check_cover.mjs <项目>              # 量全部存在的封面
 *   node <skill>/scripts/check_cover.mjs <项目> --only 916   # 只量 1080×1920
 *   node <skill>/scripts/check_cover.mjs <项目> --json       # 机器可读
 *
 * 判据（与 references/cover-guide.md 一致）：
 *   · 画布四边安全边距：16:9 ≥96px、3:4 ≥110px、9:16 左右 ≥90px
 *   · 9:16 特例：上边 ≥180px、下边 ≥160px（平台 UI 层，不是可裁区）
 *   · 钩子字号：16:9 ≥96px、3:4 ≥120px、9:16 ≥130px
 *   · 钩子必须是画面最大字号（否则视觉焦点不在钩子上）
 *   · 钩子每行字数上限：16:9 ≤7、3:4 ≤5、9:16 ≤6（防孤字断行 / 放不下）
 *   · 9:16 禁止左右两栏（量「同一水平带内是否出现并排放置的块级元素」）
 *   · 无元素越出画布
 *
 * 退出码：0 = 全 PASS；1 = 有 FAIL（可进 CI / 流水线门禁）
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, '..');
const require = createRequire(path.join(SKILL_ROOT, 'node', 'package.json'));

const log = (m) => process.stderr.write(`[cover-check] ${m}\n`);
const die = (m) => { process.stderr.write(`[cover-check] ✗ ${m}\n`); process.exit(1); };

// ---------- 规格（与 cover_build.mjs 的 SPECS 对齐） ----------
const SPECS = {
  '169': {
    key: '169', file: 'cover_169.html', width: 1920, height: 1080,
    label: '16:9 · 抖音主封面',
    margin: 96,              // 四边统一
    marginTop: 96, marginBottom: 96, marginX: 96,
    hookMin: 96, hookMaxChars: 8,   // 钩子容器 1060px ÷ (130px×0.97) ≈ 8.4
    noColumns: false,
  },
  '34': {
    key: '34', file: 'cover_34.html', width: 1440, height: 1080,
    label: '3:4 · 主页栅格兼容',
    margin: 110,
    marginTop: 110, marginBottom: 110, marginX: 110,
    hookMin: 120, hookMaxChars: 8,  // 钩子容器 1220px ÷ (130px×0.97) ≈ 9.7
    noColumns: false,
  },
  '916': {
    key: '916', file: 'cover_916.html', width: 1080, height: 1920,
    label: '9:16 · 竖版全屏',
    margin: 90,
    marginTop: 180, marginBottom: 160, marginX: 90,   // ★ 上下是平台 UI 层，不是可裁区
    hookMin: 130, hookMaxChars: 6,  // 钩子容器 900px ÷ (150px×0.97) ≈ 6.2
    noColumns: true,                                  // ★ 窄画幅禁止左右两栏
  },
};

function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--only') a.only = argv[++i];
    else if (t === '--json') a.json = true;
    else if (t === '--browser') a.browser = argv[++i];
    else if (t === '--shot') a.shot = true;           // 顺手出一张 1x 预览图
    else a._.push(t);
  }
  return a;
}

function resolveBrowserExec() {
  const isWin = process.platform === 'win32';
  const cands = isWin ? [
    path.join(process.env['PROGRAMFILES'] || 'C:/Program Files', 'Google/Chrome/Application/chrome.exe'),
    path.join(process.env['PROGRAMFILES(X86)'] || 'C:/Program Files (x86)', 'Google/Chrome/Application/chrome.exe'),
    path.join(process.env['PROGRAMFILES(X86)'] || 'C:/Program Files (x86)', 'Microsoft/Edge/Application/msedge.exe'),
    path.join(process.env['PROGRAMFILES'] || 'C:/Program Files', 'Microsoft/Edge/Application/msedge.exe'),
  ] : [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge',
  ];
  return cands.find(p => { try { return fs.existsSync(p); } catch { return false; } }) || null;
}

// 在页面里量：所有"可见内容块"的包围盒 + 钩子行切分
const PAGE_PROBE = `(() => {
  const W = document.documentElement.clientWidth, H = document.documentElement.clientHeight;
  const vis = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
    const b = el.getBoundingClientRect();
    return b.width > 0.5 && b.height > 0.5;
  };
  const rnd = (n) => Math.round(n);

  // ── 1) 找钩子：在"句子级"文本元素里取字号最大的（排掉 6.02 / 4 这类纯数字）──
  //     判据与判"钩子是否最大"必须分开，否则「钩子最大」永远自证成立。
  let hookEl = null, hookFs = 0, maxFsAny = 0;
  const norm = (s) => (s || '').replace(/\s+/g, '');
  for (const el of document.querySelectorAll('div, span, p, h1, h2')) {
    if (!vis(el)) continue;
    const own = Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('');
    if (!norm(own)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize) || 0;
    if (fs > maxFsAny) maxFsAny = fs;
    // 句子级：自身文本 ≥6 个"字位"（CJK 记 1，拉丁/数字记 0.55），且不是纯数字串
    const t = norm(own);
    const wide = (t.match(/[\u3400-\u9FFF\uF900-\uFAFF\u3000-\u303F\uFF00-\uFFEF]/g) || []).length;
    const narrow = t.length - wide;
    const weight = wide + narrow * 0.55;
    const pureNumber = /^[\d.,%$¥+\-–—:：]+$/.test(t);
    if (weight < 6 || pureNumber) continue;
    if (fs > hookFs) { hookFs = fs; hookEl = el; }
  }

  // ── 2) 钩子按视觉行切分（Range client rects 的 top 分桶） ──
  const lines = [];
  if (hookEl) {
    const rg = document.createRange();
    rg.selectNodeContents(hookEl);
    const rects = Array.from(rg.getClientRects())
      .filter(r => r.width > 1 && r.height > 1)
      .sort((a, b) => a.top - b.top || a.left - b.left);
    for (const r of rects) {
      const row = lines.find(L => Math.abs(L.top - r.top) < r.height * 0.55);
      if (row) { row.left = Math.min(row.left, r.left); row.right = Math.max(row.right, r.right); row.chars += 1; }
      else lines.push({ top: r.top, left: r.left, right: r.right, chars: 1 });
    }
  }

  // ── 3) 全画布内容包围盒（用于四边边距与越界）──
  let box = null;
  const offenders = [];
  for (const el of document.body.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed' || el.classList.contains('bg') || el.classList.contains('grain')) continue;
    if (!vis(el)) continue;
    const b = el.getBoundingClientRect();
    if (b.width < 1 || b.height < 1) continue;
    // 只统计"有自己文字/边框/背景"的叶子块，避免父容器把边距吃光
    const hasOwnText = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    const hasPaint = cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.borderTopWidth !== '0px';
    if (!hasOwnText && !hasPaint) continue;
    if (!box) box = { l: b.left, t: b.top, r: b.right, b: b.bottom };
    else { box.l = Math.min(box.l, b.left); box.t = Math.min(box.t, b.top); box.r = Math.max(box.r, b.right); box.b = Math.max(box.b, b.bottom); }
    if (b.left < -1 || b.top < -1 || b.right > W + 1 || b.bottom > H + 1) {
      const nm = el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : el.tagName.toLowerCase();
      if (offenders.length < 6) offenders.push(nm + ' x' + rnd(b.left) + '→' + rnd(b.right) + ' y' + rnd(b.top) + '→' + rnd(b.bottom));
    }
  }

  // ── 4) 左右两栏探测：同一水平带内是否有两组块级内容左右分离 ──
  //     找 top 重叠 >60% 且水平间隙 > 画布宽 8% 的一对叶子块
  const leaves = [];
  for (const el of document.body.querySelectorAll('div, p, h1, h2, span')) {
    const cs = getComputedStyle(el);
    if (!vis(el)) continue;
    if (el.classList.contains('bg') || el.classList.contains('grain')) continue;
    const hasOwnText = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    if (!hasOwnText) continue;
    const b = el.getBoundingClientRect();
    leaves.push({ b, nm: el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/)[0] : el.tagName.toLowerCase() });
  }
  const pairs = [];
  for (let i = 0; i < leaves.length; i++) {
    for (let j = i + 1; j < leaves.length; j++) {
      const A = leaves[i].b, B = leaves[j].b;
      const ovTop = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
      const minH = Math.min(A.height, B.height);
      if (minH <= 0 || ovTop / minH < 0.6) continue;                 // 必须在同一水平带
      const gap = Math.max(A.left, B.left) - Math.min(A.right, B.right);
      if (gap < W * 0.08) continue;                                   // 必须真的左右分离
      const span = Math.max(A.right, B.right) - Math.min(A.left, B.left);
      if (span < W * 0.72) continue;                                  // 合起来要铺满画布
      pairs.push(leaves[i].nm + ' ↔ ' + leaves[j].nm + ' (间隙 ' + rnd(gap) + 'px, 合宽 ' + rnd(span) + 'px)');
    }
  }

  // ── 5) 比钩子还大的其它元素（纯数字另算）──
  const biggerThanHook = [];
  for (const el of document.body.querySelectorAll('*')) {
    const own = Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('');
    if (!norm(own) || !vis(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize) || 0;
    if (fs <= hookFs + 0.5) continue;
    const t = norm(own);
    const nm = el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/)[0] : el.tagName.toLowerCase();
    biggerThanHook.push({ sel: nm, fontSize: rnd(fs * 10) / 10, pureNumber: /^[\\d.,%$¥+\\-–—:：]+$/.test(t), text: t.slice(0, 12) });
  }
  biggerThanHook.sort((a, b) => b.fontSize - a.fontSize);

  return {
    canvas: { W, H },
    hook: hookEl ? {
      sel: hookEl.className && typeof hookEl.className === 'string' ? '.' + hookEl.className.trim().split(/\\s+/).join('.') : hookEl.tagName.toLowerCase(),
      fontSize: hookFs,
      text: (hookEl.textContent || '').replace(/\\s+/g, ' ').trim(),
      lines: lines.map(L => ({ top: rnd(L.top), left: rnd(L.left), right: rnd(L.right), width: rnd(L.right - L.left), segments: L.chars })),
    } : null,
    box: box ? { l: rnd(box.l), t: rnd(box.t), r: rnd(box.r), b: rnd(box.b) } : null,
    offenders,
    maxFsAny: rnd(maxFsAny * 10) / 10,
    // 比钩子还大的"其它"元素。纯数字（悖论数字）单列 —— 它比钩子大是允许的，
    // 非数字的比钩子大才是"焦点被抢"。
    biggerThanHook: biggerThanHook.slice(0, 5),
    columnPairs: pairs.slice(0, 4),
  };
})()`;

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectDir = path.resolve(args._[0] || '.');
  if (!fs.existsSync(path.join(projectDir, 'frames'))) die(`不是项目目录（没有 frames/）：${projectDir}`);

  let specs;
  if (args.only) {
    specs = String(args.only).split(',').map(s => s.trim()).map(k => {
      if (!SPECS[k]) die(`未知规格 --only ${k}（可用：${Object.keys(SPECS).join(' / ')}）`);
      return SPECS[k];
    });
  } else {
    specs = Object.values(SPECS);
  }
  const present = specs.filter(s => fs.existsSync(path.join(projectDir, 'frames', s.file)));
  if (!present.length) die(`frames/ 下没有封面帧（找 ${specs.map(s => s.file).join(' / ')}）`);

  let chromium;
  try { ({ chromium } = require('playwright-core')); }
  catch { die('playwright-core 缺失：在技能目录 node/ 下 npm install playwright-core'); }

  const browserExec = args.browser || resolveBrowserExec();
  const launchOpts = {};
  if (browserExec) launchOpts.executablePath = browserExec;

  const browser = await chromium.launch(launchOpts);
  const report = [];
  let anyFail = false, anyWarn = false;

  // ★ 必须量「终态」而不是「中间态」（lessons #30）：页内若有 GSAP 时间轴，
  //   先把它 seek 到轴末再量。否则量到的是入场起始值 —— 边距 / 行数 / 字号全错，
  //   而且**看起来像真错误**（本次实测：3:4 版轴长 1.54s，等 0.65s 就量，
  //   钩子还在 opacity:0，脚本把悖论数字 112px 误判成钩子并报「钩子字号不足」）。
  const FREEZE = `(() => {
    const t = window.__tl;
    if (t && typeof t.duration === 'function') {
      try { t.pause(t.duration(), false); return { frozen: true, dur: t.duration() }; }
      catch (e) { return { frozen: false, err: String(e) }; }
    }
    return { frozen: false };
  })()`;

  for (const spec of present) {
    const fileUrl = pathToFileURL(path.join(projectDir, 'frames', spec.file)).href;
    const page = await browser.newPage({ viewport: { width: spec.width, height: spec.height }, deviceScaleFactor: 1 });
    await page.goto(fileUrl);
    await page.waitForTimeout(300);
    const fr = await page.evaluate(FREEZE);
    if (!fr.frozen) await page.waitForTimeout(1600 + 600);   // 无时间轴：等 CSS 动画自然结束
    await page.waitForTimeout(120);
    const m = await page.evaluate(PAGE_PROBE);
    if (args.shot) {
      const shotDir = path.join(projectDir, 'out');
      fs.mkdirSync(shotDir, { recursive: true });
      await page.screenshot({ path: path.join(shotDir, `check_${spec.key}.png`) });
    }
    await page.close();

    const checks = [];
    // level: 'fail' 计入退出码；'warn' 只提示
    const add = (name, ok, detail, level = 'fail') => {
      checks.push({ name, ok, detail, level: ok ? 'ok' : level });
      if (!ok) { if (level === 'fail') anyFail = true; else anyWarn = true; }
    };

    // ① 画布
    add('画布尺寸', m.canvas.W === spec.width && m.canvas.H === spec.height,
      `${m.canvas.W}×${m.canvas.H}（应 ${spec.width}×${spec.height}）`);

    // ② 边距（只在有内容包围盒时判）
    if (m.box) {
      const [ml, mt, mr, mb] = [m.box.l, m.box.t, spec.width - m.box.r, spec.height - m.box.b];
      add(`左边距 ≥${spec.marginX}`, ml >= spec.marginX - 1, `${ml}px`);
      add(`右边距 ≥${spec.marginX}`, mr >= spec.marginX - 1, `${mr}px`);
      add(`上边距 ≥${spec.marginTop}`, mt >= spec.marginTop - 1, `${mt}px${spec.key === '916' ? '（9:16 让开平台顶部信息层）' : ''}`);
      add(`下边距 ≥${spec.marginBottom}`, mb >= spec.marginBottom - 1, `${mb}px${spec.key === '916' ? '（9:16 让开底部标题栏）' : ''}`);
    } else {
      add('内容包围盒', false, '未找到任何可见内容块');
    }

    // ③ 越界
    add('无元素越出画布', m.offenders.length === 0, m.offenders.length ? m.offenders.join(' ; ') : 'OK');

    // ④ 钩子
    if (m.hook) {
      add(`钩子字号 ≥${spec.hookMin}`, m.hook.fontSize >= spec.hookMin - 0.5,
        `${m.hook.fontSize}px  「${m.hook.text}」`);

      // 钩子是否仍是最大焦点：纯数字（悖论数字）比钩子大是允许的 → WARN；文字比钩子大 → FAIL
      const bigger = m.biggerThanHook || [];
      const textBigger = bigger.filter(b => !b.pureNumber);
      const numBigger = bigger.filter(b => b.pureNumber);
      add('钩子是最大的文字', textBigger.length === 0,
        textBigger.length ? textBigger.map(b => `${b.sel} ${b.fontSize}px「${b.text}」`).join(' ; ')
                          : `钩子 ${m.hook.fontSize}px 为最大文字` + (numBigger.length ? `（悖论数字 ${numBigger.map(b => b.fontSize + 'px').join('/')} 更大，允许）` : ''));
      if (numBigger.length) {
        add('悖论数字未压过钩子', numBigger.every(b => b.fontSize <= m.hook.fontSize * 1.35),
          `${numBigger.map(b => b.sel + ' ' + b.fontSize + 'px').join(' ; ')}（上限 钩子×1.35 = ${Math.round(m.hook.fontSize * 1.35)}px）`, 'warn');
      }

      const maxW = spec.width - spec.marginX * 2;
      const over = m.hook.lines.filter(L => L.width > maxW + 1);
      add(`钩子行宽 ≤${maxW}`, over.length === 0,
        over.length ? over.map(L => `${L.width}px`).join(' ; ')
                    : `最大 ${Math.max(...m.hook.lines.map(L => L.width))}px / ${m.hook.lines.length} 行`);

      // 每行字数：参考值，超了只是提醒（硬判据是上面的行宽）
      const em = m.hook.fontSize;
      const est = m.hook.lines.map(L => Math.round(L.width / (em * 0.93)));   // 0.93 ≈ 中文字宽×字距实测系数
      add(`钩子每行 ≲${spec.hookMaxChars} 字`, Math.max(...est) <= spec.hookMaxChars + 1,
        `估 ${est.join(' / ')} 字（本画幅参考上限 ${spec.hookMaxChars}；硬判据是行宽 ≤${maxW}px）`, 'warn');

      const lastLineNarrow = m.hook.lines.length >= 2 &&
        m.hook.lines[m.hook.lines.length - 1].width < m.hook.lines[0].width * 0.42;
      add('末行不是孤字', !lastLineNarrow,
        lastLineNarrow ? `末行仅 ${m.hook.lines[m.hook.lines.length - 1].width}px（首行 ${m.hook.lines[0].width}px）—— 疑似孤字断行` : 'OK');
    } else {
      add('找到钩子', false, '未找到句子级文字元素（自身文本 ≥6 字位）—— 检查钩子是否真的存在');
    }

    // ⑤ 9:16 禁左右两栏
    if (spec.noColumns) {
      add('9:16 无左右两栏', m.columnPairs.length === 0,
        m.columnPairs.length ? m.columnPairs.join(' ; ') : 'OK');
    }

    report.push({ spec, checks, m, frozen: fr });
  }

  await browser.close();

  if (args.json) {
    console.log(JSON.stringify(report.map(r => ({
      spec: r.spec.key, label: r.spec.label, frozen: r.frozen,
      checks: r.checks, hook: r.m.hook, box: r.m.box,
    })), null, 2));
    process.exit(anyFail ? 1 : 0);
  }

  // ---------- 人读报告 ----------
  for (const r of report) {
    const fails = r.checks.filter(c => c.level === 'fail').length;
    const warns = r.checks.filter(c => c.level === 'warn').length;
    const tag = fails ? `✗ ${fails} 项未过${warns ? ` / ${warns} 提醒` : ''}`
                      : (warns ? `✓ 通过（${warns} 项提醒）` : '✓ 全部通过');
    console.log(`\n=== ${r.spec.label}  ${r.spec.width}×${r.spec.height}  ${tag} ===`);
    console.log(`    量测状态：${r.frozen.frozen ? `时间轴已 seek 到轴末 ${r.frozen.dur.toFixed(2)}s（终态）` : '无时间轴，静态'}`);
    for (const c of r.checks) {
      console.log(`  ${c.level === 'ok' ? '✓' : c.level === 'warn' ? '!' : '✗'} ${c.name.padEnd(22)} ${c.detail}`);
    }
    if (r.m.hook) {
      console.log(`  · 钩子 ${r.m.hook.lines.length} 行 / ${r.m.hook.fontSize}px，各行宽：` +
        r.m.hook.lines.map(L => `${L.width}px`).join(' / '));
    }
  }
  console.log(`\n${anyFail ? '✗ 有未通过项 —— 按 references/cover-guide.md 的自检清单修版后重跑'
                            : (anyWarn ? '✓ 通过（提醒项属参考值，肉眼判断即可）' : '✓ 全部通过')}`);
  process.exit(anyFail ? 1 : 0);
}

main().catch(e => die(e.stack || String(e)));
