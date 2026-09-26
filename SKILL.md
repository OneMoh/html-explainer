---
name: html-explainer
version: 1.4.1
description: 把任意主题做成「讲解/科普视频」并渲染成 MP4：调研→审查→解说词→字幕→配音（edge-tts，或火山引擎语音合成 2.0）→并行构建 HTML 场景→确定性逐帧渲染→成片后出多画幅封面。**画面语言内置 23 个模板风格 / 8 个类别**（大胆信号卡、奢华极简、NYT 数据图表、瑞士网格、故障艺术、胶片漏光、流体 Hero、Logo 收尾、东方柔和有机、VFX 文字光标…共 23 种风格，含每种的画布/配色/字体/时间轴规范，见 references/style-catalog.md），流程规范与音画同步体系承自 anything2explainer（词边界字幕、两级时钟、语速标定、多 agent 分工与 QC 判据），渲染层为自研 seek 式渲染器。**封面默认 16:9 + 3:4 两张**：抖音主封面 1920×1080 + 兼容主页栅格 3:4 的 1440×1080（独立重排，防切字）；**竖版投放再加 9:16 的 1080×1920**（左右并置必须改上下堆叠、上下边距让开平台 UI 层）。独立可移植：GSAP 内置、playwright-core 随包、ffmpeg 走 imageio-ffmpeg 回退、浏览器自动探测 Chrome/Edge；**不依赖 html-video / anything2explainer 任何代码或目录**。触发场景：要做科普/讲解/教学/知识/产品类视频、"讲一下 X 做成视频"、要用 html-video 那种模板化画面但更稳的音画同步、要挑某种视觉风格（极简/数据/赛博/电影感/品牌）出片、要出抖音封面/竖版封面/9:16 封面、anything2explainer 换 HTML 渲染、或提到 html-explainer / HTML 讲解视频 / explainer video / MG 视频。
agent_created: true
---

# html-explainer

> **定位**：`anything2explainer` 的流程与音画同步 + `html-video` 的 **23 个模板风格库**，
> 渲染层独立实现。作者 **Moh**，MIT 许可（第三方声明见 `THIRD_PARTY_NOTICES.md`）。
>
> **零外部依赖**：不需要 Remotion/npm 工程，不需要 html-video 仓库/Studio/pnpm/agent 后端。
> 技能自带：GSAP（离线）、playwright-core、渲染器、TTS/字幕/时间轴/主题/QC/封面全套脚本。
> 对两个来源项目的引用**只存在于注释署名里**，运行时不读它们的任何文件。
> 风格库是**抄下来的设计规范文本**（`references/style-catalog.md`），来源 `html-video`（Apache-2.0），
> 类比：把菜谱抄回家，之后做菜不需要原餐厅营业。

把一个主题做成**原创**讲解视频：任意风格的 MG 画面（HTML/CSS/GSAP，1920×1080 或竖版）、
配音（edge-tts）、词级对齐硬字幕、全局进度条。一句话一个场景，画面节拍直接锚在
吐字时刻上（`B('块文本')` 节拍器）。

## ★ 画面风格库（23 个模板 / 8 个类别）

**不要自己从零想画面 —— 先从风格库里挑；挑出候选后交用户拍板（见**确认点 0**），不许静默自选。**
完整目录（含每种的画布/字体/时间轴/配色纪律）
见 **`references/style-catalog.md`**；怎么改编成合规帧见 **`references/template-guide.md`**。

| 类别 | 可用风格 |
|---|---|
| 演示 / 标题卡 | 大胆海报帧、大胆信号卡帧、奢华极简留白帧、创意电压分屏帧、电光工作室分屏帧、故障艺术标题帧、Kinetic Type、Swiss Grid、Warm Grain |
| 数据可视化 | NYT 风数据图表帧、数据滚动帧、NYT Graph、瑞士网格数据帧 |
| 图解 / 流程 | 东方柔和有机帧、Decision Tree |
| 氛围 / 空镜 | 胶片漏光电影帧 |
| 营销 / Hero | 流体背景 Hero 帧 |
| 片头片尾 | 品牌 Logo 收尾帧 |
| 社媒竖版 | Play Mode、Vignelli（9:16）|
| 产品演示 | Product Promo、Product Promo · 30s |
| 特效 | VFX 文字光标 |

**两类模板、两种改编成本**（速查表「类型」列）：

| 类型 | 数量 | 处理 |
|---|---|---|
| **★ rich** | 12 | 单文件 + 纯 CSS `@keyframes`。**零改动可渲染** —— 只需①换系统字体栈（删 Google Fonts）②让出底部字幕带③填真实内容 |
| **gsap** | 11 | 多 composition + CDN GSAP（或 Remotion）。**不要搬代码**，只取视觉 DNA 用 CSS keyframes 重写（搬进来会得到静止首帧且零报错，见 `lessons.md` #9）|

