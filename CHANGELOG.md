# 变更日志

`html-explainer` 的所有重要变更都记录在这里。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

`1.2.2` 之前的版本（`1.1.0` / `1.2.0` / `1.2.1`）都是私有内部发布，
在这个公开仓库里没有对应提交，所以**不给链接**。
**`1.2.2` 是 GitHub 上的首个公开版本**，`1.2.2` 起每个版本都有对应的 git tag。

---

## [1.4.1] — 2026-09-26

> 出片实战（小米 / 华为那期，11,146 帧 / 22 场）踩到的一个**静默失败**：
> 成片标称 6:11、实际只有 3:41 有画面，而 ffmpeg 退出码为 0、每场日志都报齐。

### 修复

- **★★ `scripts/render_video.mjs`：场景帧号边界漏 1 帧，后果是成片**中段断流**。**
  旧写法在算 `gfEnd` 时用 `Math.round((cursorSec + dur + gap) * fps)` **现场重算**，
  而下一轮的 `gf` 用的是**累计后**的 `cursorSec` —— 同一时间点在 float64 上可能差 1 个 ULP，
  舍入后正好差 1（实例：`gfEnd_ai_hw = round(221.5499… × 30) = 6646`
  vs `gf_layout = round(221.5500… × 30) = 6647` → **6647 谁都不写**）。21 个边界里中了 1 个。
  连锁反应才是要命的地方：截图阶段 `doneFrames` 少 1，但**每场日志都报齐**看不出异常；
  `image2` 解复用器遇缺号即**停止解码**；而命令行里的 `-t <renderSec>` 仍把**容器时长写成全长**，
  `ffmpeg` **退出码还是 0** → 产出「`Duration: 00:06:11.54` 看起来完全正常、实际视频流只有
  6,646 帧 = 3:41.5、后 150 秒无画面」的坏片，**肉眼抽查几帧也发现不了**。
  改为**构造性无缝**：先一次算好每场起点，令第 i 场的终点帧**直接等于**第 i+1 场的起点帧
  （末场封到 `totalFrames`）。修复后实测 **11,146 / 11,146 ✓**。

### 新增

- **合成前的「帧完整性闸门」。** 逐号核对帧文件，缺帧直接 `die` 并**点名缺在哪个场景**、
  附上可复制的 `--only <id>` 修补命令 —— 拦在 mux **之前**，省掉一次 26 分钟的无效合成。
  `qc_check.py` 的帧数实测能抓到同类问题（第 148 行，lessons `#57`），但那已经到**成片之后**，
  而且不点名场景。
- **`ffmpeg` 合成命令行加 `-xerror`。** 让解复用 / 解码错误变成**非零退出**，而不是静默出片。

### 文档

- `references/lessons.md` 补 `#86` / `#87`：
  - `#86` 帧号边界必须构造性无缝：完整连锁反应（含「`Duration` 正常但帧数少一半」这个
    假象）+ 修复式 + 判别式（`Σ n === totalFrames` 且帧号无缺无重）+ **怎么验成片有没有断流**
    （`ffmpeg -i out/x.mp4 -map 0:v:0 -f null -` 看末尾 `frame=`，必须等于 `layout.json` 的
    `total_frames`；**只看 `Duration` 会被 apad 音轨骗**）。附一条排查纪律：
    复算场景边界**不要用 Python `round()`** —— 银行家舍入 vs JS `Math.round = floor(x+0.5)`，
    在 `.5` 处差一格，会把缺帧**定位到错误的场景**（本次因此白跑一次 `--only layout` 重渲，
    真凶是 `ai_hw`）。
  - `#87` `--only <单场>` 时并发会**退化成 1**（队列里只有 1 场，`conc = Math.max(1, …)`），
    没有多 worker 摊薄固定开销 → 补帧这类小修**默认就该带 `--png-fast`**。实测同机
    0.9–1.2 帧/秒 → **9.4 帧/秒**（636 帧：9 分钟 → 70 秒）；帧体积 +22% 但 PNG 依旧
    逐像素无损，可与默认模式渲出的帧**安全混在同一套序列里**。

