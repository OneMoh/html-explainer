/* motion.js — html-explainer 动效库（v2.0）
 *
 * 定位：把「镜头语言」变成纯函数。每个 move 都是 t（绝对秒）→ 一组数字
 * （位移 / 缩放 / 透明度 / 半径 / 变换矩阵），你把它写进 el.style.transform
 * 或 ctx.setTransform 都行。库本身**不碰 DOM、不碰 canvas**，无状态、无构建步骤，
 * 因此窗口 can 被逐帧 seek：同样的 t 永远给出同样的数。
 *
 * 契约（渲染器只依赖这三条）：
 *   window.__seek(t)  → 设置 t 时刻的全部样式
 *   window.__ready    → 字体就绪后 measure/simulate，再 seek(0)
 *   window.__meta     = { dur, fps, w, h, inFrame? }
 * 可选：
 *   window.__motion(t0, t1) → px（屏幕最远位移，含镜头）；渲染器据此决定该帧开几次快门
 *
 * 引入方式：
 *   浏览器（file:// 不能用 module）：<script src="../assets/motion.js"></script> → window.HXM
 *   Node（跑自测）：const HXM = require('./motion.js')
 *
 * 设计纪律（每条都是从踩坑里换来的）：
 *   · 慢动作别用 opacity 淡入 —— 用带位移的弹簧「落下」，否则读起来像 PPT（riseWord）。
 *   · 一个 beat 不许「替换」上一个 —— 必须让某个元素跨过边界继续动（rectMorph / irisOpen / camTrack）。
 *   · 快动作必须开快门 —— 超过 80px/帧 不开运动模糊就会重影（render_video.mjs --shutter）。
 *   · 所有随机数都从固定种子出（seededRng），渲染路径上不许出现 Math.random()。
 *
 * 动作词汇（后续小节）：弹簧 / 进出场 / 承接 / 相机 / 蒙版，详见 references/motion-library.md。
 */
