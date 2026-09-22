# 变更日志

`html-explainer` 的所有重要变更都记录在这里。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

`1.2.2` 之前的版本都是私有内部发布。**`1.2.2` 是 GitHub 上的首个公开版本。**

---

## [1.2.3] — 2026-09-22

### 新增

- **`render_video.mjs --only <场景id,场景id>`** —— 改完某一场的文案或动效后，**只重渲这一场的帧**，
  其余场景的帧原样保留。实测：14 场 6194 帧整片重渲约 20 分钟，只重渲末场 78 秒。
  脚本会检查被指定场景是否为末场并给出警告（非末场一旦时长变化，其后场景帧号会整体前移）。
- **`references/lessons.md` 第 43–45 条**：结尾写法红线（同义反复 / 自指复读 / 鸡汤留白三类废句，
  及「勾选框全空的待办清单」这一替代写法）、极简帧的信息重复、`--only` 的两个前提与必做清理。

### 修复

- **★ 合成阶段的 `-shortest` 会砍掉视频尾部。** 音轨通常比画面短（段尾静音 + 片尾留白），
  `-shortest` 按较短的那条流收尾，于是**片尾字幕与片尾文字面被截短**。
  实测某片：片尾设计 1.5s，成片只剩 1.16s（成片比 layout 短 0.52s）。
  已改为 `-af apad -t <renderSec>`：**音轨不足的部分补静音，画面长度由 layout 唯一决定**，
  不再受音轨长度左右。
- **`scripts/qc_check.py` 抽帧判据改为「体积 + 内容」双条件**：
  体积低于本片中位数 35% 时不再直接判可疑，先看该帧的颜色数与标准差 ——
  片头淡入起点、纯文字面这类**合法的极简画面**体积天然小，旧判据会稳定误报。
- **`qc_check.py` 时长差文案**：原先「成片差 0.48s」会被读成缺陷，
  实际是段间 gap 与片尾留白的设计值；已改为分别列出「音轨 / layout 期望 / 成片」三个口径。

---

## [1.2.2] — 2026-09-21 — 首个公开版本

### 新增

- **`scripts/lint_frames.py`** —— 渲染前的画面静态体检。在花时间渲染整片之前，先检查八条
  画面契约与已知坑：外部字体 / CDN 引用、硬编码颜色字面量、缺失 `window.__tl` 注册、
  CDN 版 GSAP、墙钟逻辑（`setInterval`、`requestAnimationFrame` 计数）、CSS `transition`
  入场、`B('…') || 数字` 兜底写法、侵入字幕禁区的内容、缺失中文字体族。
- **`scripts/peek_frame.mjs`** —— 单帧速览。把一个场景 seek 到若干时点截图，耗时是**秒级**，
  于是不用渲全片就能判断画面设计。`--at` 收的是百分比，不是帧号。
- **双语项目 README**（`README.md` 中文为默认，`README.en.md` 英文）。
- **开源治理文件**：`LICENSE`（MIT）、`THIRD_PARTY_NOTICES.md`、`CHANGELOG.md`、
  `CONTRIBUTING.md`、`licenses/Apache-2.0.txt`、`.gitignore`、`.gitattributes`、
  GitHub issue / PR 模板，以及 CI 工作流。

### 修复

- **`speech_end_sec` 在冷跑与缓存重跑之间不一致**（lessons #31）。`_result()` 量的是已经裁过
  静音的输出文件，于是头部裁剪量被减了两次：冷跑报 `7.541s`，缓存重跑报 `7.696s` ——
  0.155s 的差异破坏了「两次渲染逐帧一致」的保证，并让末块字幕提前消失。现在统一存**裁后
  坐标系**下的值。

### 变更

- 文档：`scripts/lint_frames.py` 与 `scripts/peek_frame.mjs` 补进命令序列与文件表
  （两者此前都没有被文档记录）。
- 文档：lint 现在是工作流里的显式阶段，位置在生成字幕之后、渲染之前。
- 文档：删除对私有客户项目的引用，使技能可以公开发布。
- 文档：README 精简 —— 移除**面向智能体执行**的七条命令序列与「命令参考」表（这些属于
  `SKILL.md` 的职责），改为只向使用者交代**视频项目结构**与产物位置；同时删去「路线图」
  与文末作者签名。-150 行，中文 364→295 行、英文 390→319 行。
- 许可：风格目录衍生自 Apache-2.0 内容，现已带上完整的来源署名。

### 备注

- 从实战回填：预览渲染会清空帧目录（`--keep-frames`）、重渲单个场景的临时项目法、
  以及「开场 0.5 秒内就必须出现主角」的冷开场规则（lessons #32–#34）。

---

## [1.2.1] — 2026-09-20

四个渲染 / QC 正确性修复，全部是靠给渲染器加探针找出来的，而不是靠肉眼看。
详见 `references/lessons.md` #27–#30。

