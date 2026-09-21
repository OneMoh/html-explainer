# 画面风格目录（从 html-video 模板库导入）

> **这是风格知识，不是代码依赖。**
> html-explainer 运行时不引用 html-video 仓库；本目录用于挑选画面语言，
> 复刻时须由 agent 改写成「离线 + 纯 CSS keyframes + 字幕带禁区」的合规帧。
> 复刻契约见 `references/frame-contract.md`；本目录由 `scripts/import_styles.py` 生成。

共 **23** 个风格，覆盖 8 个类别。

### 两类模板（复刻成本不同，先看这个）

| 类型 | 数量 | 结构 | 适配 seek 渲染器 |
|---|---|---|---|
| **rich（推荐）** | 12 | 单文件 + 纯 CSS `@keyframes` 时间轴；带完整风格规范（时间轴/配色/字体）| **零改动可渲染**，只需换字体栈 + 让出字幕带 |
| **gsap** | 11 | 多 composition + CDN 加载 GSAP | 须重写为单文件 + 本地 GSAP（见 `lessons.md` #9 的 `__hvUnfreeze` 整类坑）|

> **rich 为什么零改动可用**：seek 渲染器用 `document.getAnimations().currentTime = t*1000` 驱动 CSS 动画，时间轴已由 CSS `animation-delay` 声明，天然确定性。gsap 型的多 composition 结构在单帧里没有起播钩子，正是 `__hvUnfreeze` 静默失败的来源。

## 速查表