> 时长档要匹配内容：`frame-bold-signal` 是 3–6s 的短片花，拉长到 20s 会空。
> 长段（>10s）优先选 3–30s 档的（Swiss Grid / Kinetic Type / NYT Graph / Warm Grain）。

## 何时用 / 不用

- 用：给主题/文章/文档做讲解视频；要挑某种视觉风格出片；要 html-video 那种模板化画面但要求音画稳；要 anything2explainer 流程但不想装 Remotion。
- 不用：复刻现有视频、真人口播、实拍为主；要 Remotion/React 代码动画本体（那是 anything2explainer 的领域）。

## 环境（首台机器跑一次）

```bash
bash <skill>/setup_env.sh            # 自检；--install 联网补装
```

依赖：Python≥3.9（edge-tts==7.2.8 钉死 / numpy / pillow / imageio-ffmpeg）、Node≥18、
**火山引擎零额外依赖**（`tts_volcano.py` 只用标准库 `urllib`，不需要装任何 SDK）。
Chrome 或 Edge（几乎必有；都没有才下载 playwright chromium ~115MB）、ffmpeg（PATH 或
imageio-ffmpeg 静态二进制自动回退）。Windows 注意：项目路径全 ASCII；给 Node/Python
传 `C:/...` 正斜杠路径；别用 heredoc 给 Python 传正则。

## 命令流水线（项目目录内，顺序不能乱）

```bash
PY=<venv python 绝对路径>          # 派子 agent 时必须展开成绝对路径写进 prompt
"$PY" <skill>/scripts/new_project.py <dir> <slug> --topic "主题"   # 阶段 0 建项目
"$PY" <skill>/scripts/tts_setup.py      --project .   # ★ 先定配音方案 + 音色（问用户：edge / 火山）
"$PY" <skill>/scripts/tts_build.py      --project .   # 配音：audio/*.mp3 + manifest
"$PY" <skill>/scripts/timeline_build.py --project .   # 全局时间轴：layout.json + narration-full.mp3
"$PY" <skill>/scripts/subs.py           --project .   # 字幕：subs.json + beats.js + srt/vtt
"$PY" <skill>/scripts/lint_frames.py    --project .   # 静态体检：八条契约违规（渲染前一秒出结果，比渲完再发现便宜得多）
node <skill>/scripts/check_layout.mjs   .             # ★ 几何体检：越界 / 侵入字幕带 / 元素互相遮挡（lint 看不见几何）
node <skill>/scripts/render_video.mjs   . [--preview 30] [--keep-frames] [--only <场景id>] [--mux-only] [--png-fast|--jpeg] [--concurrency N]   # 渲染：out/<slug>.mp4
"$PY" <skill>/scripts/qc_check.py       --project .   # 体检 + 抽帧速览图
node <skill>/scripts/cover_build.mjs    .             # 封面：out/cover_169.png + cover_34.png（竖版再加 cover_916.png）
node <skill>/scripts/check_cover.mjs    .             # 封面终态几何实测：边距/钩子字号/行宽/孤字/9:16 禁两栏（FAIL 清零再交）
```

配音引擎（**跑之前必须先问用户**，见确认点 3）：`edge`（默认，免费免密钥）或
`volcano`（火山引擎语音合成 2.0，音质更好，需 API Key）。两者产出的 manifest 结构一致，
下游零改动。切换：`--provider edge|volcano` 或 `TTS_PROVIDER` 环境变量。
**火山密钥只存 `tts.env`（已 gitignore）—— agent 只调 `tts_volcano.py`，不读该文件。**
详见 `references/volcano-tts.md`。

渲染截图模式（**画面里有满幅照片时务必换掉默认 PNG**，见 `lessons.md` 第 69 条）：
默认 PNG 对纯 CSS 图形帧很快（45ms/帧），但**对照片满幅帧是 582ms/帧（13×），
且编码在浏览器进程内串行 —— 加 `--concurrency` 完全无效**（实测并发 1/3/6 路的总吞吐
1.80 / 1.86 / 1.87 帧/秒）。照片类片子选：

- `--png-fast`：CDP `optimizeForSpeed`，**逐像素无损**、4.4× 加速（132ms/帧，体积 +22%）。
- `--jpeg --jpeg-quality 95 --crf 18 --preset medium`：13× 加速、体积 1/5；
  q95 = PSNR 41.65dB，已低于 x264 crf18 自身的失真，成片看不出。

辅助工具（随时可用，不进主流水线）：