---

## [1.4.0] — 2026-09-26

### 新增

- **★ `scripts/check_cover.mjs`：封面终态几何实测器。** 封面规范一直写着「先跑终态测量，再逐条
  肉眼过」，但**没给工具** —— 于是「差 20px 的贴边」和「多出一个字的孤行」这两类只能靠机器抓的
  问题，全落在肉眼里，而肉眼恰恰看不出它们。新工具把自检清单变成机器判据：四边边距 / 钩子字号 /
  **钩子是否仍是画面最大文字** / 钩子行宽 / 孤字断行 / 元素越界；`916` 另判**无左右两栏**。
  先 `tl.pause(tl.duration(), false)` seek 到轴末再量（量中间态等于量错，见下「修复」），
  退出码 0/1 可挂流水线；`--only` / `--json` / `--shot`。
- **封面第三个画幅 `916`（1080×1920，竖版投放）。** `cover_build.mjs` 的 `SPECS` 加一条即生效
  （渲染与自检都是数据驱动的），输出 2 倍图 2160×3840；`--only` 支持逗号分隔。**缺哪张封面帧
  就跳哪张** —— 只投横版的项目不必建 9:16。
- `references/cover-guide.md` 新增「C. 1080×1920」整节：**三段式**构图（角标 0–10% / 视觉
  10–45% / 钩子 50–88%，重心偏上）；**上下边距是「不可裁区」而不是「安全边距」** —— 上 ≥180px
  让开账号与时长层、下 ≥160px 让开标题栏与互动按钮；钩子放大一档到 130–170px、悖论数字缩到
  96–130px；**左右并置必须改上下堆叠**（1080px 宽里放不下两栏）。

### 变更

- `references/cover-guide.md` 从「双方案」重写为「多画幅」：三画幅重排对照表（含钩子容器宽
  1060 / 1220 / 900px）、自检清单分档（边距 / 字号 / 字数）。**每行字数上限改为由容器宽反算**：
  `字数 ≤ 容器宽 ÷ 字号 ÷ 0.97`；硬判据是**行宽 ≤ 容器宽**，字数只是查孤字断行的参考
  （旧值 7 / 5 字是更早一版小字号设计留下的，与当前 130px 字号不匹配）。
- `scripts/render_video.mjs`：ffmpeg 回退链补上**托管 Python 探测**。此前回退只问
  `PY` / `python3` / `python`，而 WorkBuddy 这类环境下 PATH 上根本没有 python（只有
  `~/.workbuddy/binaries/python/...`），于是「PATH 无 ffmpeg → 问 python → python 也不在 PATH」
  一路静默落空，最后只报一句「找不到 ffmpeg」，看不出是回退链断了。现在主动扫托管 venv 与
  解释器目录（Windows `Scripts/python.exe` 与 POSIX `bin/python` 都覆盖）再问。
- `SKILL.md` / `scripts/new_project.py` / `assets/cover-template.html` / `README`：封面口径从
  「两张」统一为「多画幅」，确认点 1 增加「投放画幅」一问。
- `README.md` / `README.en.md` 的版本徽章此前停在 `1.3.1`（落后 `SKILL.md` 两个版本，自洽性检查
  只看 SKILL 与 CHANGELOG 所以没报）—— 本次一并对齐。

### 修复