### 修复

- **`tl.pause(t)` 会静默吞掉本次 seek 的回调。** GSAP 的签名是
  `pause(atTime, suppressEvents)`，第二参默认为 `true`，于是 seek 触发的任何
  `onUpdate` / `onStart` / `onComplete` 都被丢弃。用 `onUpdate` 写的计数器因此在成片里恒为
  初值 —— 不报错、不告警、缩略图尺寸正确，静态检查也查不出来。渲染器与封面器现在调用
  `tl.pause(t, false)`。文档同时把数字滚动引导向**纯 transform 的「数字卷轴」**，
  完全不依赖任何回调。
- **传给 `chromium.launch()` 的 `deviceScaleFactor` 被静默忽略。** `viewport` 与
  `deviceScaleFactor` 都是 context 级选项，只在 `newPage()` 上生效。封面实际写成了 1 倍图，
  而日志声称 2 倍。现在构建用 PIL 核验输出尺寸，不再信日志。
- **QC 抽样只覆盖了视频前四分之一。** `qc_check.py` 取字幕块起始时间后写成 `pts[:samples]`，
  拿的是**前 N 块**而不是均匀铺开。一条 39 块的视频抽了 12 块，只覆盖 0.25–23.86s，后 6 个
  场景一帧没抽，却报告「全部通过」。现在按步长在全片范围均匀抽样。
- **封面排版是在动画中途量的。** 校验紧接页面加载后就跑，读的是 `fromTo` 起始值而不是稳定
  终态，于是报出幽灵偏移。现在测量前先置 `__MG_RENDER__` 并 seek 到 `tl.duration()`，
  与封面渲染器完全一致。

---

## [1.2.0] — 2026-09-20

### 新增

- **封面双方案。** 每条成片现在产出两张独立排版的封面而不是一张：`cover_169.png`
  （1920×1080，输出 3840×2160）用于信息流与播放器，`cover_34.png`（1440×1080，
  输出 2880×2160）用于主页栅格。
  - `scripts/cover_build.mjs` —— 封面渲染器，复用场景渲染器的确定性 seek 内核，但有三处
    刻意不同：不带字幕层、只 seek 到单个「封面时刻」（默认 `--at last`）而不是逐帧步进、
    以及默认 2 倍输出。
  - `assets/cover-template.html` —— 封面模板，三个必需元素写在文件头注释里。
  - `references/cover-guide.md` —— 重排对照表、尺寸规则、上传策略与自检清单。
- `scripts/new_project.py` 现在会把两份封面 HTML 一起生成到新项目里。

### 备注

- 两张封面是**共享同一套视觉基因的姊妹版式，绝不是一对裁切**。从 16:9 裁 3:4 会丢掉
  57.8% 的画面宽度（1920 → 810px），必然把大字钩子切掉。重排改的是构型本身：悖论视觉
  从「右侧左右并置」变成「上方竖排堆叠」，钩子从两行变成三行。

---

## [1.1.0] — 2026-09-20 — 首个打包发布

### 新增

- 核心流水线：`new_project.py` → `tts_build.py` → `timeline_build.py` → `subs.py` →
  `render_video.mjs` → `qc_check.py`。
- **确定性 seek 渲染器**（`render_video.mjs`）。不录活页面的屏，而是每一帧都靠 seek
  GSAP 时间轴（`tl.pause(t, false)`）并同步 CSS 动画
  （`document.getAnimations().currentTime = t*1000`）后再截图。这消掉了实时录制的一整类
  失败：没有起播竞态、没有字体加载超时、没有不稳定的引导期。
- **`B('块文本')` 节拍同步。** 画面动画按**匹配字幕块文本**定位，而不是写死帧号，于是改解说词
  会重排全片时序，而一个画面文件都不用动。
- `scripts/subs.py` —— 字幕三出口（运行时 JSON、SRT/VTT 外挂、渲染器注入的画面内层），
  外加每场景生成一份 `beats.js`。
- `scripts/make_theme.py` —— 四个预设 + 按主题词推色，写出唯一颜色来源 `theme.css`。
- `scripts/qc_check.py` —— 流 / 时长 / 响度 / 抽帧体检，附抽帧速览图。
- `scripts/import_styles.py` —— 移植期一次性工具，把模板设计规范转写成
  `references/style-catalog.md` / `.json`。
- 23 种画面风格目录，8 个类别，按改编成本分类。
- `setup_env.sh` 做首次环境自检，`--install` 装缺失依赖；`package_skill.py` 打可移植 zip。

[1.2.3]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.3
[1.2.2]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.2
[1.2.1]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.1
[1.2.0]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.0
[1.1.0]: https://github.com/OneMoh/html-explainer/releases/tag/v1.1.0
