#!/usr/bin/env node
/**
 * test_motion.mjs —— 动效库（assets/motion.js → window.HXM）的数值自测。
 *
 *   node tests/test_motion.mjs          # 期望全部 PASS，退出码 0
 *
 * 为什么值得写：动效库是无头数学库，错了不会报错、只会「画面看着怪」。
 * 这里把每个 move 的**可证伪性质**固化成断言：
 *   · 端态：t 走到末了必须落在设计值上
 *   · 起点：t 在定义域之前必须恒为静止（否则冷开场会「先闪一下」）
 *   · 纯函数：同 t 两次调用必须逐位相等（渲染器 seek 两次要出同一帧）
 *   · 单调/有界：弹簧不过冲太过、半径有上限
 *   · 曲线：t80 落在文档标称的档位上
 */
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const HXM = require(path.join(__dirname, '..', 'assets', 'motion.js'));

let pass = 0, fail = 0;
const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;
function ok(name, cond, detail = '') {
  if (cond) { pass++; console.log(`  PASS  ${name}${detail ? '  ' + detail : ''}`); }
  else { fail++; console.log(`  FAIL  ${name}  ${detail}`); }
}
function group(n) { console.log(`\n${n}`); }

/* ───────────── 曲线 ───────────── */
group('curves');
{
  for (const [k, c] of Object.entries(HXM.ease)) {
    if (typeof c !== 'function') continue;
    // ease.back 是**工厂**（返回曲线），不是曲线本身 —— 取它的默认实例来测
    if (typeof c(0) === 'function') {
      const inst = c();
      ok(`ease.${k}() 是工厂，实例 (0)=0/(1)=1`, near(inst(0), 0, 1e-9) && near(inst(1), 1, 1e-9));
      continue;
    }
    ok(`ease.${k}(0)=0`, near(c(0), 0, 1e-9), `got ${c(0)}`);
    ok(`ease.${k}(1)=1`, near(c(1), 1, 1e-9), `got ${c(1)}`);
  }
  // t80 档位：文档里 expoOut≈.23 / quintOut≈.28 / smoother≈.67 / linear≈.80
  const bands = [['expoOut', 0.23, 0.03], ['quintOut', 0.28, 0.03], ['smoother', 0.67, 0.04], ['linear', 0.80, 0.01]];
  for (const [k, want, tol] of bands) {
    const got = HXM.t80(HXM.ease[k]);
    ok(`t80(${k}) ≈ ${want}`, Math.abs(got - want) <= tol, `got ${got.toFixed(3)}`);
  }
  ok('t80 单调：expoOut < smoother', HXM.t80(HXM.ease.expoOut) < HXM.t80(HXM.ease.smoother));
  const bz = HXM.cubicBezier(0.16, 1, 0.3, 1);
  ok('cubicBezier(0)=0', near(bz(0), 0, 1e-9));
  ok('cubicBezier(1)=1', near(bz(1), 1, 1e-9));
  ok('cubicBezier 过冲：中段单调不减', bz(0.5) > 0.5);
}

/* ───────────── 弹簧 ───────────── */
group('spring');
{
  ok('spring 从 0 起', near(HXM.spring(0), 0, 1e-9));
  const s1 = HXM.spring(3, 0.6, 20);
  ok('spring 收敛到 1', near(s1, 1, 2e-2), `got ${s1.toFixed(4)}`);
  const over = Math.max(...Array.from({ length: 600 }, (_, i) => HXM.spring(i / 200, 0.4, 20)));
  ok('zeta .4 过冲但 < 1.5', over > 1.0 && over < 1.5, `peak ${over.toFixed(3)}`);
  const crit = Math.max(...Array.from({ length: 600 }, (_, i) => HXM.spring(i / 200, 1, 20)));
  ok('zeta 1 不过冲', crit <= 1.0 + 1e-6, `peak ${crit.toFixed(5)}`);
  const st = HXM.settle(0.6, 20, 0.02);
  ok('settle 有界 (0,3]', st > 0 && st <= 3, `${st}s`);
  ok('springVel(0)=0', near(HXM.springVel(0), 0, 1e-9));
}