- **封面验收的两个假阳性（这一版的由来）。**
  ① **等固定毫秒数会量到中间态**：第一版脚本 `goto` 后等 650ms 就量，而 `cover_34.html` 的时间轴
  长 **1.54s** —— 650ms 时钩子还停在 `opacity:0`，既没进边距统计，又让脚本把悖论数字「6.02」
  （112px）当成「画面最大文字」并误判为钩子，报出「上边距 84px / 下边距 82px / 钩子字号只有
  112px」三条**不存在的排版事故**。改为 seek 到轴末。
  ② **钩子识别与「钩子是否最大」是同一条判据**：第一版「钩子」= 字号最大的带文字元素，
  而检查项是「钩子字号是画面最大」—— 自己验自己，**永远 PASS，等于没查**。改为把「句子级」
  元素（自身文本 ≥6 字位、且不是纯数字串）作为候选取最大者，再**另外**与全场最大字号比；
  数字压过钩子只提醒（上限 钩子×1.35），文字压过才 FAIL。
- `references/lessons.md` 补 `#82`–`#85`：9:16 独立排版三条纪律 / `SPECS` 数据驱动与 `--only`
  逗号分隔 / 验收脚本必须 seek 轴末（任何「等 N 毫秒再量」都是定时炸弹）/ 钩子识别与
  「是否最大」要拆成两条独立判据。

---

## [1.3.3] — 2026-09-25

### 新增

- **★ `scripts/check_layout.mjs`：渲染前的几何体检器。** `lint_frames.py` 是**静态文本**检查
  （禁色值字面量、禁 transition、中文字体族…），**它看不见几何**；而画面里最常见的两类
  「静默出错」恰恰是几何问题 —— **遮挡**（图表轴标签被底部证据条压住、两段文字打架）和
  **越界**（内容溢出画布、压进字幕带）。两者都 lint 全绿、渲完几千帧才被人眼发现。
  新工具把「谁和谁重叠、谁越界」变成可枚举清单（`out/layout_report.md`）：
  侵入字幕禁区 / 出画 / 文字被遮挡 / 文字重叠 = **ERROR**（退出码 1，可挂流水线）；
  越安全边 / 文字压色块 / 色块重叠 = WARN；「疑似该跟图形共心却差了 N 像素」= INFO。
  度量基准是被三个版本的假阳性逼出来的：**量字墨**（`Range` 逐行，不是元素框）+ **纵向收成
  em 盒**（行盒含字体留白，紧排大字号会擦边），带底色的元素仍用元素框。
- **★ `scripts/frame_at.py`：排障入口 —— 报「几分几秒」直接落到那一帧。**
  `--at 1:23` 给出场景 id / 帧号 / `frames/<id>.html` / 当刻字幕块（反查代码里的哪一句
  `B('…')`）/ 整帧图 / 底部 260px 禁区带裁图 / **场景终态帧**；另有 `--list`（全片场景时间表）、
  `--box x0,y0,x1,y1`（再裁可疑区）、`--final`、`--no-images`。
  配合带视觉的模型看图 → 改一个 HTML → `--only <id>` 局部重渲 → 回到同一时间点复核。
- `peek_frame.mjs` 新增 `--guides`：叠**十字中线 + 字幕禁区线 + 左右安全边**。
  判「元素有没有对齐」必须有参照物 —— 没有基准线时，肉眼判不出「圆点在不在图形中心」。
- `.github/ISSUE_TEMPLATE/bug_report.yml` 新增「★ 出错的位置在几分几秒？」字段。
- `tests/geometry-fixture/`：**几何体检的证伪样本** —— 一个文件里塞进 issue #1 的三类症状
  （越界 / 遮挡 / 错位），期望 ERROR 2 / WARN 0 / INFO 1。检查类工具必须能被证伪：
  拿合格项目报 0 ERROR 是**待证实**而不是通过（见 `references/lessons.md` #76）。
- `references/frame-contract.md` 新增「几何：两类不会报错的错，和它们的确定性判据」一节，
  含**一个几何体只准有一个坐标系**（SVG 图元与 HTML 部件不得混用两套基准）；
  第 6 条把安全线口径写清（170px 硬底线 / 176px 设计基准）。
- SKILL.md 新增「★ 画面出错怎么定位」一节（报时间点 → 定位 → 看图 → 改 → 局部重渲 四步），
  质量标尺补「几何 ERROR 清零」；`references/lessons.md` 新增 #76–#78。

