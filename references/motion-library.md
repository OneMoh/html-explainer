# 动效库 —— `assets/motion.js`（v2.0）

> 一句话：**把「镜头语言」变成时间的纯函数**。每个动作都是 `t`（绝对秒）→ 一组数字。
> 库不碰 DOM、不碰 canvas，无状态、无构建步骤，因此可以被**逐帧 seek**：同样的 `t` 永远给出同样的数。

---

## 1. 为什么需要它

讲解视频的动效默认只有两种写法：CSS `@keyframes`（做不了承接和物理）和 GSAP 手写时间轴
（每期重写一遍，且**非确定性**——实时播放和逐帧渲染结果不一致）。

本库把 23 个模板里反复用到的动作抽象成**动作词汇**，每期只需挑选、组合、调参：

- **确定性**：所有随机数走 `seededRng`，渲染路径上不出现 `Math.random()`。同一 `t` 同一样式，逐帧渲染与实时预览一致。
- **可组合**：动作是纯函数，可以叠加（弹簧 + 镜头 + 环境光 = 三层各自算，最后一个 `transform` 相乘）。
- **可测**：库里没有任何副作用，所以 `tests/test_motion.mjs` 能对它做 148 条断言。

---

## 2. 引入方式

```html
<!-- 浏览器（file:// 下不能用 ES module）：挂到 window.HXM -->
<script src="../assets/motion.js"></script>
<script>
  const HXM = window.HXM;
  function __seek(t) { /* 用 HXM.* 算出本帧样式 */ }
</script>
```

```js
// Node（跑自测 / 预计算）：
const HXM = require('./assets/motion.js');
```

---

## 3. 场景契约（渲染器只依赖这三条）

| 钩子 | 作用 |
|---|---|
| `window.__seek(t)` | 设置 `t` 时刻的**全部**样式。渲染器每帧调一次，必须在同一帧内把所有元素都定到 `t` 上 |
| `window.__ready` | 字体就绪后 measure/simulate，再 `seek(0)`。渲染器等到它为真才开始抓帧 |
| `window.__meta` | `{ dur, fps, w, h, inFrame? }` |

可选（但强烈建议）：

| 钩子 | 作用 |
|---|---|
| `window.__motion(t0, t1)` | 返回 `t0→t1` 区间内**屏幕最远位移**（px，含运镜）。渲染器据此决定这一帧要不要开快门、开几次 |

---

## 4. 曲线（curves）

时序的基础层。所有 `tween` / 弹簧都从这里取。

### 4.1 `ease` 缓动表

| 键 | 特征（t80 = 走完 80% 的进度） | 用在 |
|---|---|---|
| `linear` | 匀速 | 进度条、无限滚动 |
| `smooth` / `smoother` | 两端慢 | 通用位移 |
| `sineInOut` / `cubicInOut` / `quintInOut` | 由软到硬 | 运镜、卡片位移 |
| `quadOut` `cubicOut` `quartOut` `quintOut` | 由软到硬（出场） | 元素入场 |
| `expoOut` | 极快起、长尾收（t80 ≈ .23） | **默认入场曲线** |
| `expoIn` / `expoInOut` | 极快收 | 退场、运镜加速 |
| `circOut` | 圆滑刹车 | 弹出 |
| `backOut` | 轻微过冲 | 强调 |
| `back(s)` | **工厂函数**：`back(2.2)` 返回一条过冲更猛的曲线 | 需要自定义过冲量时 |

> `back` 是唯一需要"调用两次"的曲线：`ease.backOut(u)` 直接用，`ease.back(2.2)(u)` 才是自定义版。

### 4.2 结构化曲线

| 函数 | 签名 | 说明 |
|---|---|---|
| `cubicBezier(x1,y1,x2,y2)` | → `curve` | 把 CSS `cubic-bezier(...)` 号直接落地成 JS 曲线 |
| `tween(t, t0, t1, curve?)` | → 0..1 | **最常用的入口**：`ease.expoOut` 默认 |
| `t80(curve, frac?, steps?)` | → 数值 | 量「这条曲线走完 `frac` 用了多少归一化时间」，用于对齐时长 |
| `spring(tau, zeta?, omega?)` | → 0..1 | 阻尼弹簧的**位移**，`tau` 是自起点起的秒数 |
| `springVel(tau, zeta?, omega?)` | → 速度 | 弹簧的导数，用于挤压拉伸、判断是否还在动 |
| `ring(tau, decay?, omega?)` | → 幅度 | 衰减振荡，做"叮"的余振 |
| `settle(zeta?, omega?, eps?)` | → 秒 | **弹簧多久停**（算 hold 长度、决定该帧是否为静止帧） |
| `hermite(knots, t)` | → {x,y} | 过控制点的平滑插值，做手绘路径 / 自定义运镜轨迹 |
| `seededRng(seed)` | → `() => 0..1` | 确定性随机源。**渲染路径上唯一允许的随机** |