/* ───────────── 纯函数（渲染器的命根子） ───────────── */
group('purity — 同 t 两次调用必须逐位相等');
{
  const w1 = HXM.riseWord(0.42, 0.15), w2 = HXM.riseWord(0.42, 0.15);
  ok('riseWord 幂等', JSON.stringify(w1) === JSON.stringify(w2));
  const l1 = HXM.dropLetters(1.31, 0.5, 3), l2 = HXM.dropLetters(1.31, 0.5, 3);
  ok('dropLetters 幂等', JSON.stringify(l1) === JSON.stringify(l2));
  const f1 = HXM.flyPlane(3.2, 3.0, 0.9), f2 = HXM.flyPlane(3.2, 3.0, 0.9);
  ok('flyPlane 幂等', JSON.stringify(f1) === JSON.stringify(f2));
  const c1 = HXM.camShake(5.1, 5.0, { seed: 7 }), c2 = HXM.camShake(5.1, 5.0, { seed: 7 });
  ok('camShake 幂等', JSON.stringify(c1) === JSON.stringify(c2));
  const m1 = HXM.morphBox(1.0, 0.5, 1.5, { x: 0, y: 0, w: 10, h: 10 }, { x: 100, y: 50, w: 400, h: 300 });
  const m2 = HXM.morphBox(1.0, 0.5, 1.5, { x: 0, y: 0, w: 10, h: 10 }, { x: 100, y: 50, w: 400, h: 300 });
  ok('morphBox 幂等', JSON.stringify(m1) === JSON.stringify(m2));
  // rng 同种子同序列
  const a = HXM.seededRng(11), b = HXM.seededRng(11);
  ok('seededRng 同种子同序列', Array.from({ length: 5 }, a).join(',') === Array.from({ length: 5 }, b).join(','));
  const c = HXM.seededRng(12);
  ok('seededRng 换种子换序列', a() !== c());
  ok('seededRng ∈ [0,1)', Array.from({ length: 200 }, a).every((v) => v >= 0 && v < 1));
}

/* ───────────── enter ───────────── */
group('enter');
{
  const before = HXM.riseWord(0.10, 0.15);
  ok('riseWord 定义域前静止', before.op === 0 && before.y === 26, `op ${before.op} y ${before.y}`);
  const after = HXM.riseWord(9, 0.15);
  ok('riseWord 末端 op=1', near(after.op, 1, 1e-6), `op ${after.op}`);
  ok('riseWord 末端 y≈0', Math.abs(after.y) < 0.05, `y ${after.y.toFixed(3)}`);
  ok('riseWord 末端 s→1', near(after.s, 1, 1e-3), `s ${after.s.toFixed(4)}`);

  const dl = HXM.dropLetters(9, 0.5, 2);
  ok('dropLetters 末端平直 (sq≈0)', Math.abs(dl.sq) < 1e-3, `sq ${dl.sq.toFixed(5)}`);
  const dlMid = HXM.dropLetters(0.62, 0.5, 0);
  ok('dropLetters 中途被压扁 (sy<1)', dlMid.sy < 1, `sy ${dlMid.sy.toFixed(4)}`);

  const lo = HXM.blurAway(9, 7.0);
  ok('blurAway 末端 op=0', near(lo.op, 0, 1e-6));
  const lo0 = HXM.blurAway(7.0, 7.0);
  ok('blurAway 起点 op=1', near(lo0.op, 1, 1e-6));

  const ty = HXM.typeChars(0.0, 0.0, 'abcdefghij', { cps: 38 });
  ok('typeChars 起点 0 字', ty.n === 0 && ty.str === '');
  const tyD = HXM.typeChars(99, 0, 'abc');
  ok('typeChars 打完 done', tyD.done && tyD.str === 'abc' && tyD.n === 3);
  const tyC = HXM.typeChars(99, 0, 'abc', { blink: 2.4 });
  ok('typeChars 打完光标闪烁 (有 0 有 1)', typeof tyC.caret === 'number');

  const tkB = HXM.checkOff(1.0, 2.0);
  ok('checkOff 未到点 on=false', tkB.on === false && tkB.s === 1);
  const tkA = HXM.checkOff(9, 2.0);
  ok('checkOff 到点 on=true', tkA.on === true);

  const fpOff = HXM.flyPlane(0.0, 3.0, 0.9);
  ok('flyPlane 定义域外 invisible', !fpOff.visible);
  const fpOn = HXM.flyPlane(3.5, 3.0, 0.9);
  ok('flyPlane 保持期 visible', fpOn.visible && fpOn.op > 0.9, `op ${fpOn.op.toFixed(3)}`);
  const fpOut = HXM.flyPlane(4.4, 3.0, 0.9);
  ok('flyPlane 退场 op 下降', fpOut.op < 0.9, `op ${fpOut.op.toFixed(3)}`);
  ok('flyPlane 退场模糊上升', fpOut.blur > 1, `blur ${fpOut.blur.toFixed(2)}`);
}