```bash
"$PY" <skill>/scripts/make_theme.py --topic "医疗" --use   # 主题换色（只重写 theme.css，帧零改动）
node <skill>/scripts/peek_frame.mjs . <帧id> --at 40,80    # 单帧速览：秒级出图，先看设计对不对
# ★ peek_frame 的 --at 是**百分比**不是帧号；查冷开场空屏要传 --at 1,3,6 这种小百分数
node <skill>/scripts/peek_frame.mjs . <帧id> --at 100 --guides  # 叠十字中线 + 字幕禁区线（判对齐必开）
"$PY" <skill>/scripts/frame_at.py --project . --at 1:23    # 时间点 → 场景/帧号/源文件/终态帧图
"$PY" <skill>/scripts/frame_at.py --project . --list       # 全片场景时间表
```

画面排障（用户报「几分几秒」→ 定位到帧 → 视觉模型看图 → 改 → 局部重渲）的完整四步见
上文「★ 画面出错怎么定位」。

顺序不能乱：tts → timeline → subs（beats 依赖前两者）→ lint → 渲染 → QC → 封面。改解说词 → 重跑前三条，
`frames/<id>.beats.js` 自动刷新，**场景 HTML 一行不用改**（这是对 anything2explainer
「帧号硬编码、改一个字全片重对位」的结构性改进）。

> **`--preview` 会删掉渲出来的帧**（设计上是「预览模式顺手清草稿」）。凡是要拿 PNG 做
> 拼接 / 复核 / 只重渲单场，一律加 `--keep-frames`，否则帧目录会在合成后被清空（lessons #32）。
> 只改了一两个场景的画面时，**不要全片重渲**：用「临时项目法」按全局帧号补渲再贴回，
> 本片 3802 帧全重渲 924s，补渲 hook+outro 两段只花 220s（lessons #33）。

## ★ 封面（成片后必做，不是可选项）

封面决定点击率，成片决定完播率 —— 一张被切掉半个钩子的封面会让整片白做。

**默认出两张（16:9 + 3:4），竖版投放再加第三张 9:16。** 用户点名某画幅就按用户说的出。

| 规格 | 画布 | 输出 | 用途 |
|---|---|---|---|
| **A. 抖音主封面** | 1920×1080 | `out/cover_169.png` | 信息流 / 播放页 |
| **B. 兼容 3:4** | 1440×1080 | `out/cover_34.png` | 主页栅格（防切字） |
| **C. 竖版 9:16** | 1080×1920 | `out/cover_916.png` | 竖版全屏信息流 / 小红书 / 视频号 |

**核心纪律：每张都是独立排版，不是裁切关系。**
从 16:9 居中裁 3:4 只剩 810px 宽，丢掉 **57.8%** 画面；裁 9:16 只剩 608px 高，丢掉 **43.7%**。
大字钩子必被切。所以各张共享同一套视觉基因（配色/幕底/主视觉/钩子文案），**各自重排一次版**：

| 元素 | 16:9 版 | 3:4 版 | 9:16 版 |
|---|---|---|---|
| 悖论视觉 | 右侧，左右并置 | 上方，竖排堆叠 | 上段（10–45%），竖排堆叠 |
| 钩子 | 左下，两行 132px | 下方，三行 118px | 中下段（50–88%），三行 150px |
| 角标 | 左上 | 顶部居中 | 顶部居中（留 ≥180px 上边距） |
| 每行字数 | ≤8 字（防孤字断行） | ≤8 字 | ≤6 字 |
| 分裂线 | 右栏内横线 | 横贯（留边距） | 横贯（留边距），**不要竖线** |

**9:16 专属纪律**：上边距 ≥180px、下边距 ≥160px（让开平台顶/底 UI 层，这是**不可裁区**）；
**禁止左右两栏**（1080 宽里两栏必然放不下字）。

**封面三要素**（缺一返工）：① 大字钩子（≥96px / ≥120px / ≥130px，含反差悬念）
② 核心悖论视觉（两数对照 / 一升一降 / 分裂线 / 一明一暗，不是装饰图形）
③ 信息余量（四边 ≥96px / ≥110px / 左右 ≥90px，无贴边文字）。

做法：复制 `assets/cover-template.html` 为 `frames/cover_169.html`、`frames/cover_34.html`、
`frames/cover_916.html`（竖版才要第三份），各自排版 → `node scripts/cover_build.mjs .`
（默认 seek 到时间轴末尾取完整态，`--at 0.8` 可取入场中间态；缺哪张就跳哪张）。

**出图后必跑几何实测** —— 肉眼只能看出明显问题，差 20px 的贴边、多出一字的孤行全靠它抓：

```bash
node <skill>/scripts/check_cover.mjs .              # 量三张：边距 / 钩子字号 / 行宽 / 孤字 / 9:16 禁两栏
node <skill>/scripts/check_cover.mjs . --only 916   # 只量一张
node <skill>/scripts/check_cover.mjs . --shot       # 顺手把 1x 预览图丢到 out/
```

它按 `tl.pause(tl.duration(), false)` 把页内时间轴 seek 到轴末再量（**必须量终态**，lessons #30），
FAIL 清零才算封面过。退出码 0/1，可直接挂流水线。

