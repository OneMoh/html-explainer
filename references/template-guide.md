# 模板改编指南（html-video 模板 → html-explainer 帧）

本技能的画面语言来自 html-video 的 **23 个模板 / 8 个类别**。
`references/style-catalog.md` 是完整目录，本页讲**怎么把它变成合规帧**。

## 一、先看模板属于哪一类

| 类型 | 数量 | 结构 | 处理方式 |
|---|---|---|---|
| **★ rich** | 12 | 单文件 + 纯 CSS `@keyframes`；带完整风格规范 | **几乎零改动**：换字体栈 + 让出字幕带 + 填内容 |
| **gsap** | 11 | 多 composition + CDN GSAP，或 Remotion 引擎 | 需**重写为单文件**（照风格规范复刻，不要搬代码）|

判断方法：`references/style-catalog.md` 速查表的「类型」列，或看 JSON 目录的 `kf` 字段
（`kf≥1` 且 `multi=false` 且 `engine≠remotion` = rich）。

## 二、rich 模板改编（三步）

### 第 1 步：换字体栈（必须）

模板原文一律 `<link href="https://fonts.googleapis.com/...">`。
**必须删掉**，换成系统字体栈 —— 这是离线渲染的硬要求（详见 `lessons.md` #8）。

```css
:root{
  /* 中文优先的系统栈；display 用 Impact/Arial Black 兜住"超大粗体"的观感 */
  --font-display: "Impact", "Arial Black", "Microsoft YaHei", "PingFang SC", sans-serif;
  --font-body: -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
}
```

然后把模板里的 `font-family: 'Archivo Black'` 等替换为 `var(--font-display)`。

### 第 2 步：让出字幕带

模板不知道自己会被叠字幕。**底部 80–170px 是字幕带，不许放内容**。

模板里的 `bottom: 74px` / `bottom: 92px` / `bottom: 104px` 这类值一律抬到
`bottom: 176–210px`。参考 `lessons.md` #10。

### 第 3 步：填真实内容

从模板的 `example.md` 看它期待哪些字段（如 bold-signal 要 `section` / `nav` /
`card_label` / `title`）。**必须用真实内容，严禁 lorem ipsum。**

## 三、gsap 模板改编（重写，不搬代码）

多 composition + GSAP 的结构在单帧里**没有起播钩子**，直接搬进 seek 渲染器会得到
静止首帧、且零报错（这正是 `lessons.md` #9 的 `__hvUnfreeze` 整类坑）。

正确做法：**只取它的视觉 DNA，用纯 CSS keyframes 重新表达。**

1. 读 `source/index.html` 或 `index.html` + `compositions/*.html`，提取：
   - 配色（源码里的 `#RRGGBB`；目录 JSON 的 `colors` 字段已给线索）
   - 字号层级 / 版式骨架（元素位置、栅格）
   - 动效意图（谁先入场、位移方向、缓动感觉）
2. 用 CSS `@keyframes` + `animation-delay` 重写成单文件时间轴。
   **`animation-delay` 就是时间轴** —— seek 渲染器靠它确定每一时刻的状态。
3. 若确需 GSAP：用本技能内置的 `assets/gsap.min.js`（离线），
   并把时间轴注册到 `window.__tl`（见 `references/frame-contract.md` 契约 2）。

## 四、挑风格的实用建议

| 内容需求 | 推荐风格 |
|---|---|
| 开场 / 章节分隔 | `frame-bold-signal`（橙卡滑入）、`frame-bold-poster`（海报大字） |
| 高级感 / 极简 | `frame-build-minimal`（70% 留白 + 暖金细线） |
| 单个关键数字 | `frame-pentagram-stat`（瑞士网格 + 巨型数字）、`frame-nyt-graph` |
| 数据对比 / 趋势 | `frame-data-chart-nyt`（NYT 编辑级图表） |
| 概念关系 / 流程 | `frame-takram-organic`（柔和有机）、`frame-decision-tree`（分支流程） |
| 科技 / 赛博 | `frame-glitch-title`（故障艺术）、`vfx-text-cursor`（光标拖光） |
| 金句 / 引用 | `frame-electric-studio`（白蓝分屏引言） |
| 收尾 / 品牌 | `frame-logo-outro`（Logo 组装 + glow） |
| 电影感空镜 | `frame-light-leak-cinema`（漏光 + 颗粒 + letterbox） |

> 挑风格时**同时看时长档**：`frame-bold-signal` 是 3–6s 的短片花，
> 硬拉到 20s 会显得空。长段（>10s）优先 `frame-swiss-grid` /
> `frame-kinetic-type` / `frame-nyt-graph` 这类 3–30s 档。

## 五、改编后的自检

```bash
# 单帧渲染验证（不必等整片）
node scripts/render_video.mjs <项目> --preview 5
# 抽帧看：字体是否本地、字幕带是否干净、动画是否真的在动
```

字幕带检查：抽一帧，确认底部 80–170px 区间内没有任何内容元素。