| id | 名称 | 类别 | 时长档 | 画幅 | 类型 | 说明 |
|---|---|---|---|---|---|---|
| `frame-bold-poster` | 🟥 大胆海报帧 | 演示 / 标题卡/statement-title | 4–6s | 16:9 · 9:16 · 1:1 | ★rich | 大胆海报帧:1970s 欧洲社论海报风 + 番红强调色 + 巨型倾斜 Shrik |
| `frame-bold-signal` | 🔶 大胆信号卡帧 | 演示 / 标题卡/section-title | 3–6s | 16:9 · 9:16 · 1:1 | ★rich | 大胆信号卡帧:暗渐变底 + 大编号 + 导航面包屑 + 橙色卡片滑入 + 标题升 |
| `frame-build-minimal` | ◇ 奢华极简留白帧 | 演示 / 标题卡/hero | 4–7s | 16:9 · 1:1 | ★rich | 奢华极简留白帧:单词逐字浮现 + 暖金细线 + 呼吸感细线指示器, 70%+ 留 |
| `frame-creative-voltage` | ⚡ 创意电压分屏帧 | 演示 / 标题卡/title-card | 3–6s | 16:9 · 1:1 | ★rich | 创意电压分屏帧:电光蓝/暗错位分屏滑入 + 描边电光词 + 手写 script  |
| `frame-data-chart-nyt` | 📈 NYT 风数据图表帧 | 数据可视化/bar-chart | 5–20s | 16:9 · 9:16 · 1:1 | ★rich | NYT-newsroom 排版 + 错峰揭示动画 + 编辑级图表 (折线/柱/范 |
| `frame-data-rollup` | 📊 数据滚动帧 | 数据可视化/bar-chart | 3–8s | 16:9 · 9:16 · 1:1 | gsap | 数据滚动帧:原生 Remotion 数据动画 — 柱子按真实数据用 spring |
| `frame-decision-tree` |  Decision Tree | 图解 / 流程/flowchart | 3–30s | 16:9 | gsap | Animated flowchart with branching paths |
| `frame-electric-studio` | 🔷 电光工作室分屏帧 | 演示 / 标题卡/quote-card | 3–6s | 16:9 · 1:1 | ★rich | 电光工作室分屏帧:白/蓝双屏从中心开合 + 强调条生长 + 引言逐行浮现, 高对 |
| `frame-glitch-title` | ⚡ 故障艺术标题帧 | 演示 / 标题卡/text-card | 3–8s | 16:9 · 9:16 · 1:1 | ★rich | 数字故障 / 像散偏移 / 数据腐败标题, 适合视频转场 / cyberpunk |
| `frame-kinetic-type` |  Kinetic Type | 演示 / 标题卡/text-card | 3–30s | 16:9 | gsap | Bold kinetic typography promo |
| `frame-light-leak-cinema` | 🎞️ 胶片漏光电影帧 | 氛围 / 空镜/cinematic | 4–10s | 16:9 · 9:16 · 1:1 | gsap | 胶片漏光 + 颗粒噪点 + 16:9 letterbox + 衬线大字, 电影感 |
| `frame-liquid-bg-hero` | 🌊 流体背景 Hero 帧 | 营销 / Hero/hero | 4–12s | 16:9 · 9:16 · 1:1 | ★rich | WebGL 风流体置换背景 + 顶部叠加金句, 适合视频片头 / landing |
| `frame-logo-outro` | 🎬 品牌 Logo 收尾帧 | 片头片尾/outro | 3–10s | 16:9 · 9:16 · 1:1 | ★rich | Logo 分块组装入场 + glow bloom + tagline 揭示, 适 |
| `frame-nyt-graph` |  NYT Graph | 数据可视化/editorial | 3–30s | 16:9 | gsap | Animated data chart in print editorial s |
| `frame-pentagram-stat` | 📊 瑞士网格数据帧 | 数据可视化/stat-card | 3–6s | 16:9 · 1:1 | ★rich | 瑞士网格数据帧:巨大数字锚点 + 红色强调 + 生长条形图 + 黑色数据底栏,  |
| `frame-play-mode` |  Play Mode | 社媒竖版/playful | 3–30s | 16:9 | gsap | Playful elastic animations |
| `frame-product-promo` |  Product Promo | 产品演示/multi-scene | 3–30s | 16:9 | gsap | Multi-scene product showcase with SVG as |
| `frame-product-promo-30s` |  Product Promo · 30s | 产品演示/multi-scene | 25–35s | 16:9 | gsap | Multi-scene 30-second product promo: pro |
| `frame-swiss-grid` |  Swiss Grid | 演示 / 标题卡/corporate | 3–30s | 16:9 | gsap | Structured grid layout |
| `frame-takram-organic` | 🌿 东方柔和有机帧 | 图解 / 流程/concept-diagram | 4–7s | 16:9 · 1:1 | ★rich | 东方柔和有机帧:毛玻璃圆角卡 + 曲线连接描入 + 放射节点弹出 + 柔和漂浮, |
| `frame-vignelli` |  Vignelli | 社媒竖版/portrait-bold | 3–30s | 9:16 | gsap | Bold typography with red accents |
| `frame-warm-grain` |  Warm Grain | 演示 / 标题卡/hero | 3–30s | 16:9 | gsap | Cream aesthetic with grain texture |
| `vfx-text-cursor` | ✨ VFX 文字光标 | 演示 / 标题卡/text-card | 3–10s | 16:9 · 9:16 · 1:1 | ★rich | 光标拖光 + 彩色像散射线 + 定向光斑, 适合视频片头逐字揭示金句 |

## 按用途挑风格

### 氛围 / 空镜

- **`frame-light-leak-cinema`** — 胶片漏光电影帧
  - 胶片漏光 + 颗粒噪点 + 16:9 letterbox + 衬线大字, 电影感开场 / 章节卡

### 数据可视化

- **`frame-data-chart-nyt`** — NYT 风数据图表帧
  - NYT-newsroom 排版 + 错峰揭示动画 + 编辑级图表 (折线/柱/范围带)
- **`frame-data-rollup`** — 数据滚动帧
  - 数据滚动帧:原生 Remotion 数据动画 — 柱子按真实数据用 spring 从 0 长上去、数字同步从 0 滚到目标值。静态 HTML 图表做不出的'数字活起来'效果。
- **`frame-nyt-graph`** — NYT Graph
  - Animated data chart in print editorial style
- **`frame-pentagram-stat`** — 瑞士网格数据帧
  - 瑞士网格数据帧:巨大数字锚点 + 红色强调 + 生长条形图 + 黑色数据底栏, 理性克制的编辑风

### 图解 / 流程

- **`frame-decision-tree`** — Decision Tree
  - Animated flowchart with branching paths
- **`frame-takram-organic`** — 东方柔和有机帧
  - 东方柔和有机帧:毛玻璃圆角卡 + 曲线连接描入 + 放射节点弹出 + 柔和漂浮, 米色自然色调

### 片头片尾

- **`frame-logo-outro`** — 品牌 Logo 收尾帧
  - Logo 分块组装入场 + glow bloom + tagline 揭示, 适合视频片尾 / 品牌闭幕

### 营销 / Hero

- **`frame-liquid-bg-hero`** — 流体背景 Hero 帧
  - WebGL 风流体置换背景 + 顶部叠加金句, 适合视频片头 / landing hero / 海报

### 演示 / 标题卡

- **`frame-bold-poster`** — 大胆海报帧
  - 大胆海报帧:1970s 欧洲社论海报风 + 番红强调色 + 巨型倾斜 Shrikhand 大字 + 三行标题逐行升起 + 衬线斜体副题, 印刷质感强。
- **`frame-bold-signal`** — 大胆信号卡帧
  - 大胆信号卡帧:暗渐变底 + 大编号 + 导航面包屑 + 橙色卡片滑入 + 标题升起, 高冲击力
- **`frame-build-minimal`** — 奢华极简留白帧
  - 奢华极简留白帧:单词逐字浮现 + 暖金细线 + 呼吸感细线指示器, 70%+ 留白
- **`frame-creative-voltage`** — 创意电压分屏帧
  - 创意电压分屏帧:电光蓝/暗错位分屏滑入 + 描边电光词 + 手写 script 自描, 复古现代有活力
- **`frame-electric-studio`** — 电光工作室分屏帧
  - 电光工作室分屏帧:白/蓝双屏从中心开合 + 强调条生长 + 引言逐行浮现, 高对比专业感
- **`frame-glitch-title`** — 故障艺术标题帧
  - 数字故障 / 像散偏移 / 数据腐败标题, 适合视频转场 / cyberpunk hero
- **`frame-kinetic-type`** — Kinetic Type
  - Bold kinetic typography promo
- **`frame-swiss-grid`** — Swiss Grid
  - Structured grid layout
- **`frame-warm-grain`** — Warm Grain
  - Cream aesthetic with grain texture
- **`vfx-text-cursor`** — VFX 文字光标
  - 光标拖光 + 彩色像散射线 + 定向光斑, 适合视频片头逐字揭示金句

### 产品演示

- **`frame-product-promo`** — Product Promo
  - Multi-scene product showcase with SVG assets
- **`frame-product-promo-30s`** — Product Promo · 30s
  - Multi-scene 30-second product promo: problem-type intro, brand reveal, benefits flowchart, product surfaces, value pillars, foundation, CTA outro. Forked from Nate Herk's hyperframes-student-kit (linear-promo-30s); brand-specific copy + assets replaced with generic placeholders.

### 社媒竖版

- **`frame-play-mode`** — Play Mode
  - Playful elastic animations
- **`frame-vignelli`** — Vignelli
  - Bold typography with red accents

## 风格基因（复刻依据）

每个风格给出画布 / 字体 / 时间轴 / 配色纪律 —— 这四项足以复刻视觉签名。

### 🟥 `frame-bold-poster` — 大胆海报帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：9
- **时长档**：4–6s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：Brand manifesto / vision statement；Editorial or cultural pitch opener；A few words that should feel like a magazine cover
- **源码色值线索**：#1C1410 #D8000F #F5F2EF
- **画布**：1920×1080, 暖白纸底 `#F5F2EF`。
- **字体**：display + 数字 `Shrikhand` (海报级斜体大字); body `Libre Baskerville` (衬线, 斜体副题); mono 标签 / chrome `Space Grotesk`。
- **时间轴**：- **0.35s** 纸底淡入 (印刷感的"落纸"而非"打光")。 - **0.5s 起** 顶部 kicker: 左 mono 标签淡入 → 番红 rule 从左 scaleX 划过 → 右 mono 日期淡入。 - **0.7s** 右上巨型番红 figure (`Shrikhand` 320px) 带旋转 (-14° → -6°) 从上落入。 - **1.15s 起** 三行标题逐行升起, 每行各自 tilt: 行1 墨黑 -2°、行2 番红 -4°、行3 墨黑 +2°。 - **1.95s** 衬线斜体副题 (`Libre Baskerville` italic) fadeUp。 - **2.15s** footer 墨黑 rule 划入 + mono metadata 淡入。
- **配色纪律**：纸白 `#F5F2EF` / 墨黑 `#1C1410` / **唯一强调色番红 `#D8000F`**。红色只用在: 一条 kicker rule、巨型 figure、标题中间行、footer 右侧 metadata。其余皆墨黑。全片**只此一个**强调色。
- **内容纪律**：- headline 最多 3 行, 第 2 行自动番红; 必须真实标题, 严禁 lorem ipsum。 - 版式为"少量大字陈述", 不适合塞段落 — 信息密度高的内容请换模板。 - CJK 文本: letter-spacing 归 0、放松行高、不要对 CJK 做 uppercase。 - 动效用 `@keyframes`, `prefers-reduced-motion` 下全部停在终态。 - 单文件 HTML, 字体走 Google Fonts。

### 🔶 `frame-bold-signal` — 大胆信号卡帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：6
- **时长档**：3–6s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：Section / chapter divider；Bold launch statement；High-impact title card
- **源码色值线索**：#1a1a1a #2d2d2d #FF5722
- **画布**：1920×1080, 暗底 `#1a1a1a` + 135° 渐变 (`#1a1a1a → #2d2d2d → #1a1a1a`)。
- **字体**：display `Archivo Black` (900); body `Space Grotesk` 400/500/700。
- **时间轴**：- **0.2s** 左上巨大 section number (`Archivo Black` 96px, 如 `01/04`, 斜杠后半 opacity 0.3) 从上方 rollIn。 - **0.4s 起** 右上 nav breadcrumb 错峰淡入: active 项 `#FF5722` 橙 opacity 1, 其余白 opacity 0.35。 - **0.6s** 橙色焦点卡 (`#FF5722`, 圆角 36px 仅左侧, 占右 ~1180px) 从 translateX(110%) 滑入, 带橙色柔影。 - **1.15s** 卡内 label (uppercase, letter-spacing 4px) fadeUp。 - **1.3s** 卡内大标题 (`Archivo Black` 130px, 深色 `#1a1a1a` on 橙) fadeUp。 - **1.6s** 左下 footer (橙色 tick 短条 + system 标签) 淡入。
- **配色纪律**：暗底灰阶 + 唯一强调色 `#FF5722` 橙 (焦点卡 / active nav / footer tick)。可换成 coral/vibrant accent 但**全片只用一个**强调色。卡上文字用深色保证对比。
- **内容纪律**：- title 1-2 行, 必须用真实标题, 严禁 lorem ipsum。 - nav 面包屑反映真实章节结构, 第一项 active。 - 动效用 `@keyframes`, `prefers-reduced-motion` 下全部停在终态。 - 单文件 HTML。

### ◇ `frame-build-minimal` — 奢华极简留白帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：9
- **时长档**：4–7s · **画幅**：16:9 · 1:1
- **适合**：Premium product / brand hero；Calm single-word statement；Elegant title card
- **源码色值线索**：#FAFAF8 #1A1A18 #CBC7C0 #B0ACA4 #D4A574
- **画布**：1920×1080, 暖白底 `#FAFAF8`; 左上叠暖金径向 wash (`rgba(212,165,116,0.07)`)。**70%+ 留白是这套风格的灵魂**, 不要填满。
- **字体**：西文 `Inter` weight 200/300 (超细); 中文 `Noto Sans SC` Light。字距收紧 (-4 ~ -7px)。
- **时间轴**：- **0.2s** 四角 corner marks (暖金 0.5px 描边 L 形) + 暖金 wash 淡入。 - **0.5s** eyebrow (uppercase, letter-spacing 9px, `#B0ACA4`) fadeUp。 - **0.6s 起** hero 单词逐字符浮现 (每字 .ch span, 错峰 80ms, translateY 30→0, expo-out)。font-size ~220px, weight 200。 - **1.9s** 暖金细线 (`#D4A574`, 高 1px) 从宽 0 → 88px 居中生长。 - **2.2s** 两行 desc (weight 300, `#A8A4A0`, line-height 2) fadeUp。 - **1.8s** 侧边竖排小标签 (左右各一, rotate ±90°) 淡入。 - **2.4s 起** 底部 7 条细竖线 (1.5px, 部分暖金) 错峰升起, 随后进入 4s 慢呼吸循环 (opacity 1↔0.45)。
- **配色纪律**：仅用 暖白 `#FAFAF8` / 近黑 `#1A1A18` / 暖金 `#D4A574` / 暖灰 `#A8A4A0`/`#B0ACA4`。**禁止**鲜艳色。暖金是唯一强调, 极克制 (细线 / 角标 / 个别指示器)。
- **内容纪律**：- hero 是一个词 (≤16 字符), 必须用用户真实品牌词/主题词。 - desc 两行短句, 严禁 lorem ipsum。 - 动效用 `@keyframes`, `prefers-reduced-motion` 下全部停在终态。 - 单文件 HTML。

### ⚡ `frame-creative-voltage` — 创意电压分屏帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：7
- **时长档**：3–6s · **画幅**：16:9 · 1:1
- **适合**：Energetic brand / campaign title；Creative reveal with a human, hand-drawn accent；Retro-modern hero
- **源码色值线索**：#0d0d14 #2f4bff #6f86ff
- **画布**：1920×1080, 左电光蓝屏 (`#2f4bff`, 47%) + 右暗屏 (`#0d0d14`, 53%), 错位分割。
- **字体**：display `Syne` 800; mono `Space Mono`; 手写 `Caveat`。
- **时间轴**：- **0.1s** 左蓝屏从 translateX(-100%) 滑入; **0.25s** 右暗屏从 translateX(100%) 滑入 (错峰, expo-out)。 - **0.9s** 蓝屏左上电光高光 wash 淡入。 - **1.0s** 蓝屏左上 mono meta 行 (`// CREATIVE_MODE · ON`) 淡入。 - **1.0s 起** 右屏 display 标题逐行升起 (每行 .ln, 错峰 180ms); 一行用 `.volt` 描边电光词 (`-webkit-text-stroke` + 蓝色填充)。font-size 132px, 右对齐。 - **1.4s** 蓝屏手写 script (`Caveat`, rotate -7°) 弹入。 - **1.9s** script 下方手绘 underline (SVG path, stroke-dashoffset 描出)。 - **2.2s** 右下 mono caption 淡入。
- **配色纪律**：电光蓝 `#2f4bff`/`#6f86ff` / 暗 `#0d0d14` / 白。蓝是能量主色, 描边词与 script 制造"电压"对比。**禁止**杂色。
- **内容纪律**：- display 拆 2-4 行, 选一个词做 `.volt` 描边强调。 - script 是短手写词组 (≤24 字符), 给画面人味。 - 必须用真实标题, 严禁 lorem ipsum。 - 动效用 `@keyframes` + SVG stroke, `prefers-reduced-motion` 下全部停在终态。 - 单文件 HTML。

### 📈 `frame-data-chart-nyt` — NYT 风数据图表帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：2
- **时长档**：5–20s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：Editorial data viz；Annual report；Comparison reveal
- **源码色值线索**：#f7f5ee #1a1a1a #a91d1d
- **画布**：1920×1080, 暖白底 `#f7f5ee` 或墨黑底 `#0e0e0e` 二选一; 文字色和背景相反。

### 📊 `frame-data-rollup` — 数据滚动帧

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：remotion · **CSS 动画数**：0
- **时长档**：3–8s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：A data frame where the numbers should animate, not sit static；Weekly metrics / growth bars driven by real values；Enhancing one data segment of an otherwise hyperframes video
- **画布**：默认 1920×1080,布局全部基于真实画布尺寸 (`useVideoConfig`) 计算,9:16 / 1:1 也不会压扁。
- **内容纪律**：- 喂真实数据,别用占位数字。 - `value` 必须是数;非数会被当 0(`enhanceFrameNative` 应在绑定前归一/校验)。 - 柱子数控制在 7 根内。

###  `frame-decision-tree` — Decision Tree

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：3–30s · **画幅**：16:9
- **适合**：How-to flow；Decision branching；Process diagram
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

### 🔷 `frame-electric-studio` — 电光工作室分屏帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：7
- **时长档**：3–6s · **画幅**：16:9 · 1:1
- **适合**：Pull-quote / testimonial reveal；Mission statement card；Clean high-contrast title
- **源码色值线索**：#0a0a0a #4361ee
- **画布**：1920×1080, 白色上屏 (540px) + 电光蓝下屏 (`#4361ee`, 540px), 中线分割。
- **字体**：display + body 都用 `Manrope` 800/700/500/400。
- **时间轴**：- **0.1s** 上屏从 translateY(-100%) 下落、下屏从 translateY(100%) 上升, 同时从中心"开合"到位 (expo-out)。 - **0.9s** 接缝处黑色 accent 条 (高 8px) 从宽 0 → 320px 生长。 - **1.0s 起** 引言逐行浮现 (每行 .ln, 错峰 150ms, translateY 26→0); 跨入蓝屏的行用白色 (`.on-blue`)。font-size 96px, weight 800。 - **2.2s** 下屏 attribution (name 28px 700 + role uppercase 0.7 opacity, 白色) 淡入。 - **2.5s** 右上品牌 mark (深色) + 右下品牌 mark (白 0.6) 淡入。
- **配色纪律**：白 / 电光蓝 `#4361ee` / 近黑 `#0a0a0a` 三色。accent 条与品牌词用黑/白, 蓝是大色块。**禁止**第四个主色。
- **内容纪律**：- quote 拆成 2-4 行, 让 1-2 行落在蓝屏 (改 `.on-blue` class) 形成跨屏对比。 - 必须用真实引言/陈述, 严禁 lorem ipsum。 - 动效用 `@keyframes`, `prefers-reduced-motion` 下全部停在终态。 - 单文件 HTML。

### ⚡ `frame-glitch-title` — 故障艺术标题帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：1
- **时长档**：3–8s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：Tech product reveal；Cyberpunk aesthetic；Hacker vibe
- **源码色值线索**：#0d0e10 #f5f5f7 #00f0ff #ff2bd6 #ffb547
- **画布**：1920×1080, 背景 `#070708` 近黑或 CRT 暗灰 `#0d0e10`; 加 56px 网格 (透明 5%) + scanlines 横线 (透明 8%, 2px 间隔)。

###  `frame-kinetic-type` — Kinetic Type

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：3–30s · **画幅**：16:9
- **适合**：Promo headline；Bold statement；Punchy intro
- **源码色值线索**：#0a0a0f
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

### 🎞️ `frame-light-leak-cinema` — 胶片漏光电影帧

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：4–10s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：Cinematic intro；Documentary cold open；Mood / b-roll
- **源码色值线索**：#1a0d08 #ffb547 #ff7e3f #d97757 #2a1410
- **画布**：- **2.39:1 letterbox** (推荐): 1920×800, 上下黑边各 140px (`#000`)。 - 或 16:9: 1920×1080, 无 letterbox。

### 🌊 `frame-liquid-bg-hero` — 流体背景 Hero 帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：3
- **时长档**：4–12s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：Product launch hero；SaaS landing video；Editorial cover
- **源码色值线索**：#1e1b4b #fafaf8 #a78bfa #7c5cff #ec4899
- **画布**：1920×1080 (横) 或 1080×1920 (竖), 二选一。背景占满。

### 🎬 `frame-logo-outro` — 品牌 Logo 收尾帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：4
- **时长档**：3–10s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：Video closing card；Brand outro；Channel sign-off
- **源码色值线索**：#1a1535 #08090c #f5f5f7 #7c5cff
- **画布**：1920×1080, 黑色 `#08090c` 或品牌深色背景; 加微妙 vignette `radial-gradient(...)` 让中心更亮。

###  `frame-nyt-graph` — NYT Graph

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：3–30s · **画幅**：16:9
- **适合**：News-style stat reveal；Line chart over time；Editorial data point
- **源码色值线索**：#faf9f6
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

### 📊 `frame-pentagram-stat` — 瑞士网格数据帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：8
- **时长档**：3–6s · **画幅**：16:9 · 1:1
- **适合**：Single hero metric / benchmark reveal；Editorial data slide；Rational, high-contrast brand moment
- **源码色值线索**：#E63946
- **画布**：1920×1080, 纯白底 `#ffffff`; 叠瑞士网格 — 水平/垂直细线 (黑, opacity 0.04-0.06), 开场 0.7s 内 scaleX/scaleY 从 0 扫入。
- **字体**：西文 `Archivo` (900/700/500) 或 `Helvetica Neue`; 中文 `Noto Sans SC` Bold。理性、紧凑、负字距。
- **时间轴**：- **0.0-0.7s** 网格线扫入 (scaleX/scaleY 0→1, cubic-bezier(0.16,1,0.3,1))。 - **0.5-1.6s** 右侧巨大数字锚点 (font-size ~1020px, weight 900, 黑, opacity 0.07) 从下方 8% 升入并淡现, bleed off 右边缘。 - **0.7s** 红色 eyebrow label (uppercase, letter-spacing 6px, `#E63946`) fadeUp。 - **0.85s** 主数字 headline (~200px, weight 900) fadeUp; 句点/单位用 `#E63946` 红强调。 - **1.15s** 副标 (24px, `#999`) fadeUp。 - **1.3s** 红色 center rule (高 5px) 从宽 0 → 400px 生长。 - **1.35-1.7s** 5 根条形图错峰从底部 scaleY 0→1 生长; 中间一根 `#E63946` 红 + opacity 0.85, 其余黑 opacity 0.12。 - **1.5s** 黑色数据底栏 (高 80px) 从 translateY(100%) 滑入; 内含 3 组 stat (红色大数字 + 灰白小标签) + 右侧 system 标签。
- **配色纪律**：仅用 黑 / 白 / `#E63946` 红 / 中性灰 `#999`。**严禁**其他彩色。红色是唯一强调色, 用在 label / 主数字标点 / center rule / 中间条 / 数据底栏数字。
- **内容纪律**：- 必须用用户的真实指标/数字, 严禁 lorem ipsum 或编造 benchmark。 - headline 是一个数字 (≤12 字符); anchor 是它的简写 (≤4 字符) 用作背景巨字。 - 动效用 `@keyframes`, `prefers-reduced-motion` 下全部停在终态 (静态成图)。 - 单文件 HTML。

###  `frame-play-mode` — Play Mode

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：3–30s · **画幅**：16:9
- **适合**：Playful social ad；Casual intro；Fun product
- **源码色值线索**：#0057FF
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

###  `frame-product-promo` — Product Promo

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：3–30s · **画幅**：16:9
- **适合**：Product showcase；Multi-feature reel；Hero promo
- **源码色值线索**：#0a0a0f
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

###  `frame-product-promo-30s` — Product Promo · 30s

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：25–35s · **画幅**：16:9
- **适合**：30-second product promo；B2B SaaS launch；Multi-feature reel with sound
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

###  `frame-swiss-grid` — Swiss Grid

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：3–30s · **画幅**：16:9
- **适合**：Corporate slide；Minimal report card；Typography-led title
- **源码色值线索**：#f2f2f2
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

### 🌿 `frame-takram-organic` — 东方柔和有机帧

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：6
- **时长档**：4–7s · **画幅**：16:9 · 1:1
- **适合**：System / architecture concept reveal；Warm, human product story；Network or memory-graph explainer
- **源码色值线索**：#EFEAE0 #3A3A34 #7A9E7F #2E2E28 #C98A5E
- **画布**：1920×1080, 米色底 `#EFEAE0`; 右侧叠 sage 绿径向 wash (`rgba(122,158,127,0.10)`)。整体柔和、自然、有呼吸感。
- **字体**：西文 `Manrope` 700/600/400; 中文 `Noto Sans SC`。圆润, 不要太硬。
- **时间轴**：- **0.2s** 左侧毛玻璃圆角卡 (`rgba(255,253,248,0.66)` + blur 8px + border-radius 40px + 柔影) 从下方 26px + scale 0.985 升入。 - **0.7s** 绿色 eyebrow (`#7A9E7F`, uppercase, letter-spacing 4px) fadeUp。 - **0.9s** 卡标题 (92px, weight 700) fadeUp; 一个 accent 词用陶土橙 `#C98A5E`。 - **1.2s** caption (22px, `#8A867C`, line-height 1.8) fadeUp。 - **1.3s** 右侧放射图中心节点 (陶土橙, r=40) 弹出 (overshoot)。 - **1.4s 起** 8 条曲线 link (sage `#B8C9BA`, stroke-dasharray draw) 从中心错峰描出。 - **1.9s 起** 8 个外围节点 (sage 绿, r=22) 错峰 pop (scale 0→1, overshoot)。 - **2.0s 起** 整个放射图进入 7s 慢漂浮循环 (translateY 微动)。
- **配色纪律**：米色 `#EFEAE0` / 暖白卡 / sage 绿 `#7A9E7F`·`#B8C9BA` / 陶土橙 `#C98A5E` / 暖灰文字。**禁止**高饱和科技蓝/紫。绿是结构色, 橙是强调色 (核心节点 + 标题 accent 词)。
- **内容纪律**：- 节点图是"艺术品", 节点数 4-8 按内容调 (改 SVG 里 node/link 数量 + 角度)。 - 必须用真实概念/关系, 严禁 lorem ipsum。 - 动效用 `@keyframes` + SVG stroke-dashoffset, `prefers-reduced-motion` 下全部停在终态。 - 单文件 HTML。

###  `frame-vignelli` — Vignelli

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：0
- **时长档**：3–30s · **画幅**：9:16
- **适合**：Portrait social；Bold statement card；Red-accent promo
- **源码色值线索**：#1a1a1a #cc0000
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

###  `frame-warm-grain` — Warm Grain

- **复刻类型**：gsap（需重写为单文件）
- **引擎**：hyperframes · **CSS 动画数**：1
- **时长档**：3–30s · **画幅**：16:9
- **适合**：Product launch；Lifestyle brand；Magazine-style intro
- **源码色值线索**：#f5f0e0
- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— 复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。

### ✨ `vfx-text-cursor` — VFX 文字光标

- **复刻类型**：★ rich（零改动可渲染）
- **引擎**：hyperframes · **CSS 动画数**：1
- **时长档**：3–10s · **画幅**：16:9 · 9:16 · 1:1
- **适合**：Code demo intro；Tech narrative；Terminal vibe
- **源码色值线索**：#06070a #f5f5f7 #ff3b6f #00d4ff
- **画布**：1920×1080, 背景 `#06070a` 暗哑黑 或 `#0a0d12` (有暖偏蓝); 加微妙 vignette。

## 来源与署名

画面风格提炼自 html-video 模板库（全部 Apache-2.0 / MIT，允许再分发与商用）。
上游设计来源见下（部分模板直接原创于 html-video 作者）：

- **frontend-slides** → `frame-bold-poster`, `frame-bold-signal`, `frame-creative-voltage`, `frame-electric-studio`
- **huashu-design** → `frame-build-minimal`, `frame-pentagram-stat`, `frame-takram-organic`
- **none** → `frame-data-rollup`

> 改编自模板的帧，建议在片尾或说明里保留风格署名。