详规见 **`references/cover-guide.md`**。


## 核心机制（为什么音画稳）

| 机制 | 口径 |
|---|---|
| 帧时长 | MP3 **容器时长**（tts_build 裁首尾静音后回填）。词边界时长每段少 ~0.86s，用它必错位 |
| 末块字幕收尾 | 语音**真实结束**（speech_end_sec）—— 两级时钟，混用则「字幕过了语音还没过」 |
| 字幕节拍 | 词级时间戳首字对帧号，绝不按字数插值（中文同字数时长差 3 倍）。edge 取 `WordBoundary`，火山取 `sentence.words[]`（**需显式开 `audio_params.enable_subtitle`，本包默认开**；不开会静默退回插值） |
| 画面节拍 | 场景 HTML 里 `B('块文本')` 取该词起播秒排 GSAP —— 画面与吐字同源 |
| 渲染 | **确定性 seek**：`tl.pause(t, false)` + CSS 动画 `currentTime=t×1000` → 截图 → ffmpeg 合成。无实时录制，html-video 的引导期/起播/字体坑整类不存在。**第二参必须传 `false`**，少了它 `onUpdate` 类回调被静默抑制（数字滚动恒为初值，见 lessons #27） |
| 字幕层/进度条 | 渲染器注入并逐帧驱动（`#mg-subs` 44px 白字黑边 bottom 96px；`#mg-progress` accent 填充），帧作者零负担 |

## 流程（五个确认点必须停下等用户回话）

完整版见 `references/workflow-guide.md`（含研究员/构建/QC agent 的 prompt 模板与时长档位表）。

0. **建项目**（5 分钟）：`new_project.py` + 定主题（`make_theme.py --topic/--preset … --use`，颜色全在 theme.css 的 CSS 变量里，画面代码禁止色值字面量）

   ### ★ 确认点 0 —— 配色 / 风格一律先问，禁止凭记忆替用户拍板

   **这是硬规则，每一期都要走一遍，不得沿用上一期的选择。**

   - 开工（乃至挑风格）之前，先给用户 **2–4 个候选**，每条写清三件事：
     **① 色号（hex）② 一句气质描述 ③ 适合什么内容**。让用户挑，而不是替他挑。
   - **风格模板同样要问**：从 `references/style-catalog.md` 选出 2–4 个候选列出来，
     不要静默从「上次挺好用」的记忆里定 2–4 种。
   - 用户**自带色号**时：照他的色号落地，但仍要回报
     「我打算用哪个色做哪个语义（重点 / 指标 / 警示）」，请他确认。
   - 用户明确说「你决定」「按你上一次的来」时才可以自行选择 —— 且要说明选了什么、为什么。
   - ⚠️ 反面教材：看到暖色题就默认 `--preset amber`、看到数据题就默认瑞士网格。
     记忆里"好用"的东西不构成用户的选择。
1. **调研**（20 分钟，1 agent）：research/调研.md，每个数字带 URL；**确认点 1**（时长/语言 + **投放画幅与封面张数**）并行问

   **确认点 1 顺带问一件事：封面要哪几张。** 默认 16:9 + 3:4 两张（横版投抖音/视频号）。
   若用户会投**竖版**（竖版成片、全屏竖版信息流、小红书、朋友圈），要**再加 9:16 那张** ——
   9:16 不是把 3:4 拉长，是另一种构图（左右并置必须改上下堆叠、上下边距让开平台 UI 层）。
   现在问清，后面就不用返工；用户说「按默认」就只做两张。
2. **解说词**（30 分钟）：narration.json（`|` 切字幕块，中文 ≤16 字/块）→ 填 order → **确认点 2**（文案定稿）→ **确认点 3**（配音方案 + 音色）→ tts/timeline/subs 三连 → 核对时长区间（差 >15% 改句子，别改语速硬凑）→ **定稿后不改词**

   **确认点 3 必须问两件事**（用 `tts_setup.py` 落实）：
   ① **方案** —— 「配音用 edge-tts（免费、免密钥、开箱可用）还是火山引擎语音合成 2.0
     （音质更好，需要 API Key，约 1 分钟配置）」；
   ② **音色** —— 选定方案后列候选让用户挑，也可自定义 ID。
   选火山时：缺 `tts.env` → `tts_setup.py` 生成空模板并**停下来**，让用户手工填密钥
   （**agent 不读该文件、不参与填值**）；用户说填好了 → `--check` 测连接 → 再选音色。
   ★ 提醒用户用 `cp tts.env.example tts.env` **复制**，别把 `tts.env.example` **改名**成
   `tts.env` —— 那是要留在仓库里的模板（改名会让 `check_integrity.py` 报错）。
   详见 `references/volcano-tts.md`。