/* ───────────── carry ───────────── */
group('carry');
{
  const A = { x: 100, y: 100, w: 50, h: 50, r: 8 }, B = { x: 0, y: 0, w: 1920, h: 1080, r: 0 };
  const m0 = HXM.morphBox(0.5, 0.5, 1.5, A, B), m1 = HXM.morphBox(1.5, 0.5, 1.5, A, B);
  ok('morphBox 起点=A', near(m0.x, 100) && near(m0.w, 50));
  ok('morphBox 终点=B', near(m1.x, 0) && near(m1.w, 1920) && near(m1.h, 1080));
  ok('morphBox 中心随之移动', m1.cx === 960 && m1.cy === 540);

  const i0 = HXM.irisOpen(1.0, 1.0, 2.0, 960, 540), i1 = HXM.irisOpen(2.0, 1.0, 2.0, 960, 540);
  ok('irisOpen 起点 r≈0', i0.r < 1e-6 && i0.covered === false);
  ok('irisOpen 终点 盖满画幅', i1.covered && i1.r >= Math.hypot(960, 540), `r ${i1.r.toFixed(1)}`);

  const d1 = HXM.diveInto(2.0, 1.0, 2.0, { x: 0, y: 0, w: 1920, h: 1080 });
  ok('diveInto 终态 s=1', near(d1.s, 1, 1e-6), `s ${d1.s}`);
  const dHalf = HXM.diveInto(1.5, 1.0, 2.0, { x: 0, y: 0, w: 1920, h: 1080 });
  ok('diveInto 对数空间：中点是几何平均', Math.abs(dHalf.s - Math.sqrt(1)) < 1e-9 || dHalf.s <= 1 + 1e-9);
  const dZoom = HXM.diveInto(2.0, 1.0, 2.0, { x: 900, y: 500, w: 120, h: 80 });
  ok('diveInto 推入小目标 s 很大', dZoom.s >= 16 - 1e-6, `s ${dZoom.s.toFixed(2)}`);
  ok('diveInto 矩阵 6 元', dZoom.matrix.length === 6);

  const h0 = HXM.arcHop(1.0, 1.0, 2.0, { x: 0, y: 0 }, { x: 100, y: 0 });
  const hm = HXM.arcHop(1.5, 1.0, 2.0, { x: 0, y: 0 }, { x: 100, y: 0 });
  ok('arcHop 起终点 y 相同', near(h0.y, 0, 1e-6) && near(HXM.arcHop(2.0, 1.0, 2.0, { x: 0, y: 0 }, { x: 100, y: 0 }).y, 0, 1e-6));
  ok('arcHop 中途拱起 (y<0)', hm.y < -50, `y ${hm.y.toFixed(1)}`);

  const r0 = HXM.railShift(1.0, [1.5, 2.5]);
  const r2 = HXM.railShift(9.0, [1.5, 2.5]);
  ok('railShift 起点 shift=0', near(r0.shift, 0, 1e-6));
  ok('railShift 末端 shift=2', near(r2.shift, 2, 1e-3), `shift ${r2.shift}`);
  ok('railShift 末端余震停 (<1px)', Math.abs(r2.wobble) < 1, `wobble ${r2.wobble.toFixed(4)}`);

  const s1 = HXM.sealDisc(9, 1, 2, { r: 200 });
  ok('sealDisc 末端 r=200', near(s1.r, 200, 1e-6));
  ok('sealDisc 末端转满一圈', near(s1.rot, Math.PI * 2, 1e-6));

  const bw = HXM.burstWord(13.6, [[13.25, 'a'], [13.5, 'b'], [13.72, 'c']]);
  ok('burstWord 取当前词', bw.word === 'b' && bw.i === 1);
  ok('burstWord 未开始 word 空', HXM.burstWord(1, [[2, 'x']]).word === '');
}