---

## 5. 动作词汇（按叙事阶段分组）

一共 5 组，每一组对应"画面上正在发生什么"。

### 5.1 `enter` —— 某样东西到场

| 动作 | 签名要点 |
|---|---|
| `riseWord(t, t0, opts)` | 词从下方"落下"并微弱淡入。**慢动作别用纯 opacity 淡入**，会读成 PPT |
| `dropLetters(t, t0, i, opts)` | 逐字落下 + 落地挤压。`dt` 控制错峰间隔 |
| `springIn(t, t0, opts)` | 元素整体弹簧进场（`rise` 抬升高度、`s0/ds` 起始缩放） |
| `blurAway(t, t1, opts)` | 退场：位移 + 模糊 + 微放大。`dir` 决定往哪边糊掉 |
| `riseFromMask(t, t0, i, opts)` | 从蒙版后升起（配合 `clip-path`），比淡入"有实感" |
| `typeChars(t, t0, text, opts)` | 打字机。`cps` 字/秒、`blink` 光标闪烁 |
| `checkOff(t, tl, opts)` | 勾选：过冲 + 回弹，落笔果断 |
| `flyPlane(t, t0, hold, opts)` | 平面飞入 → 停留 → 飞出（`from/to/exit` 三态），做"穿屏" |

### 5.2 `carry` —— 下一镜从这个镜里长出来

> **纪律**：一个 beat 不许"替换"上一个，必须让某个元素**跨过边界继续动**。

| 动作 | 说明 |
|---|---|
| `morphBox(t, t0, t1, A, B, opts)` | 矩形 A 变形成矩形 B（位置+宽高+转角）——最基础的承接 |
| `irisOpen(t, t0, t1, cx, cy, opts)` | 以某点为心开光圈（虹膜展开），把上一镜"揭"开 |
| `diveInto(t, t0, t1, target, opts)` | 镜头扎进某个矩形（`fit:'cover'/'contain'`），做"放大进入细节" |
| `arcHop(t, t0, t1, from, to, opts)` | 抛物弧线跳（`height` 弧高），比直线位移有生命感 |
| `gatherTo(t, t0, t1, i, n, from, to, opts)` | n 个元素错峰汇聚到一点（`arc` 弧、`spin` 自旋） |
| `railShift(t, switches, opts)` | 轨道换挡：切换瞬间整车抖动（`amp` 幅度、`tilt` 倾斜） |
| `sealDisc(t, t0, t1, opts)` | 圆形封印/合拢（`turns` 圈数） |
| `burstWord(t, list)` | 爆发式短语序列：`[{t, text, ...}]`，做标题弹幕 |

### 5.3 `contact` —— 一件事引发另一件

| 动作 | 说明 |
|---|---|
| `landHit(t, tHit, opts)` | 落地撞击：`decay/omega` 衰减振荡，`sqx/sqy` 挤压量 |
| `splitOnHit(t, tHit, x, cx, opts)` | 撞击瞬间把一条线/字炸开（`spread` 散开、`rot` 旋转、`falloff` 衰减） |
| `tapPress(t, tc, opts)` | 点击反馈：`depth` 下压、`flash` 高光闪。配 UI 音 |
| `pointer(t, knots, clicks, opts)` | 光标沿路径移动 + 沿路点击（`down` 按下深度） |
| `stretch2(vx, vy, opts)` | 速度 → 拉伸（橡皮感）。`k/max` 控制强度上限 |
| `sim.*` | 物理仿真工具集：`magnet`（磁吸）/ `follow`（跟随+边界）/ `jelly`（软体抖动）/ `verlet`（绳索、布料） |

### 5.4 `camera` —— 运镜

| 动作 | 说明 |
|---|---|
| `camTrack(t, keys, opts)` | 关键帧运镜（`keys = [{t,x,y,zoom}]`），出 `camera` 状态 |
| `layerMatrix(cam, opts)` | 相机状态 → 某深度层的 `transform` 矩阵（`depth` 视差） |
| `depthBlur(depth, focus?, opts)` | 按深度算虚化量（合焦处为 0） |
| `whipPan(t, t0, dur, dist, opts)` | 甩镜：快速横向撕裂，**必须开快门**才不跳 |
| `camShake(t, tHit, opts)` | 撞击相机抖动（确定性 seed） |
| `slowPush(t, t0, t1, amount?)` | 极缓推镜（默认 +7%），长镜头不静止 |
| `gridDots(cam, opts)` | 背景网格点随相机视差移动，给运镜"刻度感" |
| `toScreen/toWorld/boxOnScreen/screenTravel` | 世界↔屏幕坐标互转、把一个盒子的屏幕位置/移动量算出来 |