(function (root) {
  'use strict';

  /* ══════════════════════════ 标量工具 ══════════════════════════ */
  const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
  const lerp = (a, b, k) => a + (b - a) * k;
  const seg = (t, t0, t1) => (t1 === t0 ? (t >= t1 ? 1 : 0) : clamp((t - t0) / (t1 - t0), 0, 1));
  const sstep = (e0, e1, x) => { const k = clamp((x - e0) / (e1 - e0 || 1e-9), 0, 1); return k * k * (3 - 2 * k); };
  const ssstep = (e0, e1, x) => { const k = clamp((x - e0) / (e1 - e0 || 1e-9), 0, 1); return k * k * k * (k * (k * 6 - 15) + 10); };
  /** 第 i 个元素的错峰起点：stagger(t0, i, 0.055) */
  const stagger = (t0, i, dt) => t0 + i * dt;
  const smooth = (u) => u * u * (3 - 2 * u);
  const smoother = (u) => u * u * u * (u * (u * 6 - 15) + 10);

  /* ══════════════════════════ 曲线 ══════════════════════════
   * t80 = 走完 80% 距离所用的时间占比。它是选曲线的唯一判据：
   *   高（≈.8）= 匀速，读起来像网页过渡；低（≈.2）= 冲出去再收住，读起来像发射镜头。
   * 别到处用同一个 smootherstep —— 那样全片每个动作都是同一条软 S 曲线。
   */
  const powOut = (n) => (u) => 1 - Math.pow(1 - u, n);
  const powInOut = (n) => (u) => (u < 0.5 ? Math.pow(2, n - 1) * Math.pow(u, n) : 1 - Math.pow(-2 * u + 2, n) / 2);
  const EXPO_K = 1 - Math.pow(2, -10);
  const ease = {
    linear: (u) => u,                                            // t80 .80
    smooth,                                                      // t80 .71
    smoother,                                                    // t80 .67
    sineInOut: (u) => -(Math.cos(Math.PI * u) - 1) / 2,
    cubicInOut: powInOut(3),
    quintInOut: powInOut(5),
    quadOut: powOut(2),                                          // t80 .55
    cubicOut: powOut(3),                                         // t80 .42
    quartOut: powOut(4),                                         // t80 .33
    quintOut: powOut(5),                                         // t80 .28
    expoOut: (u) => (u <= 0 ? 0 : u >= 1 ? 1 : (1 - Math.pow(2, -10 * u)) / EXPO_K),   // t80 .23
    expoIn: (u) => (u <= 0 ? 0 : u >= 1 ? 1 : (Math.pow(2, 10 * u) - 1) / 1023),
    expoInOut: (u) => (u < 0.5 ? ease.expoIn(2 * u) / 2 : 1 - ease.expoIn(2 - 2 * u) / 2),
    circOut: (u) => Math.sqrt(1 - Math.pow(1 - clamp(u), 2)),
    backOut: (u) => { const s = 1.70158; return 1 + (s + 1) * Math.pow(u - 1, 3) + s * Math.pow(u - 1, 2); },
    back: (s = 1.70158) => (u) => 1 + (s + 1) * Math.pow(u - 1, 3) + s * Math.pow(u - 1, 2),
  };

  /** CSS cubic-bezier(x1,y1,x2,y2) 的 JS 版 —— 照规范/参考片给的曲线号直接落地 */
  function cubicBezier(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const px = (s) => ((ax * s + bx) * s + cx) * s;
    const py = (s) => ((ay * s + by) * s + cy) * s;
    const dpx = (s) => (3 * ax * s + 2 * bx) * s + cx;
    const solve = (x) => {
      let s = x;
      for (let i = 0; i < 8; i++) {
        const e = px(s) - x;
        if (Math.abs(e) < 1e-7) return s;
        const d = dpx(s);
        if (Math.abs(d) < 1e-6) break;
        s -= e / d;
        if (s < 0 || s > 1) break;
      }
      let lo = 0, hi = 1;
      s = x;
      for (let i = 0; i < 60; i++) { const v = px(s); if (Math.abs(v - x) < 1e-7) return s; if (x > v) lo = s; else hi = s; s = (lo + hi) / 2; }
      return s;
    };
    return (u) => (u <= 0 ? 0 : u >= 1 ? 1 : py(solve(u)));
  }

  const tween = (t, t0, t1, curve = ease.expoOut) => curve(seg(t, t0, t1));

  /** 数值反查：某条曲线走完 frac 距离用了多少时间占比 —— 用来给「曲线选型」定证据 */
  function t80(curve, frac = 0.8, steps = 4000) {
    for (let i = 0; i <= steps; i++) { const u = i / steps; if (curve(u) >= frac) return u; }
    return 1;
  }

  /** 临界/欠阻尼二阶阶跃响应 0→1。zeta<1 过冲（.4 弹 / .8 稳），=1 临界。 */
  function spring(tau, zeta = 0.6, omega = 20) {
    if (tau <= 0) return 0;
    if (zeta < 1) {
      const wd = omega * Math.sqrt(1 - zeta * zeta);
      return 1 - Math.exp(-zeta * omega * tau) * (Math.cos(wd * tau) + (zeta * omega / wd) * Math.sin(wd * tau));
    }
    if (zeta === 1) return 1 - Math.exp(-omega * tau) * (1 + omega * tau);
    const q = omega * Math.sqrt(zeta * zeta - 1), r1 = -zeta * omega + q, r2 = -zeta * omega - q;
    return 1 - (r2 * Math.exp(r1 * tau) - r1 * Math.exp(r2 * tau)) / (r2 - r1);
  }

  /** spring() 对时间的导数（每秒进度）—— 用它做「按速度压扁」的 squash */
  function springVel(tau, zeta = 0.6, omega = 20) {
    if (tau <= 0) return 0;
    if (zeta < 1) {
      const s = Math.sqrt(1 - zeta * zeta);
      return (omega / s) * Math.exp(-zeta * omega * tau) * Math.sin(omega * s * tau);
    }
    if (zeta === 1) return omega * omega * tau * Math.exp(-omega * tau);
    const q = omega * Math.sqrt(zeta * zeta - 1), r1 = -zeta * omega + q, r2 = -zeta * omega - q;
    return omega * omega * (Math.exp(r1 * tau) - Math.exp(r2 * tau)) / (r1 - r2);
  }

  /** 绕 0 的衰减振荡 —— 一次点击、一次落地、一次余震 */
  const ring = (tau, decay = 9, omega = 26) => (tau <= 0 ? 0 : Math.exp(-decay * tau) * Math.sin(omega * tau));

  /** spring() 稳定到 1±eps 需要多少秒 —— 规划一个 beat 要 hold 多久 */
  function settle(zeta = 0.6, omega = 20, eps = 0.02) {
    let last = 0;
    for (let i = 1; i <= 20000; i++) { const t = i / 1000; if (Math.abs(1 - spring(t, zeta, omega)) > eps) last = t; }
    return last;
  }

  /** 过 {t,x,y} 结点的 Hermite 曲线 —— 手（指针）的连续路径 */
  function hermite(knots, t) {
    const n = knots.length;
    if (!n) return [0, 0];
    if (t <= knots[0].t) return [knots[0].x, knots[0].y];
    if (t >= knots[n - 1].t) return [knots[n - 1].x, knots[n - 1].y];
    let i = 0;
    while (knots[i + 1].t < t) i++;
    const k0 = knots[i], k1 = knots[i + 1], h = k1.t - k0.t || 1e-9, u = (t - k0.t) / h;
    const km = knots[Math.max(0, i - 1)], kp = knots[Math.min(n - 1, i + 2)];
    const m0x = ((k1.x - km.x) / (k1.t - km.t || 1e-9)) * h, m0y = ((k1.y - km.y) / (k1.t - km.t || 1e-9)) * h;
    const m1x = ((kp.x - k0.x) / (kp.t - k0.t || 1e-9)) * h, m1y = ((kp.y - k0.y) / (kp.t - k0.t || 1e-9)) * h;
    const h00 = 2 * u ** 3 - 3 * u ** 2 + 1, h10 = u ** 3 - 2 * u ** 2 + u;
    const h01 = -2 * u ** 3 + 3 * u ** 2, h11 = u ** 3 - u ** 2;
    return [h00 * k0.x + h10 * m0x + h01 * k1.x + h11 * m1x,
            h00 * k0.y + h10 * m0y + h01 * k1.y + h11 * m1y];
  }

  /** xorshift32 —— 只在 setup 期决定布局抖动，绝不出现在渲染路径 */
  function seededRng(seed = 1) {
    let s = (seed >>> 0) || 1;
    return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return (s >>> 0) / 4294967296; };
  }

  /** 定步长预积分采样器：真的需要积分的东西（软体/绳/磁吸）跑一次 240Hz，之后按 t 查表 */
  const DT = 1 / 240;
  function sampler(states, t0, per) {
    return (t) => states[clamp(Math.floor((t - t0) / per), 0, states.length - 1)];
  }

  /* ══════════════════════════ enter · 某样东西到场 ══════════════════════════ */

  /** 一个词「落下」：弹簧上升 + 轻微放大。不透明度**领先**于弹簧，所以不会被读成淡入。 */
  function riseWord(t, t0, { zeta = 0.6, omega = 22, dist = 26, s0 = 0.94, ds = 0.06, fade = 1.5 } = {}) {
    const k = spring(t - t0, zeta, omega);
    return { k, op: clamp(k * fade, 0, 1), y: (1 - k) * dist, s: s0 + ds * k };
  }

  /** 字标逐字落下：速度把它压扁（sy）拉宽（sx），落定后弹回。 */
  function dropLetters(t, t0, i, { dt = 0.055, zeta = 0.5, omega = 26, dist = 46,
    squash = 0.0075, max = 0.22, widen = 0.6, fade = 1.6, h = 0.012 } = {}) {
    const tau = t - t0 - i * dt;
    const k = spring(tau, zeta, omega);
    const dk = (spring(tau, zeta, omega) - spring(tau - h, zeta, omega)) / h;
    const sq = clamp(Math.abs(dk) * squash, 0, max);
    return { k, sq, op: clamp(k * fade, 0, 1), y: (1 - k) * dist, sx: 1 + sq * widen, sy: 1 - sq };
  }

  /** 卡片入场：弹簧 + 缩放 */
  function springIn(t, t0, { zeta = 0.62, omega = 18, rise = 36, s0 = 0.94, ds = 0.06, fade = 1.5 } = {}) {
    const k = spring(t - t0, zeta, omega);
    return { k, op: clamp(k * fade, 0, 1), s: s0 + ds * k, dy: (1 - k) * rise };
  }

  /** 卡片退场：抬起 + 略微放大 + 模糊消失 */
  function blurAway(t, t1, { dur = 0.22, dir = -1, dist = 90, blur = 10, grow = 0.03 } = {}) {
    const k = ssstep(t1, t1 + dur, t);
    return { k, op: 1 - k, dy: dir * k * dist, blur: k * blur, s: 1 + grow * k };
  }

  /** 整行从遮罩后面升起。y 是 dist 的比例（把行高传进来）。 */
  function riseFromMask(t, t0, i = 0, { dt = 0.13, zeta = 0.47, omega = 17, dist = 1 } = {}) {
    const k = spring(t - t0 - i * dt, zeta, omega);
    return { k, y: (1 - k) * dist, visible: k > 0 };
  }

  /** 打字机：按 cps 逐字吐，打字中光标常亮、打完后闪烁 */
  function typeChars(t, t0, text, { cps = 38, blink = 2.4 } = {}) {
    const n = clamp(Math.floor((t - t0) * cps), 0, text.length);
    const done = n >= text.length;
    return { n, str: text.slice(0, n), done, caret: (!done || Math.floor(t * blink) % 2 === 0) ? 1 : 0 };
  }

  /** 勾选框：到点从 0.8 弹起 */
  function checkOff(t, tl, { zeta = 0.5, omega = 28 } = {}) {
    const on = t >= tl, k = spring(t - tl, zeta, omega);
    return { on, k, s: on ? 0.8 + 0.2 * k + 0.25 * (1 - k) : 1 };
  }

  /** 整屏切面斜飞：右后方转进来 → 停住 → 左侧转出去。
   *  CSS 写法：translate(x) perspective(2200px) rotateY(rotY) rotateX(rotX) scale(s)。 */
  function flyPlane(t, t0, hold, { from = 1500, to = 0, exit = -1700, zeta = 0.78, omega = 14, out = 0.28,
    blurIn = 10, blurOut = 12, rotY0 = -18, rotY1 = -9, rotOut = 10, rotX = 4,
    s0 = 0.92, pre = 0.02, post = 0.35 } = {}) {
    const t1 = t0 + hold, visible = t >= t0 - pre && t < t1 + post;
    const kin = spring(t - t0, zeta, omega), kout = ssstep(t1, t1 + out, t), kc = Math.min(1, kin);
    return {
      visible, kin, kout,
      x: lerp(from, to, kin) + kout * exit,
      blur: Math.max((1 - kc) * blurIn, kout * blurOut),
      rotY: lerp(rotY0, rotY1, kc) + kout * rotOut,
      rotX, s: lerp(s0, 1, kc), op: 1 - kout,
    };
  }

  /* ══════════════════════════ carry · 下一镜从这个镜里长出来 ══════════════════════════ */
  /* 「替换」是幻灯片；「延续」才是剪辑。以下七个是让元素跨过边界的办法。 */

  /** 容器形变：矩形 A（一张卡、一个按钮）长成矩形 B（整页）。x/y 取左上角。 */
  function morphBox(t, t0, t1, A, B, { curve = ease.expoOut, spring: sp = null } = {}) {
    const k = sp ? spring(t - t0, sp.zeta ?? 0.7, sp.omega ?? 16) : curve(seg(t, t0, t1));
    const x = lerp(A.x, B.x, k), y = lerp(A.y, B.y, k), w = lerp(A.w, B.w, k), h = lerp(A.h, B.h, k);
    return { k, x, y, w, h, r: lerp(A.r ?? 0, B.r ?? 0, k), cx: x + w / 2, cy: y + h / 2 };
  }

  /** 圆形舞台从主体 (cx,cy) 打开，直到盖满画幅 */
  function irisOpen(t, t0, t1, cx, cy, { W = 1920, H = 1080, curve = ease.expoOut, r0 = 0 } = {}) {
    const k = curve(seg(t, t0, t1));
    const far = Math.max(Math.hypot(cx, cy), Math.hypot(W - cx, cy), Math.hypot(cx, H - cy), Math.hypot(W - cx, H - cy)) + 2;
    return { k, cx, cy, r: lerp(r0, far, k), covered: k >= 1 };
  }

  /** 镜头推入 target{x,y,w,h} 直到它填满画幅 —— 它的内部就是下一镜。
   *  缩放取对数插值，读起来是「一个速度」而不是「先慢后快」。
   *  screen = world·s + (tx,ty) → DOM：matrix(...)，transform-origin:0 0；canvas：setTransform(...) */
  function diveInto(t, t0, t1, target, { W = 1920, H = 1080, curve = ease.expoInOut, fit = 'cover' } = {}) {
    const k = curve(seg(t, t0, t1));
    const sEnd = fit === 'contain' ? Math.min(W / target.w, H / target.h) : Math.max(W / target.w, H / target.h);
    const s = Math.exp(Math.log(sEnd) * k);
    const tcx = target.x + target.w / 2, tcy = target.y + target.h / 2;
    const px = lerp(tcx, W / 2, k), py = lerp(tcy, H / 2, k);
    const tx = px - s * tcx, ty = py - s * tcy;
    return { k, s, tx, ty, matrix: [s, 0, 0, s, tx, ty] };
  }

  /** 主体沿弧线跳到下一个位置（落点配 landHit） */
  function arcHop(t, t0, t1, from, to, { height = 200, curve = ease.smoother } = {}) {
    const k = curve(seg(t, t0, t1));
    return { k, x: lerp(from.x, to.x, k), y: lerp(from.y, to.y, k) - Math.sin(k * Math.PI) * height };
  }

  /** 第 i/n 个元素沿扇形弧线归位；按索引错峰 */
  function gatherTo(t, t0, t1, i, n, from, to, { dt = 0.08, arc = 120, spin = 0.4, curve = ease.smoother } = {}) {
    const k = curve(seg(t, t0 + i * dt, t1 + i * dt)), o = i - (n - 1) / 2, bump = Math.sin(k * Math.PI);
    return { k, x: lerp(from.x, to.x, k), y: lerp(from.y, to.y, k) - bump * arc, rot: bump * o * spin };
  }

  /** 有弹性的滑轨：每次 switch 时间点推进一格并余震；文字滞后一拍。
   *  第 j 块面板位于 x = 中心 + (j − shift)·width + wobble。 */
  function railShift(t, switches, { dur = 0.35, amp = 55, decay = 7, omega = 22, tilt = 0.08,
    stretchX = 0.24, stretchY = 0.15, lag = 1.8, curve = ease.smoother } = {}) {
    let shift = 0, r = 0;
    for (const ts of switches) { shift += curve(seg(t, ts, ts + dur)); r += ring(t - ts, decay, omega); }
    const stretch = Math.abs(r);
    return { shift, index: Math.round(shift), wobble: r * amp, rot: r * tilt,
      sx: 1 + stretch * stretchX, sy: 1 - stretch * stretchY, textDx: -r * amp * lag };
  }

  /** 全员折成品牌圆盘：一个圆盘长大并旋转 */
  function sealDisc(t, t0, t1, { r = 235, turns = 1, curve = ease.smoother } = {}) {
    const k = curve(seg(t, t0, t1));
    return { k, r: r * k, rot: k * turns * Math.PI * 2 };
  }

  /** 硬切词：一记一记地砸。list = [[t, word], …]。这是全片唯一允许「裸切」的地方。 */
  function burstWord(t, list) {
    let word = '', i = -1;
    for (let j = 0; j < list.length; j++) if (t >= list[j][0]) { word = list[j][1]; i = j; }
    return { word, i };
  }

  /* ══════════════════════════ contact · 一件事引发另一件 ══════════════════════════ */

  /** 落地的那圈震动：撞击瞬间压扁，随后余震。把 r 喂给被撞的东西。 */
  function landHit(t, tHit, { decay = 7, omega = 22, sqx = 0.13, sqy = 0.16 } = {}) {
    const r = ring(t - tHit, decay, omega);
    return { r, sx: 1 + r * sqx, sy: 1 - r * sqy };
  }

  /** 落在 cx 的一击把标题撕开：离命中点越近的字被推得越远，弹一下再合上。 */
  function splitOnHit(t, tHit, x, cx, { width = 600, spread = 65, bounce = 65, rot = 0.18, falloff = 3,
    open = [-0.01, 0.48], close = [0.63, 0.98], decay = 7, omega = 22, curve = ease.smoother } = {}) {
    const d = (x - cx) / width, r = ring(t - tHit, decay, omega);
    const apart = curve(seg(t, tHit + open[0], tHit + open[1])) * (1 - curve(seg(t, tHit + close[0], tHit + close[1])));
    return { dx: Math.sign(d) * apart * spread, dy: r * bounce * Math.exp(-d * d * falloff), rot: r * d * rot };
  }

  /** 一次点击：按下沉、反弹、状态翻转 */
  function tapPress(t, tc, { depth = 0.16, decay = 10, omega = 30, flash = 0.4 } = {}) {
    const cl = t - tc, sq = cl > 0 ? ring(cl, decay, omega) * depth : 0;
    return { s: 1 + sq, sq, down: cl > 0, active: cl > 0 && cl < flash };
  }

  /** 指针：沿 Hermite 路径走，每次点击压到 down 并保持 hold 秒 */
  function pointer(t, knots, clicks = [], { down = 0.84, hold = 0.14 } = {}) {
    const p = hermite(knots, t);
    let s = 1;
    for (const c of clicks) { const d = t - c; if (d >= 0 && d < hold) s = down; }
    return { x: p[0], y: p[1], s };
  }

  /** 沿运动方向拉长、横向收窄。vx/vy 单位 px/s。 */
  function stretch2(vx, vy, { k = 0.0012, max = 0.45, kY = 0.0008, maxY = 0.3 } = {}) {
    const sp = Math.hypot(vx, vy);
    return { speed: sp, ang: Math.atan2(vy, vx), sx: 1 + clamp(sp * k, 0, max), sy: 1 - clamp(sp * kY, 0, maxY) };
  }

  /* ── 活体机构（sim）──
   * 卡片里「真的在跑」的机制：由手驱动，240Hz 预积分一次，之后 at(t) 查表。
   * 这是「UI 不是贴图，是活的」的来源。card = {t, out, x, y}。 */
  const sim = {
    DT,
    /** 磁性按钮：指针进半径 R 就被吸过去 */
    magnet(card, hand, { B = { x: 230, y: 158 }, R = 150, pull = 0.36, K = 120, damp = 0.85 } = {}) {
      const D = Math.pow(damp, DT * 60);
      let x = 0, y = 0, vx = 0, vy = 0;
      const st = [];
      for (let t = card.t; t <= card.out + 0.3; t += DT) {
        const h = hand(t);
        const dx = h[0] - (card.x + B.x), dy = h[1] - (card.y + B.y), d = Math.hypot(dx, dy);
        let tx = 0, ty = 0;
        if (d < R) { const f = pull * (1 - (d / R) ** 2); tx = dx * f; ty = dy * f; }
        vx += (tx - x) * K * DT; vy += (ty - y) * K * DT; vx *= D; vy *= D; x += vx * DT; y += vy * DT;
        st.push([x, y]);
      }
      return { st, per: DT, B, at: sampler(st, card.t, DT) };
    },
    /** 弹簧跟随：在盒子里追指针，出盒子就回位 */
    follow(card, hand, { K = 70, damp = 0.88, home = [230, 140], box = [30, 430, 50, 240],
      reach = [40, 500, 40, 310] } = {}) {
      const D = Math.pow(damp, DT * 60);
      let x = home[0], y = home[1], vx = 0, vy = 0;
      const st = [];
      for (let t = card.t; t <= card.out + 0.3; t += DT) {
        const h = hand(t);
        let tx = clamp(h[0] - card.x, box[0], box[1]), ty = clamp(h[1] - card.y, box[2], box[3]);
        const inside = h[0] > card.x - reach[0] && h[0] < card.x + reach[1] && h[1] > card.y - reach[2] && h[1] < card.y + reach[3];
        if (!inside) { tx = home[0]; ty = home[1]; }
        vx += (tx - x) * K * DT; vy += (ty - y) * K * DT; vx *= D; vy *= D; x += vx * DT; y += vy * DT;
        st.push([x, y, vx, vy]);
      }
      return { st, per: DT, at: sampler(st, card.t, DT) };
    },
    /** 果冻：一圈带邻接耦合的径向弹簧，指针按到哪凹到哪 */
    jelly(card, hand, { N = 48, C = { x: 230, y: 150 }, R0 = 78, K = 42, CP = 1800, damp = 0.962,
      reach = 60, dent = 14 } = {}) {
      const D = Math.pow(damp, DT * 60);
      const r = new Float32Array(N), v = new Float32Array(N);
      const st = [];
      let step = 0;
      for (let t = card.t; t <= card.out + 0.3; t += DT, step++) {
        const h = hand(t), hx = h[0] - (card.x + C.x), hy = h[1] - (card.y + C.y);
        for (let i = 0; i < N; i++) {
          const th = (i / N) * Math.PI * 2;
          const px = Math.cos(th) * R0 * (1 + r[i]), py = Math.sin(th) * R0 * (1 + r[i]);
          const d = Math.hypot(hx - px, hy - py);
          let push = 0;
          if (d < reach) push = -(1 - d / reach) * dent;
          const lap = r[(i + N - 1) % N] + r[(i + 1) % N] - 2 * r[i];
          v[i] += (-r[i] * K + lap * CP + push) * DT;
          v[i] *= D;
        }
        for (let i = 0; i < N; i++) r[i] += v[i] * DT;
        if (step % 4 === 0) st.push(Float32Array.from(r));
      }
      return { st, per: DT * 4, N, C, R0, at: sampler(st, card.t, DT * 4) };
    },
    /** 绳：N 个结点挂在 (ax,ay)，被指针推歪。样本是 [x0,y0,x1,y1,…] */
    verlet(card, hand, { N = 16, L = 13, ax = 230, ay = 40, damp = 0.985, gravity = 1400,
      reach = 34, push = 2.2, iters = 3 } = {}) {
      const px = new Float32Array(N), py = new Float32Array(N), ox = new Float32Array(N), oy = new Float32Array(N);
      for (let i = 0; i < N; i++) { px[i] = ox[i] = ax; py[i] = oy[i] = ay + i * L; }
      const st = [];
      let step = 0;
      for (let t = card.t; t <= card.out + 0.3; t += DT, step++) {
        const h = hand(t), hx = h[0] - card.x, hy = h[1] - card.y;
        for (let i = 1; i < N; i++) {
          const vx = (px[i] - ox[i]) * damp, vy = (py[i] - oy[i]) * damp;
          ox[i] = px[i]; oy[i] = py[i];
          px[i] += vx; py[i] += vy + gravity * DT * DT;
          const dx = px[i] - hx, dy = py[i] - hy, d = Math.hypot(dx, dy);
          if (d < reach && d > 0.01) { const f = ((reach - d) / reach) * push; px[i] += (dx / d) * f; py[i] += (dy / d) * f; }
        }
        for (let it = 0; it < iters; it++) {
          px[0] = ax; py[0] = ay;
          for (let i = 0; i < N - 1; i++) {
            const dx = px[i + 1] - px[i], dy = py[i + 1] - py[i];
            const d = Math.hypot(dx, dy) || 1e-6, c = ((d - L) / d) * 0.5;
            if (i === 0) { px[1] -= dx * c * 2; py[1] -= dy * c * 2; }
            else { px[i] += dx * c; py[i] += dy * c; px[i + 1] -= dx * c; py[i + 1] -= dy * c; }
          }
        }
        if (step % 4 === 0) {
          const s = new Float32Array(N * 2);
          for (let i = 0; i < N; i++) { s[i * 2] = px[i]; s[i * 2 + 1] = py[i]; }
          st.push(s);
        }
      }
      return { st, per: DT * 4, N, at: sampler(st, card.t, DT * 4) };
    },
  };

  /* ══════════════════════════ camera · 运镜 ══════════════════════════ */
  /* 静止的机位会让观众觉得「就缺灵动的跟踪运镜」。key 是机位，operator 的手感来自三层：
   *   · 追（把主体前方的点提前 ~0.1s 落 key）
   *   · 甩（落点先用 expoInOut 甩过去再停）
   *   · 抖（每次落地 shake 一下）
   * 空地上不加参照物，运镜读不出来 —— 后面垫一层 gridDots。 */

  /** key 列表 {t,x,y,zoom?,rot?,curve?}；(x,y) 是画幅中心对应的世界点。zoom 在对数空间插值。 */
  function camTrack(t, keys, { curve = ease.cubicInOut, W = 1920, H = 1080 } = {}) {
    const pick = (k) => ({ x: k.x ?? W / 2, y: k.y ?? H / 2, zoom: k.zoom ?? 1, rot: k.rot ?? 0 });
    if (!keys.length) return { x: W / 2, y: H / 2, zoom: 1, rot: 0 };
    if (t <= keys[0].t) return pick(keys[0]);
    const n = keys.length;
    if (t >= keys[n - 1].t) return pick(keys[n - 1]);
    let i = 0;
    while (keys[i + 1].t < t) i++;
    const A = pick(keys[i]), B = pick(keys[i + 1]);
    const k = (keys[i + 1].curve || curve)(seg(t, keys[i].t, keys[i + 1].t));
    return {
      x: lerp(A.x, B.x, k), y: lerp(A.y, B.y, k),
      zoom: Math.exp(lerp(Math.log(A.zoom), Math.log(B.zoom), k)), rot: lerp(A.rot, B.rot, k),
    };
  }

  /** 位于 depth 的一层在 cam 下的仿射矩阵 [a,b,c,d,e,f]。
   *  depth 0 = 焦平面；>0 更远（动得少、缩得少）；<0 更近（动得多）—— 一个机位造视差。 */
  function layerMatrix(cam, { W = 1920, H = 1080, depth = 0 } = {}) {
    const f = 1 / (1 + Math.max(-0.9, depth));
    const cx = W / 2 + (cam.x - W / 2) * f, cy = H / 2 + (cam.y - H / 2) * f;
    const z = Math.exp(Math.log(cam.zoom) * f);
    const c = Math.cos(cam.rot * f) * z, s = Math.sin(cam.rot * f) * z;
    return [c, s, -s, c, W / 2 - (c * cx - s * cy), H / 2 - (s * cx + c * cy)];
  }

  /** 位于 depth 的一层、机位对焦在 focus 时的景深模糊（px） */
  const depthBlur = (depth, focus = 0, { k = 10, max = 14 } = {}) => Math.min(max, Math.abs(depth - focus) * k);

  /** 甩镜：dur 内走完 dist。只有开快门才读得出来。 */
  function whipPan(t, t0, dur, dist, { curve = ease.expoInOut } = {}) {
    return { k: curve(seg(t, t0, t0 + dur)), d: dist * curve(seg(t, t0, t0 + dur)) };
  }

  /** 落地后的机位余震：衰减、确定、撞击前恒为 0 */
  function camShake(t, tHit, { amp = 12, decay = 9, freq = 19, seed = 1 } = {}) {
    const tau = t - tHit;
    if (tau <= 0) return { x: 0, y: 0, rot: 0 };
    const r = seededRng(seed);
    const fx = freq * (1 + 0.1 * r()), fy = freq * (1.31 + 0.1 * r()), fr = freq * (0.77 + 0.1 * r());
    const e = amp * Math.exp(-decay * tau), w = 2 * Math.PI * tau;
    return { x: e * Math.sin(w * fx), y: 0.7 * e * Math.sin(w * fy), rot: 0.0015 * e * Math.sin(w * fr) };
  }

  /** hold 期间的慢推：1 → 1+amount。注意：它是**运动**，别放在「静止呼吸」上。 */
  const slowPush = (t, t0, t1, amount = 0.07) => 1 + amount * seg(t, t0, t1);

  /** 远处的点阵（透过 cam 看）。屏幕上一个点恒为 px 半径 —— 给运镜一个可以蹭着滑过去的参照。 */
  function gridDots(cam, { depth = 1.2, spacing = 48, px = 1.4, W = 1920, H = 1080 } = {}) {
    const M = layerMatrix(cam, { W, H, depth });
    const c = [[0, 0], [W, 0], [0, H], [W, H]].map((p) => toWorld(M, p[0], p[1]));
    const xs = c.map((p) => p[0]), ys = c.map((p) => p[1]);
    return {
      matrix: M, spacing, r: px / Math.hypot(M[0], M[1]),
      x0: Math.floor(Math.min(...xs) / spacing) * spacing, x1: Math.max(...xs),
      y0: Math.floor(Math.min(...ys) / spacing) * spacing, y1: Math.max(...ys),
    };
  }

  /** 透过 layerMatrix 的 M：世界→屏幕、屏幕→世界、世界框的屏幕包围盒 */
  const toScreen = (M, x, y) => [M[0] * x + M[2] * y + M[4], M[1] * x + M[3] * y + M[5]];
  function toWorld(M, x, y) {
    const d = M[0] * M[3] - M[1] * M[2], u = x - M[4], v = y - M[5];
    return [(M[3] * u - M[2] * v) / d, (M[0] * v - M[1] * u) / d];
  }
  function boxOnScreen(M, b) {
    const P = [[b.x, b.y], [b.x + b.w, b.y], [b.x, b.y + b.h], [b.x + b.w, b.y + b.h]].map((p) => toScreen(M, p[0], p[1]));
    const xs = P.map((p) => p[0]), ys = P.map((p) => p[1]);
    const x0 = Math.min(...xs), y0 = Math.min(...ys);
    return { x: x0, y: y0, w: Math.max(...xs) - x0, h: Math.max(...ys) - y0, op: b.op };
  }

  /** 两个机位之间，画幅四角的屏幕位移最大值 —— 运镜在 __motion 里的那份位移。
   *  渲染器拿它换算「这一帧要开几次快门」。 */
  function screenTravel(c0, c1, cMid, { W = 1920, H = 1080, depth = 0 } = {}) {
    const M0 = layerMatrix(c0, { W, H, depth }), M1 = layerMatrix(c1, { W, H, depth }), Mm = layerMatrix(cMid, { W, H, depth });
    let d = 0;
    for (const [sx, sy] of [[0, 0], [W, 0], [0, H], [W, H]]) {
      const [wx, wy] = toWorld(Mm, sx, sy);
      const p = toScreen(M0, wx, wy), r = toScreen(M1, wx, wy);
      d = Math.max(d, Math.hypot(p[0] - r[0], p[1] - r[1]));
    }
    return d;
  }

  /* ══════════════════════════ ambience · 环境与光 ══════════════════════════ */

  /** SwiftUI 的命名弹簧：Spring(duration d, bounce b) ⇔ zeta = 1−b, omega = 2π/d。
   *  想让 UI 读起来「原生」而不是「被做了动画」，用它。 */
  const SWIFT = { smooth: 0, snappy: 0.15, bouncy: 0.3 };
  function swiftSpring(tau, kind = 'smooth', { duration = 0.5, bounce = null } = {}) {
    const b = bounce ?? SWIFT[kind] ?? 0;
    return spring(tau, 1 - b, (2 * Math.PI) / duration);
  }

  /** 常驻的光场：level 0 = 静止（低辉光，地平线 ≈ rest·H），1 = 整幅被淹。
   *  返回一个锚在画幅下方的椭圆（径向渐变填它），core 是「亮到能把字翻白」的半半径。
   *  涌起 ≤0.4s，退去 ~1s。 */
  function glowField(level, { W = 1920, H = 1080, rest = 0.84, top = -300, r0 = 660, r1 = 1500, tilt = 0.012 } = {}) {
    const ry = r0 + r1 * level, horizon = lerp(H * rest, top, level);
    return { cx: W / 2, cy: horizon + 0.62 * ry, rx: ry * 2.3, ry, tilt, horizon, core: 0.5, stops: [0, 0.36, 0.6, 0.8, 1] };
  }

  /** 一圈圈退去的洪水：n 个半径错峰离开一点，每个 dur 秒穿过画幅。
   *  ring0 之外填洪水色、环与环之间交替两种色调，最里面露出世界。 */
  function floodRings(t, t0, { n = 3, dt = 0.16, dur = 1.25, rMax = 1160, curve = ease.smoother } = {}) {
    const r = [];
    for (let k = 0; k < n; k++) r.push(rMax * curve(seg(t, t0 + k * dt, t0 + k * dt + dur)));
    return { r, done: t >= t0 + (n - 1) * dt + dur };
  }

  /* 噪声场（"原生 MeshGradient" 质感）：域扭曲值噪声、两个八度、小网格、对比拉伸后查色带。
   * 返回 gx×gy 的 RGBA；putImageData 进一张小 canvas 再模糊放大 —— 这是「布」的读法。
   * 明度非单调的色带（两片亮之间夹一道暗折）才是布；单调的就是渐变色卡。 */
  function noiseHash(x, y, s) {
    let h = (x * 374761393 + y * 668265263 + s * 1442695041) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  }
  function noiseAt(x, y, s) {
    const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = noiseHash(xi, yi, s), b = noiseHash(xi + 1, yi, s);
    const c = noiseHash(xi, yi + 1, s), d = noiseHash(xi + 1, yi + 1, s);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  }
  const noiseFbm = (x, y, s) => 0.5 * noiseAt(x, y, s) + 0.25 * noiseAt(x * 2.02, y * 2.02, s);
  function rampPick(stops, k) {
    k = clamp(k, 0, 1);
    for (let i = 1; i < stops.length; i++) {
      if (k <= stops[i][0]) {
        const [a, A] = stops[i - 1], [b, B] = stops[i], u = (k - a) / (b - a || 1e-9);
        return A.map((v, j) => v + (B[j] - v) * u);
      }
    }
    return stops[stops.length - 1][1];
  }
  const RAMP = {
    ember: [[0, [200, 120, 24]], [0.22, [236, 170, 34]], [0.42, [122, 96, 26]], [0.54, [160, 94, 32]], [0.74, [240, 74, 92]], [1, [252, 210, 198]]],
    peach: [[0, [240, 150, 92]], [0.24, [252, 204, 148]], [0.44, [190, 104, 66]], [0.58, [236, 124, 108]], [0.8, [250, 186, 172]], [1, [255, 240, 228]]],
    dusk: [[0, [118, 58, 94]], [0.24, [226, 98, 112]], [0.44, [88, 44, 68]], [0.58, [176, 74, 98]], [0.8, [246, 150, 122]], [1, [255, 224, 204]]],
    deep: [[0, [16, 22, 44]], [0.26, [30, 62, 120]], [0.46, [18, 30, 62]], [0.6, [42, 88, 150]], [0.82, [120, 170, 220]], [1, [226, 240, 252]]],
    sage: [[0, [70, 92, 74]], [0.24, [122, 158, 127]], [0.44, [58, 74, 62]], [0.6, [96, 128, 104]], [0.82, [188, 210, 190]], [1, [240, 246, 238]]],
  };
  function noiseField(tau, seed = 3, stops = RAMP.peach, { gx = 16, gy = 20, contrast = 3.4, out = null } = {}) {
    const d = out || new Uint8ClampedArray(gx * gy * 4);
    for (let j = 0; j < gy; j++) {
      for (let i = 0; i < gx; i++) {
        const u = (i / gx) * 1.1, v = (j / gy) * 1.4;
        const qx = noiseFbm(u + 0.11 * tau, v - 0.07 * tau, seed);
        const qy = noiseFbm(u + 5.2 - 0.09 * tau, v + 1.3 + 0.05 * tau, seed);
        const k = 0.5 + (noiseFbm(u + 1.8 * qx + 0.04 * tau, v + 1.8 * qy, seed) - 0.375) * contrast;
        const c = rampPick(stops, k), n = (i + j * gx) * 4;
        d[n] = c[0]; d[n + 1] = c[1]; d[n + 2] = c[2]; d[n + 3] = 255;
      }
    }
    return d;
  }
  noiseField.ramps = RAMP;
  noiseField.ramp = rampPick;

  /** 传送带：rampDur 秒的平滑起步后匀速，stop 处平滑停住。一次积分，之后仍是 t 的纯函数。
   *  at(t) → {x, tau}：x = 走过的 px，tau = 一个会跟着变慢的时钟（每张卡自己的循环用它驱动）。 */
  function beltLoop({ dur, start = 0, speed = 204, rampDur = 1.0, stop = null, hz = 240 } = {}) {
    const n = Math.ceil(dur * hz) + 1;
    const X = new Float64Array(n), TA = new Float64Array(n);
    let x = 0, tau = 0;
    for (let i = 0; i < n; i++) {
      const t = i / hz;
      const k = stop ? 1 - smooth(seg(t, stop[0], stop[1])) : 1;
      x += (speed * swiftSpring(t - start, 'smooth', { duration: rampDur }) * k) / hz;
      tau += k / hz;
      X[i] = x; TA[i] = tau;
    }
    return {
      at(t) {
        const f = clamp(t * hz, 0, n - 1), i = Math.floor(f), j = Math.min(n - 1, i + 1), u = f - i;
        return { x: lerp(X[i], X[j], u), tau: lerp(TA[i], TA[j], u) };
      },
    };
  }

  /* ══════════════════════════ 导出 ══════════════════════════ */
  const HXM = {
    version: '2.0.0', library: 'html-explainer/motion',
    // scalars
    clamp, lerp, seg, sstep, ssstep, stagger, smooth, smoother,
    // curves
    ease, cubicBezier, tween, t80, spring, springVel, ring, settle, hermite, seededRng,
    // enter
    riseWord, dropLetters, springIn, blurAway, riseFromMask, typeChars, checkOff, flyPlane,
    // carry
    morphBox, irisOpen, diveInto, arcHop, gatherTo, railShift, sealDisc, burstWord,
    // contact
    landHit, splitOnHit, tapPress, pointer, stretch2, sim,
    // camera
    camTrack, layerMatrix, depthBlur, whipPan, camShake, slowPush, gridDots,
    toScreen, toWorld, boxOnScreen, screenTravel,
    // ambience
    swiftSpring, glowField, floodRings, noiseField, beltLoop,
  };

  root.HXM = HXM;
  if (typeof module === 'object' && module.exports) module.exports = HXM;
})(typeof window !== 'undefined' ? window : globalThis);
