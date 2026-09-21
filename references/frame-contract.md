# 场景帧契约（frame-contract）

一个场景 = 一个自包含 HTML 文件 `frames/<id>.html`，1920×1080，GSAP 时间轴驱动。
渲染器逐帧 `tl.pause(t, false)` 确定性截图 —— 与实时录制的根本区别：**任何「依赖墙钟」的东西都会失控**。

> **画面从哪来？** 先看 **`references/style-catalog.md`** —— html-video 的 23 个模板风格
> （8 个类别，含每种画布/字体/时间轴/配色规范）。改编三步法与挑风格建议见
> **`references/template-guide.md`**。从零设计画面是最后选项，不是第一选项。

模板：`assets/frame-template.html`（复制后改内容，契约注释在文件头）。

## 八条硬性契约

| # | 契约 | 违反后果 |
|---|------|----------|
| 1 | 画布 1920×1080（或 project.json 声明的尺寸），系统字体栈 | 渲染视口即画布 |
| 2 | 绝不引外部字体/Google Fonts（渲染器 5s 字体硬顶） | 整帧退化或首帧字体错 |
| 3 | 颜色全部取 `../theme.css` 的 CSS 变量，禁止字面量 | 换主题 = 半换皮 |
| 4 | 动画只用 GSAP：`var tl = gsap.timeline({paused:true}); window.__tl = tl;` | 渲染器找不到时间轴 → 报错 |
| 5 | 节拍用 `B('块文本')` 对齐吐字 | 画面与配音两张皮 |
| 6 | 底部 80–170px 是字幕带，内容收在 `bottom ≥ 170px` | 字幕压字，两边都读不清 |
| 7 | 每帧一个视觉焦点：主角 ≥170px 或大字 ≥96px 带 accent 柔光；配角不发光；文字 ≥22px | QC 退回 |
| 8 | GSAP `<script src="../assets/gsap.min.js">`（本地内置），不引 CDN | 离线渲染失败 |

## 关于第 4 条的细节（最容易踩）

- **不要用 CSS transition 做入场**。transition 只在属性变化时触发一次，渲染器逐帧 seek 时根本不生效。
- **`@keyframes` 循环装饰（呼吸光、流光）可以用**：渲染器会同步 seek 所有 `document.getAnimations()`（`currentTime = t×1000`），确定性的。
- GSAP 时间轴**注册后不要自己 play**。渲染器下（`window.__MG_RENDER__` 已置位）由渲染器逐帧 seek；浏览器直接打开预览时才自动起播：

```js
if (!window.__MG_RENDER__) {
  requestAnimationFrame(function(){ requestAnimationFrame(function(){ tl.play(0); }); });
}
```

- **★ 数字滚动不要用 `onUpdate` 写 DOM**。GSAP `pause(atTime, suppressEvents)` 第二参默认 `true`，
  渲染器 seek 时**会掐掉本次触发的 `onUpdate`/`onComplete`** → `textContent` 永远停在初值（不报错、成片数字不动）。
  渲染器已显式传 `pause(t, false)` 修好根因，但**帧里仍推荐用纯 transform 驱动的「数字卷轴」**——
  它不依赖任何回调，浏览器预览 / 任何 seek 方式都成立。**绝不**用 `setInterval`/`requestAnimationFrame` 计数
  （墙钟，必然失控）。

  ```html
  <!-- 数字卷轴：外层裁剪，内层按 ITEM 高位移，终值 = 0 时露出目标数字 -->
  <div class="strip"><span class="val">0<br>1<br>…<br>100</span></div>
  ```
  ```js
  // inline 元素不吃 transform → .strip>.val 必须 display:block
  tl.fromTo('.strip .val', { y: 0 }, { y: -(steps * ITEM), duration: 1.4, ease: 'power2.out' }, B('…'));
  ```
  参考实现见 `references/workflow-guide.md` 附的「数字卷轴」最小示例。

- 一个帧只注册一条主时间轴（`window.__tl`）。需要多段编排就放进同一条 timeline（用 label/position 参数）。

## 第 5 条：B() 节拍器

`frames/<id>.beats.js` 由 `subs.py` 生成（解说词改动 → 重跑 tts+subs → 时间自动刷新，帧代码零改动）：

```js
tl.fromTo('.card', {...}, {..., duration: 0.7}, B('右边卡片'));     // 该块起播秒
tl.fromTo('.verdict', {...}, {..., duration: 0.7}, B('结论句') + 0.2);
var tEnd = Be('证据');                                              // 该块收尾秒
```

- 参数是**字幕块的原文片段**（带标点也行，匹配时自动去标点）；找不到会抛错——宁可构建失败也不要静默错位。
- 兜底写法 `B('X') || 3.2` **禁止**：beats 缺失时要在构建期暴露，不是悄悄用旧数字。
- `window.__SEG__`：`{id, duration, speech_end, tail}` —— 帧尾呼吸：主体动画压在 `speech_end` 前，`duration - speech_end`（约 0.1–0.3s）留给静止收尾。

## 渲染器注入的东西（帧作者零负担）

| 层 | 说明 |
|----|------|
| `#mg-subs` | 硬字幕层（44px 白字黑边、bottom 96px、单帧硬切）——按 subs.json 块表逐帧切换 |
| `#mg-progress` | 全局进度条（bottom 0–12px、accent 填充、章节刻度）——按全局时间填充 |

两者 z-index 900/901，`pointer-events:none`。**内容区别压进字幕带（80–170px），进度条带（0–12px）也别放东西。**

## 版式基因（来自 html-video 模板一系，可自由组合）

- **幕底**：`--bg-radial`（主题径向光）+ 96px 网格（`--line-soft`）；整片常驻不被盖
- **卡片**：24px 圆角、`--card-bg` 底、`--line` 描边；重点卡用 `--accent-soft` 底 + `--accent-border` 描边 + inset 柔光
- **大字**：74–130px / 900 字重；关键词用 `<em>` + `--accent` + 发光
- **章节角标**：`--accent` 小字 + 短横条（配角，不发光）
- **证据条**：`bottom:176px`、左侧 5px accent 竖条 + tag 胶囊（事实必须带调研出处）
- **动效词汇**：入场 `power3.out` 位移 0.6–0.7s / 强调 `back.out(1.7~2)` 缩放 / 结论光晕 `sine.out` 0.8s / 划线强调 `power3.inOut`
- 数字大特写（高光时刻）：140–180px 数字 + 计数动画（**必须用上面的 transform 数字卷轴，不用 onUpdate**）+ 全屏 `--accent` 柔光

## 反例（QC 会退回）

- 同屏 3+ 个都发光的元素（光只跟主角）
- 背景撒碎屑/小图标墙（背景只有幕底+网格）
- 字幕带里放 footnote/evidence（`bottom < 170px` 的元素一律抬走）
- 文字 < 22px（投影后不可读）
- 入场轨迹穿过字幕带（路径先抬后落）