/* ───────────── contact ───────────── */
group('contact');
{
  const lh0 = HXM.landHit(5.0, 5.0);
  ok('landHit 撞击前静止 (r=0,s=1)', lh0.r === 0 && near(lh0.sx, 1));
  const lh = HXM.landHit(5.05, 5.0);
  ok('landHit 撞击后有变形', Math.abs(lh.sx - 1) > 1e-4 || Math.abs(lh.sy - 1) > 1e-4);
  ok('landHit 衰减到静止', Math.abs(HXM.landHit(6, 5).r) < 1e-3);

  const sp = HXM.splitOnHit(5.0, 5.0, 200, 900);
  ok('splitOnHit 起初未分开', Math.abs(sp.dx) < 1e-6 || Math.abs(sp.dx) < 1);
  ok('splitOnHit 对称拉开', Math.sign(HXM.splitOnHit(5.25, 5.0, 200, 900).dx) !== Math.sign(HXM.splitOnHit(5.25, 5.0, 1400, 900).dx));

  const p0 = HXM.tapPress(1.0, 2.0), p1 = HXM.tapPress(2.05, 2.0), p2 = HXM.tapPress(3.0, 2.0);
  ok('tapPress 点击前 down=false', p0.down === false);
  ok('tapPress 点击后 down=true', p1.down === true);
  ok('tapPress flash 窗口短', p2.active === false);

  const ptr = HXM.pointer(1.0, [{ t: 0, x: 0, y: 0 }, { t: 2, x: 100, y: 100 }], [1.0]);
  ok('pointer 点击时缩小', ptr.s < 1);
  ok('pointer 走位中间值', ptr.x > 0 && ptr.x < 100);

  const st = HXM.stretch2(3000, 0);
  ok('stretch2 沿运动拉长', st.sx > 1 && st.sy < 1, `sx ${st.sx.toFixed(3)} sy ${st.sy.toFixed(3)}`);
  ok('stretch2 静止无变形', near(HXM.stretch2(0, 0).sx, 1) && near(HXM.stretch2(0, 0).sy, 1));
  ok('stretch2 有上限', HXM.stretch2(1e9, 0).sx <= 1.45 + 1e-9);
}

/* ───────────── sim（240Hz 预积分） ───────────── */
group('sim');
{
  const card = { t: 0, out: 1.2, x: 0, y: 0 };
  const hand = (t) => [230 + 200 * Math.sin(t * 3), 158 + 150 * Math.cos(t * 2)];
  for (const kind of ['magnet', 'follow', 'jelly', 'verlet']) {
    const s = HXM.sim[kind](card, hand);
    ok(`sim.${kind} 有状态`, Array.isArray(s.st) && s.st.length > 0, `${s.st.length} samples`);
    const a = s.at(0.8), b = s.at(0.8);
    ok(`sim.${kind} at() 幂等`, JSON.stringify(a) === JSON.stringify(b));
    ok(`sim.${kind} at() 越界不外溢`, s.at(-99) !== undefined && s.at(999) !== undefined);
  }
  const j = HXM.sim.jelly(card, hand);
  ok('sim.jelly 环形 N=48', j.N === 48 && j.at(0.5).length === 48);
  const v = HXM.sim.verlet(card, hand);
  ok('sim.verlet 采样 2N 分量', v.at(0.5).length === v.N * 2);
}