3. **分镜（含选风格，20 分钟）**：script/storyboard.md，每场景一行 ——
   **先从风格库挑出 2–4 个候选交用户选（受确认点 0 约束，不可静默自选）**，
   再照 `references/style-catalog.md` 的「挑风格的实用建议」表核对内容类型与时长档，
   最后写画面/主角·尺寸/光/B() 锚点；末尾全局约束
   （贯穿示例、事实清单、每章 1–2 高光时刻、每章 ≥3 运镜）。
   全片建议 2–4 种风格轮换，避免 8 个场景全用同一个模板。
4. **场景构建（并行）**：每组 4–8 场景一个 agent（一波 ≤3–4 个）。
   - 挑中的 **rich** 模板：从它的 `source/index.html` 改写 —— ①删 Google Fonts 换系统栈
     ②底部元素抬到 ≥176px ③填真实内容（照 `example.md` 的字段）
   - 挑中的 **gsap** 模板：**别搬代码**，只照风格规范用 CSS keyframes 重写
   - 全新画面：从 `frames/_template.html` 复制，契约见 `references/frame-contract.md`
   - 改编细则见 `references/template-guide.md`；边做边写盘
   - 想「照镜子」不必渲全片：`node scripts/peek_frame.mjs <项目> <id> --at 40,80` 秒级出图
5. **静态体检**：`lint_frames.py --project .` 把八条契约违规钉在渲染之前（外链字体、色值字面量、
   墙钟逻辑、`B()|| N` 兜底、字幕带压内容、缺中文字体族…）；FAIL 清零再进渲染。
   **再跑 `check_layout.mjs .`** —— lint 看不见几何，元素互相遮挡 / 侵入字幕带 / 出画只有它管；
   ERROR 清零再进渲染（两条命令都是一秒级，比渲完几千帧再回来看便宜得多）。
6. **打样**：`render_video.mjs . --preview 30` → **确认点 4**（风格/字号/语速/节奏一次定稿）→ 全片渲染 + qc_check
7. **QC**：qc_report.md 的 FAIL 清零 + qc_sheet.jpg 肉眼过（字幕带 80–170px 无内容、一焦点、光跟主角）→ 按组修复 → 重渲
8. **封面**：做 `frames/cover_169.html` + `cover_34.html`（独立排版；竖版投放再加 `cover_916.html`）
   → `node scripts/cover_build.mjs .` → **`node scripts/check_cover.mjs .`**（量终态几何，FAIL 清零）
   → 核对 `out/cover_report.md` + `references/cover-guide.md` 的自检清单
9. **交付**：mp4 + 封面（默认两张，竖版三张）+ srt/vtt（上传平台=可检索文本）+ 发布说明（硬字幕→关平台自动字幕；
   AI 配音→勾 AIGC；封面文字须与视频首帧钩子同义；受监管题材过合规）

## ★ 画面出错怎么定位（用户报「几分几秒」，agent 直接落到那一帧）

成片里发现画面问题（元素错位、被压住、少了东西、动效没走完）时，**不要重新描述场景内容、
不要从头翻 5000 帧**。流程固定成四步：

1. **用户只需要给「几分几秒」+ 一句现象。** 例：`1:23 右下角示意图里小黑点没在射线汇聚点上，偏左上`。
   `.github/ISSUE_TEMPLATE/bug_report.yml` 里有一栏专门收这个时间点。
2. **`frame_at.py` 把时间点翻译成定位信息**（一条命令，秒级）：

   ```bash
   "$PY" <skill>/scripts/frame_at.py --project . --at 1:23
   "$PY" <skill>/scripts/frame_at.py --project . --at 1:23 --box 1400,200,1920,900   # 再裁一块可疑区
   "$PY" <skill>/scripts/frame_at.py --project . --list                              # 全片场景时间表
   ```

   产出 `out/probe/`：**场景 id / 帧号 / 场景源文件 `frames/<id>.html` / 节拍文件 / 当刻字幕块
   （反查代码里的哪一句 `B('…')`）**，以及三张给视觉模型看的图 —— 整帧（1280 宽）、
   底部 260px 禁区带（1:1）、**场景终态帧**。
3. **带视觉的模型看那几张图**（这是关键：只用文本描述「蓝点没在中间」定位不到，看图能直接
   读出偏了多少、偏哪个方向、被谁压住）。先看**终态帧**，再看当刻帧。
4. **改 `frames/<id>.html` → 重跑 `check_layout.mjs`（几何）→ `lint_frames.py`（契约）→
   `render_video.mjs . --only <场景id>` 局部重渲** → 回到第 2 步复核同一时间点。

### 两条判据（省掉大量返工）

- **先看终态，再看中途。** 中途帧的入场动画可能还没走完，元素位置**本来就该**和终态不同 ——
  单看它分不清「代码错」还是「动画错」。**终态也错 = 布局本身错了；只有中途错 = 动画时序问题。**