### 修复

- **★ `qc_check.py` 的帧数校验在部分 ffmpeg 构建上被静默跳过。** 旧实现只从 ffmpeg 的
  stderr 里找 `frame= …` stats 行，而那条 stats 行**打不打印、字段前缀长什么样，随
  ffmpeg 构建而变** —— 有人用 gyan.dev 7.0 full build 时 stderr 里一条都没有，
  QC 报告里只剩一句 `⚠ 无法实测视频流帧数（跳过帧数校验）`，帧数校验形同不存在。
  现在同时读 `-progress pipe:1` 的机器可读流（跨版本稳定），两条通道任一命中即可。
  报这条的用户是自己发现的，不是我们发现的。

---

## [1.3.2] — 2026-09-25

### 修复

- **★ 渲染器的字幕层/进度条是「白字 + 黑描边」写死的，做亮底（浅色背景）片时字幕直接看不见。**
  症状：帧 HTML 全对、`lint_frames.py` 全绿，渲完 4950 帧才发现宣纸底的场景字幕读不出来 ——
  坏的是 `render_video.mjs` 注入的 `OVERLAY_CSS`，与帧主题无关。
  现在字幕层改为读主题变量：`--mg-sub-fg` / `--mg-sub-stroke` / `--mg-track` / `--mg-tick`
  （各自带原来的写死值作 fallback）。**主题文件里给亮底作用域补一份色即可，旧项目零影响。**
  详见 `references/lessons.md` #75。

### 新增

- **★ 确认点 0：配色 / 风格一律先问用户，禁止凭记忆拍板。** 流程从「四个确认点」改为
  「五个」。开工（乃至挑风格）之前必须先给用户 **2–4 个候选**，每条写清
  **① 色号 hex ② 一句气质描述 ③ 适合什么内容**；风格模板同样要列候选，
  不许静默从「上次挺好用」的记忆里定。用户自带色号时照他的落地，但要回报
  「哪个色做哪个语义」请他确认。同步更新 `references/workflow-guide.md`。
- `references/lessons.md` 新增 #72–#75：**双底混用（墨黑暗底 / 宣纸亮底）的正确做法**
  （把亮底做成一整套变量的作用域翻面 + 全片唯一一份明暗名单，组件 CSS 一个字不用改）、
  **两条由「抽变量」引发的 lint 假失败**（`var(--font-sans)` 会击穿中文字体族检查；
  非纯黑白的 `rgba()` 一律算色值字面量，要变成主题变量）、**亮底片的字幕层换肤**、
  以及确认点 0 的由来。

### 说明

- `scripts/` 除 `render_video.mjs` 的 `OVERLAY_CSS`（纯增量、带 fallback）外未动；
  `assets/` 未动。已跑通的项目无需重跑，除非它用了亮底。

---

## [1.3.1] — 2026-09-23

### 修复

- **★ `tts_build.py` 走火山引擎时，`project.json` 里的中文音色名没被解析成音色 ID，
  合成恒失败。** 症状是服务端返回
  `code=55000000 message='resource ID is mismatched with speaker related resource'`，
  报错信息完全看不出是「名字没解析」。
  根因：`resolve_voice_token()` 只在 `tts_setup.py` / `tts_volcano.py` 的 CLI 路径被调用，
  `tts_build.py` 是把 `project.json` 的 `voice`（如 `解说小明 2.0`）**原样**透传给
  `tts_volcano.synthesize()` 的，而 `speaker` 字段只认 ID。
  修法（两层，任一层都能挡住）：
  1. `tts_volcano.synthesize()` 入口处补 `voice = resolve_voice_token(voice, DEFAULT_VOICE)`
     —— 接口包是唯一知道音色表的地方，任何调用方都不该自己解析；
  2. `tts_build.py` 读 `project.json` 后先解析一次，让日志与 `audio-manifest.json`
     里记的是可直接复制的真 ID。

  > 教训：**「文档里写了有这一步」不等于「每条代码路径都有这一步」。**
  > `references/volcano-tts.md` 当时已写明「音色名解析走 `resolve_voice_token()`」，
  > 但那条路径实际没被接上 —— 光看文档会误判成「密钥/账号没开通音色」，
  > 于是去逐个测音色（实测 7 个 2.0 音色全都可合成），白绕一圈。