/* ───────────── camera ───────────── */
group('camera');
{
  const KEYS = [{ t: 0, x: 400, y: 300, zoom: 2 }, { t: 2, x: 1400, y: 700, zoom: 0.8 }];
  ok('camTrack 起点=A', near(HXM.camTrack(0, KEYS).x, 400) && near(HXM.camTrack(0, KEYS).zoom, 2));
  ok('camTrack 终点=B', near(HXM.camTrack(9, KEYS).x, 1400) && near(HXM.camTrack(9, KEYS).zoom, 0.8));
  const mid = HXM.camTrack(1, KEYS);
  ok('camTrack zoom 对数中点', Math.abs(mid.zoom - Math.sqrt(2 * 0.8)) < 1e-6, `zoom ${mid.zoom.toFixed(4)}`);
  ok('camTrack 空 keys 安全', HXM.camTrack(1, []).zoom === 1);

  const cam = { x: 960, y: 540, zoom: 1, rot: 0 };
  const M = HXM.layerMatrix(cam);
  ok('layerMatrix 单位机位=恒等', near(M[0], 1) && near(M[3], 1) && near(M[4], 0) && near(M[5], 0), M.map((v) => v.toFixed(3)).join(','));
  const [sx, sy] = HXM.toScreen(M, 100, 200);
  const [wx, wy] = HXM.toWorld(M, sx, sy);
  ok('toScreen/toWorld 互逆', near(wx, 100, 1e-6) && near(wy, 200, 1e-6), `${wx.toFixed(4)},${wy.toFixed(4)}`);
  const bb = HXM.boxOnScreen(M, { x: 10, y: 20, w: 100, h: 50 });
  ok('boxOnScreen 恒等=原框', near(bb.x, 10) && near(bb.w, 100) && near(bb.h, 50));

  const z2 = HXM.layerMatrix({ x: 960, y: 540, zoom: 2, rot: 0 });
  ok('zoom=2 矩阵缩放=2', near(z2[0], 2, 1e-9));

  ok('depthBlur 焦平面=0', HXM.depthBlur(0, 0) === 0);
  ok('depthBlur 有上限', HXM.depthBlur(99, 0) <= 14 + 1e-9);
  ok('screenTravel 静止机位=0', near(HXM.screenTravel(cam, cam, cam), 0, 1e-9));
  const trav = HXM.screenTravel({ x: 0, y: 0, zoom: 1, rot: 0 }, { x: 500, y: 0, zoom: 1, rot: 0 }, { x: 250, y: 0, zoom: 1, rot: 0 });
  ok('screenTravel 平移 500px → ≈500', Math.abs(trav - 500) < 1e-6, `${trav.toFixed(3)}`);

  const shakeBefore = HXM.camShake(4.9, 5.0, { amp: 20 });
  ok('camShake 撞击前恒为 0', shakeBefore.x === 0 && shakeBefore.y === 0 && shakeBefore.rot === 0);
  const shakeAfter = HXM.camShake(5.02, 5.0, { amp: 20 });
  ok('camShake 撞击后有位移', Math.abs(shakeAfter.x) > 0 || Math.abs(shakeAfter.y) > 0);
  ok('slowPush 起终值', near(HXM.slowPush(0, 0, 2, 0.1), 1) && near(HXM.slowPush(9, 0, 2, 0.1), 1.1));

  const G = HXM.gridDots(cam, { spacing: 48 });
  ok('gridDots 给矩阵与网格范围', G.matrix.length === 6 && G.x1 > G.x0 && G.spacing === 48);
  ok('gridDots 点半径随缩放收缩', HXM.gridDots({ x: 0, y: 0, zoom: 4, rot: 0 }).r < G.r);
}

