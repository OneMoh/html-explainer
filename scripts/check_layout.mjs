#!/usr/bin/env node
/**
 * check_layout.mjs —— 终态几何体检：越界 / 侵入字幕禁区 / 元素互相遮挡。
 *
 * 为什么需要它：`lint_frames.py` 是**静态文本**检查（禁色值字面量、禁 transition、
 * 中文字体族…），它完全看不见几何。而画面里最常见的两类「静默出错」恰恰是几何问题，
 * 且两者都不报错、lint 全绿、渲完几千帧才被人眼发现：
 *   ① **遮挡** —— 图表轴标签被底部证据条压住、两段文字打架（issue #1 的症状之一）
 *   ② **越界** —— 内容溢出画布、压进字幕带
 * 这个脚本把「终态帧里谁和谁重叠、谁越界」变成可枚举的清单。
 *
 * ★ 判据是**终态**，不是中途帧。入场动画跑到一半时元素本来就在半路，
 *   拿中途帧判「对齐/遮挡」必然误判（见 frame_at.py 同款说明）。
 *
 * 用法：
 *   node scripts/check_layout.mjs <项目目录>
 *   node scripts/check_layout.mjs . --only 20_shape,22_holiday
 *   node scripts/check_layout.mjs . --json          # 机读输出到 out/layout.json
 *   node scripts/check_layout.mjs . --ignore "my-wide-band"
 * 退出码：有 ERROR → 1（可直接挂进流水线）
 *
 * 产出：out/layout_report.md（人读）+ out/layout.json（机读）
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 本脚本既可能被从技能目录直接调用，也可能被脚本自己复制进项目 script/ 下，
// 因此不能靠相对路径找技能根。解析顺序：env → 向上逐级 → 各智能体技能目录。
const SKILL_SUBDIRS = [
  ['.workbuddy', 'skills'],   // WorkBuddy
  ['.claude', 'skills'],      // Claude Code
  ['.codex', 'skills'],       // OpenAI Codex
  ['.gemini', 'skills'],      // Gemini CLI
  ['.cursor', 'skills'],      // Cursor
  ['.agents', 'skills'],      // 通用约定
];
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
  const homes = [process.env.USERPROFILE, process.env.HOME].filter(Boolean);
  for (const home of homes) {
    for (const seg of SKILL_SUBDIRS) cands.push(path.join(home, ...seg, 'html-explainer'));
  }
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

const log = (m) => process.stderr.write(`[layout] ${m}\n`);
const die = (m) => { process.stderr.write(`[layout] ✗ ${m}\n`); process.exit(2); };

function parseArgs(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--only') a.only = String(argv[++i]).split(',').map((s) => s.trim()).filter(Boolean);
    else if (t === '--ignore') a.ignore = String(argv[++i]).split(',').map((s) => s.trim()).filter(Boolean);
    else if (t === '--safe-bottom') a.safeBottom = parseFloat(argv[++i]);
    else if (t === '--safe-side') a.safeSide = parseFloat(argv[++i]);
    else if (t === '--json') a.json = true;
    else if (t === '--strict') a.strict = true;
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

// ★ 真函数字面量（传字符串只会被求值不执行 → 每帧静止且零报错）
const seekEnd = async () => {
  const tl = window.__tl || (window.__timelines && Object.values(window.__timelines)[0]) || null;
  let dur = 0;
  if (tl && typeof tl.duration === 'function') {
    dur = tl.duration() || 0;
    tl.pause(0, false);
    tl.pause(dur, false);          // ← 第二参必须 false
  }
  if (document.getAnimations) {
    document.getAnimations().forEach((a) => {
      try {
        const t = Number.isFinite(a.effect && a.effect.getTiming ? a.effect.getTiming().duration : NaN)
          ? null : null;
        a.pause();
        // 循环关键帧（呼吸光等）拖到很后面，让它落在稳定相位
        a.currentTime = Math.round((dur * 1000) + 1000 * 60 * 5) || 0;
        void t;
      } catch (e) { /* ignore */ }
    });
  }
  await new Promise((r) => { requestAnimationFrame(() => { requestAnimationFrame(r); }); });
  return dur;
};