### 新增

- **★ 逐帧截图模式可选，照片类片子提速 5–13 倍。** 起因是一条全片满幅照片的片子
  实测只有 **1.93 帧/秒**（9356 帧要 84 分钟）。逐项拆解后发现瓶颈根本不在 seek
  （只占 21ms/帧），而在 **PNG 编码（561ms，占 96%）**，且**与画面内容强相关**：
  纯色/纯 CSS 图形帧只要 45ms，照片满幅帧要 582ms（13×）—— 这就是「CSS 类项目
  几百帧/分钟、照片类项目掉到 1.9 帧/秒」这个量级差的全部原因。
  更关键的是**这段编码在浏览器进程内串行**：并发 1/3/6 路的总吞吐实测
  1.80 / 1.86 / 1.87 帧/秒 —— `--concurrency` 对帧数毫无帮助。

  | 截图方式 | 单页 | 3 页并发 | 体积/帧 | 对无损基准 |
  |---|---|---|---|---|
  | Playwright PNG（默认，未变） | 1.80 帧/秒 | 1.86 | 2.5MB | 无损 |
  | **`--png-fast`**（CDP `optimizeForSpeed`） | 7.36 | 10.45 | 3.0MB | **无损**（PSNR 99dB、最大差 0） |
  | **`--jpeg --jpeg-quality 95`** | 16.07 | 29.01（5 路 32.3） | 0.54MB | PSNR 41.65dB |

  新增开关（**默认行为完全不变**）：`--png-fast`、`--jpeg-quality N`（默认 82）、
  `--crf N`、`--preset <名>`。其中 `--crf`/`--preset` 顺带把「帧容器」与「成片码率」解耦 ——
  旧行为里 `--jpeg` 会连带降成 `crf23/veryfast`（那是"草稿"语义），
  成片现在可以显式给 `--crf 18 --preset medium`。

  选用判据（已写进 `SKILL.md` 与 `references/workflow-guide.md`）：
  **帧里有满幅照片 → 换模式；`--png-fast` 要无损，`--jpeg --jpeg-quality 95` 要速度。**

- **`qc_check.py` 新增「实测视频流帧数」校验。** 原先只比容器时长，而容器时长会被音轨撑起来：
  帧序列中间若有缺口，ffmpeg 的 image2 序列会在缺口处**停下且退出码仍是 0**，
  视频流只有前半段，Duration 却照常显示完整长度（假通过，见 `lessons.md` #57）。
  现在用 `-map 0:v:0 -f null -` 数真实帧数，与 `layout.json` 的 `total_frames` 比对；
  不一致直接判 fail，并在报错里附上「找帧序列缺口 → 补齐 → `--mux-only`」的命令。
- `tts_build.py` 的日志与清单现在打印/记录**解析后的音色 ID**，便于直接对照官方文档排错。

---

## [1.3.0] — 2026-09-23

### 新增

- **★ 火山引擎（豆包）语音合成 2.0 作为可选配音引擎。** 原先只有 edge-tts；
  现在 `tts_build.py --provider edge|volcano`，`project.json` 记 `provider` 字段。
  两个引擎产出的 `audio-manifest.json` **结构完全一致**（`boundaries` 均为「秒 + 原始坐标系」），
  因此 `timeline_build.py` / `subs.py` / 渲染器**零改动**。