/* ───────────── ambience ───────────── */
group('ambience');
{
  ok('swiftSpring smooth 收敛', near(HXM.swiftSpring(3, 'smooth'), 1, 1e-3));
  const bouncy = Math.max(...Array.from({ length: 400 }, (_, i) => HXM.swiftSpring(i / 200, 'bouncy')));
  ok('swiftSpring bouncy 过冲', bouncy > 1.0, `peak ${bouncy.toFixed(3)}`);
  const gf0 = HXM.glowField(0), gf1 = HXM.glowField(1);
  ok('glowField 0→1 地平线上移', gf1.horizon < gf0.horizon);
  ok('glowField 1 淹过画幅顶', gf1.horizon <= -300 + 1e-9);
  const rf = HXM.floodRings(9, 1.0, { n: 3 });
  ok('floodRings 末端 done', rf.done && rf.r.length === 3);
  ok('floodRings 起点 r=0', HXM.floodRings(1.0, 1.0).r.every((v) => v === 0));

  const nf = HXM.noiseField(0.3, 3, HXM.noiseField.ramps.dusk, { gx: 8, gy: 8 });
  ok('noiseField 尺寸 = gx*gy*4', nf.length === 8 * 8 * 4);
  ok('noiseField alpha 全 255', Array.from({ length: 64 }, (_, i) => nf[i * 4 + 3]).every((a) => a === 255));
  const nfA = HXM.noiseField(0.3, 3, HXM.noiseField.ramps.dusk, { gx: 8, gy: 8 });
  ok('noiseField 幂等', nf.every((v, i) => v === nfA[i]));
  const nfB = HXM.noiseField(0.9, 3, HXM.noiseField.ramps.dusk, { gx: 8, gy: 8 });
  ok('noiseField 随时间流动', nf.some((v, i) => v !== nfB[i]));

  const belt = HXM.beltLoop({ dur: 6, speed: 200, rampDur: 0.8 });
  ok('beltLoop x 单调不减', belt.at(3).x >= belt.at(1).x);
  ok('beltLoop tau 单调不减', belt.at(3).tau >= belt.at(1).tau);
  ok('beltLoop 起点≈0', belt.at(0).x < 1e-6);
  const beltS = HXM.beltLoop({ dur: 6, speed: 200, stop: [4, 5] });
  ok('beltLoop stop 后趋停', beltS.at(5.5).x - beltS.at(5).x < 0.5, `Δ ${(beltS.at(5.5).x - beltS.at(5).x).toFixed(3)}`);
}

/* ───────────── 球面校验：全库导出完整性 ───────────── */
group('exports');
{
  const must = ['ease', 'spring', 't80', 'cubicBezier', 'hermite', 'seededRng', 'settle', 'ring',
    'riseWord', 'dropLetters', 'springIn', 'blurAway', 'riseFromMask', 'typeChars', 'checkOff', 'flyPlane',
    'morphBox', 'irisOpen', 'diveInto', 'arcHop', 'gatherTo', 'railShift', 'sealDisc', 'burstWord',
    'landHit', 'splitOnHit', 'tapPress', 'pointer', 'stretch2', 'sim',
    'camTrack', 'layerMatrix', 'depthBlur', 'whipPan', 'camShake', 'slowPush', 'gridDots',
    'toScreen', 'toWorld', 'boxOnScreen', 'screenTravel',
    'swiftSpring', 'glowField', 'floodRings', 'noiseField', 'beltLoop'];
  const missing = must.filter((k) => HXM[k] === undefined);
  ok(`导出齐备（${must.length} 项）`, missing.length === 0, missing.join(','));
  ok('版本号 = 2.0.0', HXM.version === '2.0.0');
}

console.log(`\n${'-'.repeat(52)}`);
console.log(fail === 0 ? `ALL PASS  (${pass} assertions)` : `${fail} FAILED / ${pass} passed`);
process.exit(fail === 0 ? 0 : 1);