- **`--only <id>` 只对末场安全**（见 `lessons.md` #15）：改短了必须删尾部过期帧，
  且**渲染日志的 ✓ 不算证据** —— 用 `frame_at.py` 回到那个时间点看图确认。

## 场景契约速查（完整版 references/frame-contract.md）

八条：1920×1080 系统字体（禁外部字体）→ 颜色只取 theme.css 变量 → 动画只用 GSAP
（`window.__tl` 注册，禁 CSS transition 入场；@keyframes 循环装饰可用，渲染器会 seek）→
节拍用 B() → 字幕带（80–170px）与进度条带（0–12px）不放内容 → 一场景一焦点
（主角 ≥170px 或大字 ≥96px 带 accent 柔光，配角不发光，文字 ≥22px）→
GSAP 用 `../assets/gsap.min.js`（本地内置）→ 主体动画压在 speech_end 前。

## 质量标尺

- 画面：每帧一个焦点，主角带光；accent 只给当前重点；背景只有幕底+网格，无碎屑
- **几何：`check_layout.mjs` ERROR 清零** —— 遮挡/越界是唯一一类「lint 全绿但仍然错」的问题
  （lint 只看文本规则）。**一个几何体只准有一个坐标系**：SVG 图元与 HTML 部件不得混用两套基准
  （issue #1「蓝点没落在射线汇聚点上」的根因，见 `references/frame-contract.md`）
- 节拍：元素出现落在对应字幕块起始 ±0.2s 内（B() 天然保证）；每句至少一处可察觉变化
- 字幕：中文 ≤16 字/块、无标点、单帧硬切、每块 ≥0.6s；末块跟着语音消失
- 底色：**用了亮底（浅色背景）就必须先给字幕层换肤** —— 渲染器注入的字幕/进度条默认是
  「白字 + 黑描边」，白字落在米白纸面上等于看不见。主题文件里给亮底作用域补
  `--mg-sub-fg` / `--mg-sub-stroke` / `--mg-track` / `--mg-tick` 即可（见 `references/lessons.md` #75）。
  **它是渲染期产物 —— 改它 = 整片重渲，所以第一次全片渲染前先用 `--preview` 拿到
  跨明暗切换的那几十秒。**
- 事实：画面数字/术语/年份逐个对调研 URL；示例数据标「示意」
- 时长：落在确认点 1 区间内；成片与音轨差 <0.5s（qc_check 把关）

## 关键文件

**流水线脚本**（按执行顺序）

| 路径 | 作用 |
|---|---|
| `scripts/new_project.py` | 阶段 0 脚手架：建目录树 + `project.json` + `narration.json` 占位 + `theme.css` + 两份封面 HTML（16:9 + 3:4；9:16 按投放需要自己加，注释里给了做法） |
| `scripts/tts_setup.py` | **配音方案向导**：选 edge/火山 → 缺密钥则生成 `tts.env` 模板并停下 → 测连接 → 选音色 → 写回 project.json。输出 `NEXT_ACTION=…` 供 agent 判断下一步 |
| `scripts/tts_volcano.py` | **火山引擎语音合成 2.0 接口包**：唯一读 `tts.env` 的地方；`--check` / `--voices` / `--synth`。密钥不回显、异常脱敏（`_redact`） |
| `scripts/tts_build.py` | 配音合成：edge-tts **或** 火山引擎（`--provider`）；缓存/硬超时/退避重试/裁静音，manifest 写两级时长。两引擎 manifest 结构一致 |
| `scripts/timeline_build.py` | layout.json 全局轴 + narration-full.mp3（gap 显式插入） |
| `scripts/subs.py` | 字幕三出口（subs.json / srt+vtt / 画面内层由渲染器注入）+ beats.js 节拍器 |
| `scripts/lint_frames.py` | **渲染前静态体检**：八条契约违规逐条报（外链字体/色值字面量/墙钟/`B()\|\|N`/字幕带压内容/缺中文字体族…）—— 只看**文本规则**，看不见几何 |
| `scripts/check_layout.mjs` | **渲染前几何体检**（终态）：侵入字幕禁区 / 出画 / 文字被遮挡 / 文字重叠 = ERROR；越安全边 / 文字压色块 / 色块重叠 = WARN；疑似未对齐 = INFO。量的是**字墨范围**（Range 逐行）而非元素框。`--only` / `--json` / `--safe-bottom`；有 ERROR 退出码 1 |
| `scripts/render_video.mjs` | 渲染器：浏览器探测 → 逐场景 seek 截图 → ffmpeg 合成；`--preview N` 快样片，`--only <场景id>` 只重渲指定场景（**仅末场安全**，变短后须清尾部过期帧，见 lessons 45），`--mux-only` 用现有帧重新合成；**帧里有满幅照片就必须换截图模式**（默认 PNG 编码占 96% 帧时间且与并发无关）：`--png-fast` 无损 4.4×，`--jpeg --jpeg-quality 95` 13×；`--crf N` / `--preset <名>` 单独控制成片码率 |
| `scripts/qc_check.py` | 流/时长/音量/抽帧体检 + contact sheet |
| `scripts/cover_build.mjs` | 封面渲染器：`169`(1920×1080) / `34`(1440×1080) / `916`(1080×1920) 各一份独立排版 → 2 倍图；`--at` / `--only` / `--jpg`；**缺哪张就跳哪张** |
| `scripts/check_cover.mjs` | **封面终态几何实测器**：边距 / 钩子字号 / 钩子是否最大文字 / 行宽 / 孤字断行 / 9:16 禁左右两栏 / 越界；`--only` / `--json` / `--shot`；退出码 0/1 |