- **`scripts/tts_volcano.py`** —— 火山 TTS 接口包（SDK 层）。走 **HTTP Chunked 单向流式**
  `POST /api/v3/tts/unidirectional`：与 edge-tts 形态同构（发一次、收一串），
  故缓存 / 硬超时 / 退避重试 / 裁静音 / 两级时钟全部原样复用。
  **零第三方依赖**（只用标准库 `urllib`）。`--check` / `--voices` / `--synth` 三个子命令。
- **`scripts/tts_setup.py`** —— 配音方案向导：选方案 → 缺密钥则生成 `tts.env` 模板并停下 →
  测连接 → 选音色 → 写回 `project.json`。输出 `NEXT_ACTION=…` 供 agent 判断下一步。
- **`tts.env.example`** —— 密钥模板（入库；真实 `tts.env` 被忽略）。

### 安全

- **★ 密钥纪律：agent 不读、仓库不记、日志不吐、分发不含。** 四条都由结构保证：
  ① 密钥只从 `tts.env` 读取，而只有 `tts_volcano.py` 读它 —— agent 只调接口包；
  ② 异常信息过 `_redact()` 脱敏（只抹本次实际加载的密钥值与 `AKLT…` 形态 token，
     保留 reqid/logid 以便排查）；
  ③ `.gitignore` 新增 `tts.env` / `*.env` / `*.key` / `*.pem` / `secrets/`；
  ④ **`check_integrity.py` 新增「密钥防线」检查**（gitignore 覆盖 + 遍历仓库抓非空密钥赋值与
     `AKLT…` token，空模板不算违规），CI 在无密钥环境下跑通。
- **★ 修掉一个真实的密钥外泄口：`package_skill.py` 原先不排除 `tts.env`** ——
  技能目录里若放了这个文件，打包会把用户的 API Key 一起塞进可分发的 zip。
  已加入 `EXCLUDE_NAMES` / `EXCLUDE_SUFFIX`（`tts.env`、`*.env`、`*.key`、`*.pem`），
  模板 `tts.env.example` 保留。已实测：打包后 zip 内无密钥文件、内容级扫描无密钥串。

### 修复

- **`tts_setup.py` 的方案选定后未落盘**：用户选火山 → 生成模板 → 填密钥 → 回来跑 `--check`，
  此时 `project.json` 还写着 `edge`，会**静默去测 edge 并报「就绪」**。现在方案一旦确定立刻写盘。
- `--check` 现在先打印 `测试方案：<provider>`，避免「测的其实不是你以为的那个」。
- `ensure_env_file()` 的查找顺序改成与 `tts_volcano.env_candidates()` 一致
  （项目目录 → 技能目录 → 新建于项目目录），消除「向导认技能目录的、接口包认项目目录的」错位。

### 修复（首次真机联调后补齐）

> v1.3.0 在合并前用**真实 API Key** 跑了完整链路（向导 → 真合成 → timeline → subs → 打包），
> 又抓出 4 个只看代码发现不了的问题。以下都已修复并实测通过；v1.3.0 此前从未发布，故不另起版本号。

- **★ 字级时间戳必须显式开 `audio_params.enable_subtitle: true`。** 官方文档的响应示例里
  `sentence.words[]` 是有值的，容易误以为「默认就给」——**实测不传这个参数 `words` 恒为空数组**
  （同文本对照：`false` → `words=0`，`true` → `words=10`）。而且它**完全不报错**：音频正常、
  时长正常、`sentence.text` 也正常。下游 `subs.py` 会静默退回**按字数插值**，成片照样出、
  字幕开始飘。现已在接口包默认开启，并在拿到音频却没有时间戳时返回 `warning`
  让 `tts_build.py` 打到台面上。该能力仅豆包 2.0 的中英文音色支持。
- **计费字数永远是 0**：`usage.text_words` 挂在**结束标记那一行**（`code=20000000`），
  而解析循环先判结束标记就 `continue` 了，那一行从没被读完。同时补上
  `X-Control-Require-Usage-Tokens-Return: *` 请求头（不传该头服务端根本不返回 `usage`）。
  修后实测：`计费 20 字` 与文本逐字对上。