> `screenTravel(c0, c1, cMid?, opts)` 是给 `__motion()` 用的：**它直接返回这段运镜在屏幕上走了多少 px**，渲染器据此决定快门样本数。

### 5.5 `ambience` —— 环境与光

| 动作 | 说明 |
|---|---|
| `swiftSpring(tau, kind?, opts)` | 位移弹簧的可控封装（`kind:'smooth'`，`bounce` 覆盖） |
| `glowField(level, opts)` | 顶部光晕强度（`rest` 静息、`top` 高度、`r0/r1` 半径） |
| `floodRings(t, t0, opts)` | 涟漪环扩散（`n` 环数、`dt` 错峰、`rMax` 最大半径） |
| `noiseField(tau, seed?, stops?, opts)` | 流动噪声场（返回 RGBA 像素，`gx×gy` 网格） |
| `noiseField.ramps` | 5 套色带：`ember / peach / dusk / deep / sage` |
| `beltLoop(opts)` | 无缝循环的传送带 / 走马灯（`speed`、`rampDur` 起停） |

---

## 6. 完整示例

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html,body{margin:0;background:#0e1116;overflow:hidden}
  #stage{position:relative;width:1920px;height:1080px;font-family:system-ui}
  .word{position:absolute;left:160px;color:#f2f4f8;font-size:96px;font-weight:700;
        opacity:0;will-change:transform,opacity}
  #disc{position:absolute;left:760px;top:380px;width:400px;height:400px;border-radius:50%;
        background:radial-gradient(circle at 35% 30%, #7c5cff, #2a1d5e)}
</style></head>
<body>
<div id="stage">
  <h1 class="word" id="w1" style="top:300px">一款药</h1>
  <h1 class="word" id="w2" style="top:430px">要烧掉 26 亿美元</h1>
  <div id="disc"></div>
</div>
<script src="../assets/motion.js"></script>
<script>
const HXM = window.HXM, DUR = 6.0;
const w1 = HXM.riseWord, disc = document.getElementById('disc');

function __seek(t) {
  // 1) 错峰起字（riseWord → { k, op, y, s }）
  const a = HXM.riseWord(t, 0.20, { dist: 26 });
  const b = HXM.riseWord(t, 1.10, { dist: 26 });
  Object.assign(document.getElementById('w1').style,
    { transform: `translateY(${a.y}px) scale(${a.s})`, opacity: a.op });
  Object.assign(document.getElementById('w2').style,
    { transform: `translateY(${b.y}px) scale(${b.s})`, opacity: b.op });

  // 2) 圆盘砸入 + 落地挤压（contact 接到 enter 上；landHit → { r, sx, sy }）
  const drop = HXM.spring(t - 1.10, 0.62, 18);
  const hit  = HXM.landHit(t, 1.10, { sqx: 0.13, sqy: 0.16 });
  disc.style.transform =
    `translateY(${(1 - drop) * -260}px) scale(${hit.sx}, ${hit.sy})`;

  // 3) 缓推镜，让整场不静止
  const push = HXM.slowPush(t, 0, DUR, 0.06);
  document.getElementById('stage').style.transform = `scale(${push})`;
}

// 告诉渲染器：这段哪些区间有大位移（决定快门样本数）
window.__motion = (t0, t1) => {
  const a = HXM.spring(t1 - 1.10, 0.62, 18) - HXM.spring(t0 - 1.10, 0.62, 18);
  return Math.abs(a) * 260;
};
window.__meta = { dur: DUR, fps: 30, w: 1920, h: 1080 };
document.fonts.ready.then(() => { __seek(0); window.__ready = true; });
</script>
</body></html>
```

---

## 7. 纪律清单（每条都是踩坑换来的）

1. **慢动作别用纯 opacity 淡入** —— 用带位移的弹簧"落下"（`riseWord`），否则读起来像 PPT。
2. **一个 beat 不许替换上一个** —— 必须让某个元素跨过边界继续动（`morphBox` / `irisOpen` / `camTrack`）。
3. **快动作必须开快门** —— 超过 80 px/帧 不开运动模糊就会重影（`render_video.mjs --shutter`）。
4. **所有随机数从固定种子出**（`seededRng`），渲染路径上不许出现 `Math.random()`。
5. **`__seek(t)` 必须覆盖全部元素** —— 漏掉的元素会保留上一帧的状态，逐帧渲染下表现为"拖影"。
6. **长镜头用 `slowPush`** —— 超过 3 秒画面完全静止，观众会以为卡了。

---

## 8. 自测

```bash
node tests/test_motion.mjs      # 148 条断言：曲线端点、弹簧收敛、确定性、坐标互转
```

测试覆盖：`ease.*` 全部曲线端点 0→1、`back` 工厂语义、`spring` 收敛与过冲、`seededRng` 可重复、
`springVel` 与数值微分一致、`toScreen/toWorld` 往返一致、`screenTravel` 单调。