**辅助工具**

| 路径 | 作用 |
|---|---|
| `scripts/peek_frame.mjs` | 单帧速览：不渲全片，秒级截某场景的几个时点看图（`--at` 是百分比）；`--guides` 叠十字中线 + 字幕禁区线（**判「元素有没有对齐」必须开**，没有基准线肉眼判不了） |
| `scripts/frame_at.py` | **时间点 → 定位**：报「几分几秒」就能拿到场景 id / 帧号 / 源文件 / 当刻字幕块 / 整帧图 / 底部禁区带裁图 / **场景终态帧**（`--at 1:23` / `--list` / `--box x0,y0,x1,y1` / `--final`）。画面排障的入口工具 |
| `scripts/check_integrity.py` | 仓库自洽性：版本号/风格目录/计数一致性 + 模板外链扫描（CI 与本地都跑） |
| `scripts/make_theme.py` | 4 预设 + 主题词推色 → theme.css（CSS 变量单源） |
| `scripts/import_styles.py` | （移植期一次性工具）把已装 html-video 的设计规范抄成纯文本风格目录；**跑视频永不需要它** |
| `tests/geometry-fixture/` | **几何体检的证伪样本**：故意坏掉的帧（越界 + 遮挡 + 错位），期望 ERROR 2 / WARN 0 / INFO 1。改 `check_layout.mjs` 后先拿它验「还抓得到错」，再拿真实项目验「误报没变多」 |
| `setup_env.sh` | 环境自检 / `--install` 联网装缺项 |
| `package_skill.py` | 打成可移植 zip（`--with-deps` 含 node_modules） |

**参考文档与资源**

| 路径 | 作用 |
|---|---|
| `references/style-catalog.md` | **23 个画面风格目录**（画布/字体/时间轴/配色纪律 + rich/gsap 分类）——纯知识，非代码依赖 |
| `references/style-catalog.json` | 同上的机器可读版（`kf`/`multi`/`engine` 字段用于自动判类型） |
| `references/template-guide.md` | 模板改编指南（rich 三步法 / gsap 重写法 / 挑风格建议） |
| `references/frame-contract.md` | 契约细则 + 版式基因 + 反例 |
| `references/cover-guide.md` | **封面详规**：一张还是几张 / 各画幅排版纪律 / 重排对照表 / 三要素 / 尺寸倍率 / 上传策略 / 自检清单 |
| `references/workflow-guide.md` | 阶段详解 + agent prompt 模板 + 时长档位表 |
| `references/lessons.md` | 踩坑台账（继承 14 条 + 本技能记录，持续追加） |
| `assets/frame-template.html` | 场景模板（契约注释在文件头，B() 用法示例） |
| `assets/cover-template.html` | **封面模板**（封面三要素注释在文件头，可改尺寸复用为 16:9 / 3:4 / 9:16 各一份） |
| `assets/gsap.min.js` | GSAP 3.13 本地内置（离线渲染；License 见同目录 `gsap-README.md`） |
| `README.md` / `README.en.md` | 对外项目说明（**README.md 中文为默认**，`README.en.md` 英文；含跨 Agent 安装指引） |
| `CONTRIBUTING.md` | 贡献指南：硬性规则、端到端自检、PR 清单 |
| `CHANGELOG.md` | 版本变更史 |
| `THIRD_PARTY_NOTICES.md` | 第三方组件与衍生内容的授权声明（**发布前必读**） |

## 跨 Agent 安装