- **★ 命中缓存时丢失首裁量 → 首跑与重跑产出不一致。** 词边界是原始坐标系，下游靠
  `lead_cut_sec` 平移；缓存只存了边界数组，于是**重跑 `lead_cut_sec=0`、首跑是 0.037**
  ——字幕整体晚一帧，且只在第二次跑时出现。缓存格式改为
  `{"boundaries": [...], "lead_cut_sec": x}`，并对旧版裸列表格式做兼容读取。
- **CLI 把中文音色名原样当 `speaker` 发出去**：`--voice "云舟 2.0"` 被服务端拒绝，
  报的是 `55000000 resource ID is mismatched with speaker related resource`
  ——完全看不出是「名字没解析」。现把 `resolve_voice_token()`（名称/序号/ID）与
  `parse_rate_percent()`（`+8%`/`8`/`0.08`）都收进接口包，`tts_setup.py` 改为委托，
  消除两份实现跑偏的可能。
- 火山项目的 `rate` 会沿用 `new_project.py` 写的 edge 格式 `+8%`，现按引擎清洗
  （火山存 int 百分比）；`--status` 在 `rate=0` 时不再误报「未设置」（`0` 是 falsy）。
- `check_integrity.py` 缺模板时新增提示：若同目录存在 `tts.env`，直接说明
  **「疑似把模板改名成了 tts.env」**（实测踩到的真实用法）。

### 备注

- 火山接口的坑已处理并写进文档：**结束标记 `code=20000000`（不是 0，误判会丢最后一段音频）**、
  单请求文本上限 ~200 字（超了按标点切分并按实际时长平移词边界）、
  **字级时间戳需显式开 `audio_params.enable_subtitle`**（见上）。
- `openspeech.bytedance.com` 是境内端点，接口包**默认绕过系统代理直连**；需要时设 `VOLC_PROXY`。
- edge 独有的「相邻数字补逗号」对火山**不启用** —— 它会改动送进去的文本，
  影响词边界与解说词的逐字对齐，而火山不熔读相邻数字。
- 真机联调的验收口径：3 段共 20 块字幕，**每块起点与其首字词边界的误差均为 0.000s**；
  首跑与缓存重跑的 manifest 深度 diff（982 个字段）完全一致；
  打包 zip 38 个成员，密钥文件名与内容级扫描**双无命中**。

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

### 文档勘误

- **`lessons.md` 第 33 条与本次改动自相矛盾，已同步修正**：该条原写「`render_video.mjs`
  没有单场景开关」（本次新增的 `--only` 正是此开关），且给出的主序列合成命令带 `-shortest`
  并注明「与渲染器逐字一致」——**照抄会把上面刚修掉的片尾截断 bug 原样装回去**。
  现改为：末场优先用 `--only`，临时项目法保留给「被改场景不在末位」的情形；合成命令同步换
  `-af apad -t <renderSec>` 并加一段「别用 `-shortest`」的说明。
- `--only` 的示例场景名由本项目专有的 `coda` 换成通用占位 `<场景id>`。

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

## 1.2.1 — 2026-09-20

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

## 1.2.0 — 2026-09-20

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

## 1.1.0 — 2026-09-20 — 首个打包发布

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

[1.4.1]: https://github.com/OneMoh/html-explainer/releases/tag/v1.4.1
[1.4.0]: https://github.com/OneMoh/html-explainer/releases/tag/v1.4.0
[1.3.2]: https://github.com/OneMoh/html-explainer/releases/tag/v1.3.2
[1.3.3]: https://github.com/OneMoh/html-explainer/releases/tag/v1.3.3
[1.3.1]: https://github.com/OneMoh/html-explainer/releases/tag/v1.3.1
[1.3.0]: https://github.com/OneMoh/html-explainer/releases/tag/v1.3.0
[1.2.3]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.3
[1.2.2]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.2