/**
 * 页面内几何审计。返回 { items, findings, skipped }。
 * 判定分三级：ERROR（一定是 bug）· WARN（可疑，多半是 bug）· INFO（算术提示，供人判断）
 */
const audit = (o) => {
  const W = o.W, H = o.H;
  const SAFE_BOTTOM = o.safeBottom;     // 硬底线：内容底边必须 ≥ 这里
  const SAFE_SIDE = o.safeSide;         // 左右安全边（含卡片外边距）
  const IGNORE = (o.ignore || []).map((s) => s.toLowerCase());
  const STRICT = !!o.strict;
  const TOL = 2;

  // 装饰层白名单：整幅幕底／网格／柔光／幽灵大字，它们本来就满屏或该被文字压住
  const DECO_TOKENS = new Set([
    'bg', 'grid', 'paperbg', 'stage', 'vignette', 'noise', 'grain', 'glow', 'halo', 'aura',
    'anchor', 'ghost', 'watermark', 'wm', 'no', 'scan', 'beam', 'streak', 'dust',
  ]);
  const DECO_MAX_OPACITY = 0.16;   // 透明度低于此值视为装饰（幽灵大字/柔光）

  const tokens = (el) => String(el.className && el.className.baseVal !== undefined
    ? el.className.baseVal : (el.className || ''))
    .split(/[\s_-]+/).filter(Boolean).map((s) => s.toLowerCase());

  const isDeco = (el) => tokens(el).some((t) => DECO_TOKENS.has(t))
    || IGNORE.some((ig) => (el.getAttribute('class') || '').toLowerCase().includes(ig));

  const effOpacity = (el) => {
    let op = 1, cur = el;
    while (cur && cur.nodeType === 1) {
      const v = parseFloat(getComputedStyle(cur).opacity);
      if (Number.isFinite(v)) op *= v;
      cur = cur.parentElement;
    }
    return op;
  };

  const colorAlpha = (c) => {
    const m = String(c || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return 1;
    const p = m[1].split(',').map((s) => parseFloat(s));
    return p.length >= 4 ? p[3] : 1;
  };
  const hasBg = (cs) => {
    const b = cs.backgroundColor || '';
    if (!b || b === 'transparent' || b === 'rgba(0, 0, 0, 0)') return false;
    return colorAlpha(b) >= 0.08;
  };
  const hasBorder = (cs) => {
    for (const s of ['Top', 'Right', 'Bottom', 'Left']) {
      const w = parseFloat(cs['border' + s + 'Width']) || 0;
      if (w <= 0 || cs['border' + s + 'Style'] === 'none') continue;
      if (colorAlpha(cs['border' + s + 'Color']) < 0.08) continue;
      return true;
    }
    return false;
  };

  const SVGNS = 'http://www.w3.org/2000/svg';
  const INLINEISH = new Set(['SPAN', 'B', 'EM', 'I', 'SMALL', 'STRONG', 'U', 'BR', 'SUB', 'SUP', 'MARK', 'TIME']);

  // 「文本叶」：整棵子树里的元素后代全是行内标签 → 渲染上就是一块文本。
  // ★ 文本可能全在 <span> 里（`<div class="axis"><span>700nm</span><span>450nm</span></div>`），
  //   所以「有没有自己的直接文本节点」不能作为判据 —— 第一版就是这么漏掉 issue #1 的遮挡的。
  const ownTextOf = (el) => {
    const out = [];
    for (const n of el.childNodes) {
      if (n.nodeType === 3) out.push(n.nodeValue);
      else if (n.nodeType === 1 && n.namespaceURI === SVGNS
               && ['tspan', 'text'].includes(n.tagName.toLowerCase())) out.push(n.textContent);
    }
    return out.join('').replace(/\s+/g, ' ').trim();
  };
  const paintOf = (el) => hasBg(getComputedStyle(el)) || hasBorder(getComputedStyle(el))
    || ['IMG', 'CANVAS', 'VIDEO'].includes(el.tagName);
  const isTextLeaf = (el) => {
    if (el.namespaceURI === SVGNS) {
      const t = el.tagName.toLowerCase();
      return (t === 'text' || t === 'tspan') && el.textContent.replace(/\s+/g, ' ').trim().length > 0;
    }
    if (!el.textContent || !el.textContent.replace(/\s+/g, ' ').trim()) return false;
    for (const d of el.querySelectorAll('*')) {
      if (d.namespaceURI === SVGNS && d.tagName.toLowerCase() === 'svg') return false;
      if (!INLINEISH.has(d.tagName)) return false;
      if (paintOf(d)) return false;          // 里面有带底色的小胶囊 → 那是块，不是纯文本
    }
    // 自己有直接文本 = 纯文本块；全靠行内子元素 = 也当文本块，但只在自己**没**底色时
    return ownTextOf(el).length > 0 || !paintOf(el);
  };

  // ★ 量**字墨范围**，不量元素框。块级文本元素的 rect 是整块宽度（左对齐的 96px 大标题
  //   元素宽 1800，字形只占左边 600），拿元素框算重叠会把「印章贴在标题右侧空白处」
  //   误报成「印章压住了标题」。Range 的 client rects 是逐行、贴合字形的 ——
  //   浏览器划词高亮用的就是这套，与肉眼看到的一致。
  // ★ 纵向还要再收一次：Range 给的是**行盒**，行盒 = 字体 em 盒 + 上下留白。
  //   大字号紧排时（标题 180px / line-height 1.18），上一行的行盒底会与下一行的行盒顶
  //   擦边十几像素 —— 肉眼毫无重叠，工具却报「文字重叠」。字体在行盒里是垂直居中的，
  //   所以把每行的纵向范围收成 `中心 ± em/2`，这才是字形真正占的地方。
  const inkRect = (el) => {
    if (el.namespaceURI === SVGNS) return null;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, hit = false;
    const w = document.createTreeWalker(el, 4 /* SHOW_TEXT */, null);
    let n;
    while ((n = w.nextNode())) {
      if (!n.nodeValue || !n.nodeValue.replace(/\s+/g, '')) continue;
      const rg = document.createRange();
      rg.selectNodeContents(n);
      const fs = parseFloat(getComputedStyle(n.parentElement || el).fontSize) || 0;
      for (const cr of rg.getClientRects()) {
        if (cr.width < 0.5 || cr.height < 0.5) continue;
        hit = true;
        const cy = (cr.top + cr.bottom) / 2;
        const half = fs > 0 ? Math.min(fs, cr.height) / 2 : cr.height / 2;
        x0 = Math.min(x0, cr.left); y0 = Math.min(y0, cy - half);
        x1 = Math.max(x1, cr.right); y1 = Math.max(y1, cy + half);
      }
    }
    return hit ? { l: x0, t: y0, rr: x1, b: y1 } : null;
  };
  const items = [];
  const skipped = [];
  for (const el of document.body.querySelectorAll('*')) {
    const tag = el.tagName.toUpperCase();
    if (['SCRIPT', 'STYLE', 'LINK', 'META', 'TITLE', 'HEAD', 'BR', 'TEMPLATE'].includes(tag)) continue;
    if (el.closest && !el.closest('body')) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (r.right < 0 || r.bottom < 0 || r.left > W || r.top > H) continue;

    const texty = isTextLeaf(el);
    const svgRoot = el.namespaceURI === SVGNS && tag === 'SVG';
    const painted = hasBg(cs) || hasBorder(cs) || ['IMG', 'CANVAS', 'VIDEO'].includes(tag);
    if (!texty && !svgRoot && !painted) continue;

    const cls = el.getAttribute('class') || '';
    if (isDeco(el) && !STRICT) { skipped.push({ id: label(el), why: '装饰层（类名白名单）' }); continue; }
    if (effOpacity(el) < DECO_MAX_OPACITY) { skipped.push({ id: label(el), why: '有效透明度 < 0.16' }); continue; }

    const box = { l: r.left, t: r.top, rr: r.right, b: r.bottom };
    // 带底色的元素用**元素框**（它靠底色遮挡）；纯文本用**字墨**（它只占字形）。
    const ink = texty && !painted ? inkRect(el) : null;
    items.push({
      el, tag, cls, texty, svgRoot, painted, r: box,
      m: ink || box,                       // m = 参与判定的矩形（文本用字墨，块用元素框）
      id: label(el),
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40),
    });
  }
  // 文本叶只留**最外层**：`<div class="axis"><span>A</span><span>B</span></div>` 会同时
  // 采到 .axis 和两个 span，同一次遮挡被报三遍。留最外层 = 一条问题一条记录。
  const textSet = new Set(items.filter((i) => i.texty).map((i) => i.el));
  const kept = items.filter((i) => {
    if (!i.texty) return true;
    for (let p = i.el.parentElement; p; p = p.parentElement) if (textSet.has(p)) return false;
    return true;
  });
  items.length = 0;
  items.push(...kept);
  function label(el) {
    const c = el.getAttribute('class') || '';
    return (c ? '.' + c.split(/\s+/).slice(0, 2).join('.') : '') + '|' + el.tagName.toLowerCase();
  }

  const findings = [];
  const add = (level, kind, msg, a, b) => findings.push({
    level, kind, msg,
    a: a ? side(a) : null,
    b: b ? side(b) : null,
  });
  function side(it) {
    const o = { id: it.id, rect: rectStr(it.m) };
    const d = Math.max(Math.abs(it.r.l - it.m.l), Math.abs(it.r.t - it.m.t),
                       Math.abs(it.r.rr - it.m.rr), Math.abs(it.r.b - it.m.b));
    if (d > 2) o.box = rectStr(it.r) + '（元素框；判定用的是字墨范围）';
    return o;
  }
  function rectStr(r) {
    return `x ${Math.round(r.l)}→${Math.round(r.rr)} / y ${Math.round(r.t)}→${Math.round(r.b)}`;
  }

  // ── A. 越界 / 侵入字幕禁区 ──────────────────────────────────
  const SAFE_LINE = H - SAFE_BOTTOM;
  for (const it of items) {
    const r = it.m;
    if (r.b > H + TOL || r.rr > W + TOL || r.l < -TOL || r.t < -TOL) {
      add('ERROR', '出画', `${it.id} 越出画布（${rectStr(r)}）`, it);
      continue;
    }
    if (r.b > SAFE_LINE + TOL) {
      add('ERROR', '侵入字幕禁区',
        `${it.id} 底边 y=${Math.round(r.b)} 低于安全线 ${SAFE_LINE}（侵入 ${Math.round(r.b - SAFE_LINE)}px）${it.text ? ' — 「' + it.text + '」' : ''}`, it);
      continue;
    }
    if (r.b > SAFE_LINE - 6) {
      add('INFO', '贴线', `${it.id} 底边 y=${Math.round(r.b)} 距安全线只剩 ${Math.round(SAFE_LINE - r.b)}px`, it);
    }
    if (r.l < SAFE_SIDE - TOL || r.rr > W - SAFE_SIDE + TOL) {
      add('WARN', '越安全边', `${it.id} 距左右边 ${Math.round(Math.min(r.l, W - r.rr))}px < ${SAFE_SIDE}px（${rectStr(r)}）`, it);
    }
  }

  // ── B. 互相遮挡（跳过祖孙关系：卡片里放文字是合法的）──────────
  const inter = (ra, rb) => {
    const w = Math.min(ra.rr, rb.rr) - Math.max(ra.l, rb.l);
    const h = Math.min(ra.b, rb.b) - Math.max(ra.t, rb.t);
    return w > 0 && h > 0 ? w * h : 0;
  };
  const area = (r) => (r.rr - r.l) * (r.b - r.t);
  // 谁的视觉高度更高：z-index 优先，其次 DOM 顺序
  const zOf = (it) => { const z = parseInt(getComputedStyle(it.el).zIndex, 10); return Number.isFinite(z) ? z : 0; };
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      const a = items[i], b = items[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      const ov = inter(a.m, b.m);
      if (ov <= 0) continue;
      const ratioMin = ov / Math.min(area(a.m), area(b.m));
      const bothText = a.texty && b.texty;
      const minArea = bothText ? 200 : 400;
      const minRatio = bothText ? 0.06 : 0.10;
      if (ov < minArea || ratioMin < minRatio) continue;
      const pct0 = Math.round(ratioMin * 100);
      // 「盖住百分之多少」要相对**文字自己的面积**算 —— 相对一条 6px 细线算会得到
      // 无意义的 100%（细线本来就只有那么高），而那些数字是给人判断用的。
      const pctText = (t) => Math.round(100 * ov / Math.max(1, area(t.m)));
      // 谁盖住谁：z-index 优先，其次 DOM 顺序
      const above = (x, y) => zOf(x) + (x.el.compareDocumentPosition(y.el) & 2 ? 0.5 : 0);
      // 文字 vs 文字（含「带底色的文字条」）：一律是问题，但要分清是不是被实心块盖住
      if (bothText) {
        const solid = a.painted ? a : (b.painted ? b : null);
        if (solid) {
          const other = solid === a ? b : a;
          if (above(solid, other) >= above(other, solid)) {
            add('ERROR', '文字被遮挡',
              `${other.id}「${other.text}」被 ${solid.id} 盖住 ${pctText(other)}%（按文字自身面积算，读不全）`, solid, other);
            continue;
          }
        }
        add('ERROR', '文字重叠',
          `${a.id}「${a.text}」与 ${b.id}「${b.text}」重叠 ${pct0}%（按较小一块算）`, a, b);
        continue;
      }
      // 色块 vs 色块：常常是刻意的（描边套填充、光影、图上的标签）。
      // SVG 的框是「画布」不是「实心块」—— 图元画到 HTML 元素上面是常态，直接跳过。
      if (!a.texty && !b.texty) {
        if (a.svgRoot || b.svgRoot) continue;
        add('WARN', '色块重叠', `${a.id} 与 ${b.id} 重叠 ${pct0}%（确认是刻意的）`, a, b);
        continue;
      }
      // 文字 vs 色块
      const textIt = a.texty ? a : b;
      const blkIt = textIt === a ? b : a;
      if (above(blkIt, textIt) >= above(textIt, blkIt)) {
        add('ERROR', '文字被遮挡',
          `${blkIt.id} 压住了 ${textIt.id}「${textIt.text}」${pctText(textIt)}%（按文字自身面积算，读不全）`, blkIt, textIt);
      } else {
        add('WARN', '文字压色块',
          `${textIt.id}「${textIt.text}」压在 ${blkIt.id} 上 ${pctText(textIt)}%（确认是刻意的）`, textIt, blkIt);
      }
      continue;
      continue;
    }
  }

  // ── C. SVG 画的东西在不在它自己的框中央 ─────────────────────
  const svgInfo = [];
  for (const it of items) {
    if (!it.svgRoot) continue;
    try {
      const svg = it.el;
      const bb = svg.getBBox();
      const ctm = svg.getScreenCTM();
      const cor = (x, y) => ({
        x: ctm.a * x + ctm.c * y + ctm.e,
        y: ctm.b * x + ctm.d * y + ctm.f,
      });
      const p1 = cor(bb.x, bb.y), p2 = cor(bb.x + bb.width, bb.y + bb.height);
      const cx = (p1.x + p2.x) / 2, cy = (p1.y + p2.y) / 2;
      const boxCx = (it.r.l + it.r.rr) / 2, boxCy = (it.r.t + it.r.b) / 2;
      const dx = cx - boxCx, dy = cy - boxCy;
      svgInfo.push({ id: it.id, contentCx: Math.round(cx), contentCy: Math.round(cy),
                     boxCx: Math.round(boxCx), boxCy: Math.round(boxCy),
                     dx: Math.round(dx), dy: Math.round(dy) });
      if (Math.hypot(dx, dy) > 24) {
        add('WARN', 'SVG 内容偏心',
          `${it.id} 画的内容中心 (${Math.round(cx)},${Math.round(cy)}) 与自身框中心 ` +
          `(${Math.round(boxCx)},${Math.round(boxCy)}) 差 ${Math.round(Math.hypot(dx, dy))}px ` +
          `（dx ${Math.round(dx)} / dy ${Math.round(dy)}）—— viewBox 与元素框比例不一致，` +
          `或图形本身没画在 viewBox 中心`, it);
      }
    } catch (e) { /* ignore */ }
  }

  // ── D. 疑似「该跟图形对齐却差了」的 HTML 部件（issue #1 那类错位）──
  // 判据刻意收得很窄，宁可漏也不误报 —— 报告里全是噪声，人就不看了：
  //   基准只认 **SVG 内容中心**（不认幕布中心：网格/列表里的点离幕布中心几十上百像素
  //   是常态，拿它当基准等于每帧都报）；候选件要小（≤160px，是「点/标记」不是卡片）；
  //   偏差 4–200px；**同一类名在一帧里命中 ≥3 次就整组丢弃**（那是网格/日历/刻度，
  //   不是「一个该居中的部件」）。
  const hitByClass = new Map();
  for (const it of items) {
    if (it.texty || it.svgRoot) continue;
    const w = it.r.rr - it.r.l, h = it.r.b - it.r.t;
    if (w > 160 || h > 160) continue;
    const cx = (it.r.l + it.r.rr) / 2, cy = (it.r.t + it.r.b) / 2;
    let best = null;
    for (const s of svgInfo) {
      const d = Math.hypot(cx - s.contentCx, cy - s.contentCy);
      if (!best || d < best.d) best = { d, an: s.id + ' 的内容中心' };
    }
    if (!best || best.d <= 4 || best.d > 200) continue;
    const key = it.cls || it.tag;
    const rec = hitByClass.get(key) || { n: 0, rows: [] };
    rec.n++;
    rec.rows.push({ it, d: best.d, an: best.an, cx, cy, w, h });
    hitByClass.set(key, rec);
  }
  for (const [key, rec] of hitByClass) {
    if (rec.n >= 3) {
      add('INFO', '疑似未对齐（整组忽略）',
        `${key} 在一帧里命中 ${rec.n} 次 —— 按网格/列表处理，不作为错位报出`, null);
      continue;
    }
    for (const r of rec.rows) {
      add('INFO', '疑似未对齐',
        `${r.it.id}（${Math.round(r.w)}×${Math.round(r.h)}）中心 (${Math.round(r.cx)},${Math.round(r.cy)}) ` +
        `距「${r.an}」${Math.round(r.d)}px —— 若本意是对齐，这就是 issue #1 那类错位`, r.it);
    }
  }

  return { items: items.map((i) => ({ id: i.id, rect: rectStr(i.r), text: i.text })),
           findings, skipped, svgInfo, safeLine: SAFE_LINE };
};

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectDir = path.resolve(args._[0] || '.');
  const pj = JSON.parse(fs.readFileSync(path.join(projectDir, 'project.json'), 'utf8'));
  const W = pj.width || 1920, H = pj.height || 1080;
  const safeBottom = args.safeBottom || 170;
  const safeSide = args.safeSide || 64;

  const framesDir = path.join(projectDir, 'frames');
  let ids = (pj.order || []).filter((id) => fs.existsSync(path.join(framesDir, `${id}.html`)));
  if (args.only) ids = ids.filter((id) => args.only.includes(id));
  if (!ids.length) die('没有可检查的帧（检查 project.json 的 order 与 frames/*.html）');

  let chromium;
  try { ({ chromium } = require('playwright-core')); }
  catch { die('playwright-core 缺失：技能目录 node/ 下 npm install playwright-core'); }

  const launchOpts = {};
  const be = resolveBrowserExec();
  if (be) launchOpts.executablePath = be;

  const browser = await chromium.launch(launchOpts);
  const report = [];
  for (const id of ids) {
    const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    try {
      await page.addInitScript('window.__MG_RENDER__ = true;');
      await page.goto(pathToFileURL(path.join(framesDir, `${id}.html`)).href, { waitUntil: 'domcontentloaded' });
      await page.evaluate(FONT_WAIT);
      const dur = await page.evaluate(seekEnd);
      const r = await page.evaluate(audit, { W, H, safeBottom, safeSide, ignore: args.ignore || [], strict: !!args.strict });
      r.id = id; r.duration = dur;
      report.push(r);
      const errs = r.findings.filter((f) => f.level === 'ERROR').length;
      const warns = r.findings.filter((f) => f.level === 'WARN').length;
      log(`${errs ? '✗' : (warns ? '!' : '✓')} ${id.padEnd(16)} 元素 ${String(r.items.length).padStart(3)} · ERROR ${errs} · WARN ${warns}`);
    } catch (e) {
      log(`✗ ${id}: ${e.message}`);
      report.push({ id, error: e.message, findings: [], items: [], skipped: [], svgInfo: [] });
    } finally {
      await page.close();
    }
  }
  await browser.close();

  // ── 报告 ───────────────────────────────────────────────────
  const total = { ERROR: 0, WARN: 0, INFO: 0 };
  for (const r of report) for (const f of (r.findings || [])) total[f.level]++;

  const lines = [`# 几何体检 · ${path.basename(projectDir)}`, '',
    `画布 ${W}×${H} · 安全线：内容底边 ≤ **y ${H - safeBottom}**（字幕带禁区上方）· 左右安全边 ±${safeSide}px`,
    '', `帧数 ${report.length} · **ERROR ${total.ERROR} · WARN ${total.WARN} · INFO ${total.INFO}**`, ''];

  for (const lv of ['ERROR', 'WARN', 'INFO']) {
    const rows = [];
    for (const r of report) for (const f of (r.findings || [])) if (f.level === lv) rows.push([r.id, f]);
    if (!rows.length) continue;
    lines.push(`## ${lv}（${rows.length}）`, '');
    for (const [id, f] of rows) {
      lines.push(`- \`${id}\` **${f.kind}** — ${f.msg}`);
      if (f.a) lines.push(`  - A：\`${f.a.id}\` ${f.a.rect}`);
      if (f.b) lines.push(`  - B：\`${f.b.id}\` ${f.b.rect}`);
    }
    lines.push('');
  }
  const clean = report.filter((r) => !r.error && !(r.findings || []).some((f) => f.level === 'ERROR'));
  lines.push(`## 无 ERROR 的帧（${clean.length}/${report.length}）`, '',
    clean.length ? clean.map((r) => '`' + r.id + '`').join(' · ') : '（无）', '');

  const outDir = path.join(projectDir, 'out');
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'layout_report.md'), lines.join('\n'), 'utf8');
  if (args.json) {
    fs.writeFileSync(path.join(outDir, 'layout.json'), JSON.stringify(report, null, 2), 'utf8');
  }
  log(`ERROR ${total.ERROR} · WARN ${total.WARN} · INFO ${total.INFO} → out/layout_report.md`);
  if (total.ERROR) log('★ ERROR 是「一定是 bug」级别：对照 messages 里的 rect 改 frames/<id>.html 后重跑');
  process.exit(total.ERROR ? 1 : 0);
}

main().catch((e) => die(e.stack || String(e)));