本技能遵循 [Agent Skills](https://code.claude.com/docs/en/skills) 约定（`SKILL.md` +
`scripts/` + `references/` + `assets/`），**不绑定任何单一智能体平台**。仓库根目录**就是**
技能目录，所以 clone 到下表任一路径即可直接生效，不需要再拷子目录。

| 智能体 | 个人级（全局） | 项目级（仓库内） |
|---|---|---|
| WorkBuddy | `~/.workbuddy/skills/` | `<工作区>/.workbuddy/skills/` |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenAI Codex | `~/.codex/skills/` | `.codex/skills/` 或 `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` 或 `.agents/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| GitHub Copilot / VS Code | `~/.copilot/skills/` | `.github/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `.opencode/skills/` |
| Windsurf | `~/.windsurf/skills/` | `.windsurf/skills/` |
| 通用约定 | `~/.agents/skills/` | `.agents/skills/` |

手动安装（把 `~/.claude` 换成你所用智能体的目录）：

```bash
git clone https://github.com/OneMoh/html-explainer.git ~/.claude/skills/html-explainer
bash ~/.claude/skills/html-explainer/setup_env.sh --install
```

也可以直接把这句话交给智能体，让它自己装：

> 给当前本地环境安装该 Skill：https://github.com/OneMoh/html-explainer.git
> 安装到你的技能目录，并检测安装必要的运行环境（Python 3.9+ / Node 18+ / Chrome 或 Edge / ffmpeg）

装完**新开一个会话**，让智能体重新扫描技能目录。同理，调用本技能时应把
`<SKILL_ROOT>` 替换成实际安装路径 —— 派子 agent 时要展开成**绝对路径**写进 prompt。

## 打包移植

技能目录自包含，不引用本机任何绝对路径（脚本按自身位置定位 `SKILL_ROOT`）。
仅有两处**兜底探测**会去探 WorkBuddy 托管的运行时目录（`setup_env.sh` 的 Python/Node
候选、`peek_frame.mjs` 的技能根候选）—— 探不到就自动跳过，不影响其它平台。

**零依赖声明（重要）**：本技能**不需要** html-video 或 anything2explainer 存在。
两个来源项目的名字只出现在：① 代码注释的出处署名 ② `scripts/import_styles.py`
这个**移植期一次性工具**的用法说明里。跑一条视频（tts → timeline → subs → render →
qc → cover）**完全不碰这两个项目**。风格库是抄成纯文本的设计规范
（`references/style-catalog.md`），已随技能打包。

```bash
# ① 打包（默认不含 node_modules，只有 ~110KB）
python package_skill.py                # → dist/html-explainer-v<版本>.zip
python package_skill.py --with-deps    # 含 playwright-core，~14MB（目标机全程离线）

# ② 新机器：解压到任意目录（放进上表任一「个人级」技能目录即可被该智能体识别）
bash setup_env.sh --install            # 自检 + 装缺项（先装后判定，装成功即算就绪）

# ③ 跑一遍端到端（可选，验证链路）
python scripts/new_project.py demo --topic "人工智能"
# …填 narration.json / 写 frames/*.html / 填 project.json.order…
python scripts/tts_build.py --project . && python scripts/timeline_build.py --project .
python scripts/subs.py --project . && node scripts/render_video.mjs .
python scripts/qc_check.py --project . && node scripts/cover_build.mjs .
```

**依赖探测顺序**（都尽量用系统已有的，避免下载）：
- Python：先找 WorkBuddy 托管 venv，再 `python3` / `python`
- Node：`node -v` ≥18；没有则扫 `~/.workbuddy/binaries/node/versions/*`（WorkBuddy 托管路径）
- 浏览器：Chrome → Edge → playwright chromium → `BROWSER_PATH` 环境变量
- ffmpeg：PATH → `imageio_ffmpeg.get_ffmpeg_exe()`（pip 装依赖时自带静态二进制）
- GSAP：包内 `assets/gsap.min.js`（离线，不外链）

已验证：把 zip 解压到干净目录、只跑 `setup_env.sh --install`，**全链路输出与原目录逐帧一致**
（同 346 帧、同抽帧体积、同音画差 0.05s）。

## 许可与致谢

- 本技能**原创代码与文档**：MIT © 2026 **Moh**（见 `LICENSE`）。
- **画面风格目录**（`references/style-catalog.md` / `.json`）由 [nexu-io/html-video](https://github.com/nexu-io/html-video)
  （Apache-2.0）的模板设计规范转写而来，已保留署名；转写文本按 Apache-2.0 分发。
- **方法论思路来源**：[Vincentwei1021/anything2explainer](https://github.com/Vincentwei1021/anything2explainer)
  （词边界字幕 / 两级时钟 / 语速标定 / QC 判据）。两者均为**他人独立项目，与本技能不是同一作者**。
  确定性 seek 渲染器、`B()` 节拍锚定、多画幅独立排版封面（16:9 / 3:4 / 9:16）为本项目原创。
- **打包内置**：GSAP 3.13（GreenSock 标准「no charge」许可，见 `assets/gsap-README.md`）、
  playwright-core（Apache-2.0）。
- 完整清单与逐条授权见 **`THIRD_PARTY_NOTICES.md`**。发布/再分发前请连同该文件一起带上。
