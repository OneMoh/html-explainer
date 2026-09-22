# 踩坑台账（lessons）

血统：上半部分继承自 anything2explainer 与 html-video-workbuddy-driver 的实战，
下半部分是本技能（确定性 seek 渲染）自己的记录。新经验 **持续追加**。

## 继承来的坑（已在技能设计里规避，但要知道原理）

1. **帧时长必须用 MP3 容器时长，不是 TTS 词边界时长**。词边界每段少算
   ~0.81–0.89s（LAME padding），5 段累积 4.3s 音画错位。本技能：tts_build
   裁首尾后回填 `container_duration_sec`，timeline_build 按它排全局轴。
2. **两级时钟**：段长用容器时长（音画同步），末块字幕收尾用语音真实结束
   （`speech_end_sec`）。混用 → 字幕比语音多停 0.8s/段。
3. **词边界字幕，绝不按字数插值**：中文同字数时长差 3 倍（"AI" 0.71s vs "让" 0.17s）。
4. **edge-tts 7.x 必须显式 `boundary='WordBoundary'`**，默认 SentenceBoundary
   整句一个事件；**相邻数字熔读**（沪深300+4479.55 → 三百万…），数字间补中文逗号。
   硬超时 45s（websocket 会永久挂起零日志）+ 4 次指数退避（端点限流）+ 缓存 sig 含 boundary 与 trim。
5. **edge-tts 语速标定**：同一句话跨 RATE 对比，`dur×(1+rate)` 是常数 → 线性。
   长片默认 +8%；1 分钟内高密度短片可到 +20%~+37%（听感优先，别只对齐字/秒数字）。
6. **字幕是屏幕文本**：去句读标点、子句连写；要断开用 `|` 再切一块，不是把标点加回来。
7. **每块字幕 ≥0.6s**（water-filling 按真实语速比例重分配，起点不动）。
8. **HTML 帧绝不引 Google Fonts**（国内不可达；实时录制系 6s/link 超时 → 成片被裁成
   静止尾帧）。本技能用确定性 seek，风险从「毁片」降级为「5s 硬顶后用兜底字体」，
   但字体不一致仍会让前后帧字重跳变 —— 契约照旧禁止。
9. **实时录制的 `__hvUnfreeze` 起播坑**（html-video）：单文件帧没有 `__hvPlayAll`，
   时间轴无人 play → 成片全空且零报错。本技能的 seek 渲染器**整类消除**此问题
   （渲染器主动 seek，帧根本不需要起播逻辑）。
10. **字幕带禁区**：底部 80–170px 只给字幕；内容元素 `bottom < 170px` 一律抬到
    176–210px。入场轨迹也不许穿带。
11. **中文文件名 + Windows ffmpeg**：UTF-8 按 ANSI 解析 → No such file。
    项目目录、输出文件、抽帧全部 ASCII；中文名最后在资源管理器里改。
12. **Git Bash 的 `/tmp` ≠ Node 的 `/tmp`**（Windows 上 Node 解析成 `C:\tmp`）；
    给 Node/Python 传路径用 `C:/...` 正斜杠绝对路径。
13. **给 Python 传含正则/反斜杠的代码不要用 heredoc/-c**（反斜杠被静默吞），
    写成 `.py` 文件再执行。
14. **QC 抽帧先看体积**：同片内「明显偏小」的帧 = 疑似空画面，比肉眼快得多。
    ⚠️ 这条继承自亮底主题的项目，**阈值不可当常数用** —— 见第 19 条（改自适应）。
    附参考量级：亮底主题纯背景 ≈90KB / 有内容 220KB+；
    暗底主题（本技能默认风格）纯背景 ≈20KB / 有内容 ≈35–60KB。

## 本技能自己的记录（持续追加）

15. **（2026-09-20 首版验证）seek 渲染确认**：`tl.pause(t, false)` 同步渲染 inline style，
    `document.getAnimations().currentTime = t*1000` 同步 CSS keyframes；双 rAF 后
    screenshot 能拿到正确的中间态（opacity 0→1 的半透明帧逐帧递增）。
    （第二参 `false` 的必要性见 #27 —— 少了它，`onUpdate` 类回调全不触发。）
16. **playwright-core 无浏览器探测**：`chromium.launch()` 不带 executablePath 时不会
    自动找系统 Chrome/Edge —— 必须显式传 `executablePath`（render_video.mjs 已内置探测链）。

17. **★ `page.evaluate` 的字符串陷阱（最隐蔽的静默失败，2026-09-20 定位）**：
    `page.evaluate` 传**字符串**时，Playwright 只把它当**表达式求值一次**。
    所以传 `"async (o) => { ... }"` 得到的是「一个箭头函数对象」而不是执行结果 ——
    函数体**根本不执行**，返回值因不可序列化变 `undefined`，**零报错**。
    症状：成片每帧都是静止首帧（只有纯 CSS 动画在动，GSAP 控制的元素停在 opacity:0）。
    正确写法：把回调写成**真正的 JS 函数字面量**（不是模板字符串），
    `await page.evaluate(frameSeek, { t, globalT, total })`。
    排查手法：在 evaluate 里 `return` 一个探针值，看是否 undefined；或先试「内联箭头函数」
    能跑通、换成字符串就挂 —— 立刻锁定此坑。

18. **`browser.launch({ viewport })` 不继承给 `newPage()`**：viewport 必须逐 page 指定
    `browser.newPage({ viewport: { width: W, height: H } })`，否则成片静默变 1280×720。

19. **QC 体积阈值必须按主题底色自适应**：固定「<100KB = 空画面」在黑底稀疏文字主题上
    会把全部合规帧判成假阳性（实测本片中位数仅 40KB）。改为**取本片抽帧体积中位数的
    35%** 作可疑线（叠加 12KB 绝对下限兜底），跨亮底/暗底主题都稳。
    真·空画面会明显掉到中位数 1/3 以下，仍能被抓住。

20. **（2026-09-20 补）画面风格库来自 html-video 的 23 个模板，不是「一种暗底风格」**。
    务必先读 `references/style-catalog.md` 再动手 —— 8 个类别、12 个 rich 模板
    （零改动可渲染）与 11 个 gsap 模板（需重写）。挑风格时同时核对**时长档**
    （3–6s 的片花模板硬拉到 20s 会显得空）。

21. **html-video 模板分两种结构，改编成本差别很大**（2026-09-20 实测）：
    - **rich**：单文件 + 纯 CSS `@keyframes` 时间轴 + 带 `SKILL.md` 风格规范
      （画布/字体/时间轴/配色纪律）。**seek 渲染器零改动即可驱动** ——
      因为时间轴由 CSS `animation-delay` 声明，`document.getAnimations().currentTime`
      可直接定位。实测 bold-signal 的 9 条动画全部可 seek（0.3s 只有编号、0.8s 卡在滑入中间态、
      1.5s 全部到位 —— 逐帧确定性正确）。
    - **gsap**：`index.html` + `compositions/*.html` 多组合 + CDN 加载 GSAP。
      **不要搬代码** —— 单帧里没有起播钩子，搬进来会得到静止首帧且零报错
      （就是 #9 的 `__hvUnfreeze` 坑）。只取视觉 DNA（配色/版式/动效意图），
      用 CSS keyframes 重新表达。
    判定：`grep -c '@keyframes'` + 是否有 `data-composition-src` / `compositions/*.html`。

22. **改编 rich 模板必做三步**（漏一步就出问题）：
    ① **删 Google Fonts 换系统字体栈** —— 模板原文一律外链 Google Fonts，
       离线环境下每 link 5s 超时且字体静默回退，前后帧字重会跳变（详见 #8）。
    ② **底部元素抬出字幕带** —— 模板不知道自己会被叠字幕，`bottom:74~104px` 的元素
       会跟硬字幕压在一起（#10）。一律抬到 `bottom:176px` 以上。
    ③ **填真实内容** —— 照模板 `example.md` 的字段填，严禁 lorem ipsum。
    实测：改编 bold-signal / build-minimal / pentagram-stat 三帧混排成片，
    509 帧 / 16.97s、音画差 0.04s、音量 −24.7dB 与源一致、QC 全过，三种风格视觉完全成型。

23. **一个项目可以混排多种模板风格，且这是推荐做法** ——
    8 个场景全用同一个模板会很单调。建议 2–4 种风格轮换
    （如：开场用 bold-signal 强冲击 → 论述用 build-minimal 留白 →
    数据用 pentagram-stat 理性）。字幕层与进度条由渲染器统一注入，
    跨风格视觉一致，各帧无需自管。

24. **风格目录是可再生成的，不要手改**：`scripts/import_styles.py --from <html-video>/templates`
    会重写 `references/style-catalog.md` + `.json`。该脚本能处理两种模板布局
    （`source/index.html` 与 `index.html`），且 YAML 解析支持 `>`/`|` 块标量与任意层级缩进
    （`output.duration.min_sec`）—— 一开始写的浅层解析器漏了 duration 和 description，注意别退回。
    **它是「抄设计规范」，不是代码依赖**：跑完一次，技能就永久拥有风格知识，
    之后做视频不需要 html-video 存在（类比：把菜谱抄回家，做菜不需要原餐厅营业）。
    零依赖验证手法：`grep -rn "html-video" scripts/ assets/ references/` ——
    只应命中注释署名，**不应命中 `import` / `readFile` / `subprocess`**。

25. **（2026-09-20）封面必须两套独立排版，绝不能用裁切**：
    成片 16:9，平台主页栅格按 3:4 裁 → 从 1920×1080 居中裁 3:4 只剩 **810px 宽，
    丢掉 57.8% 的画面宽度**，横跨全宽的大字钩子必然被切。
    正确做法：`frames/cover_169.html`（1920×1080）+ `frames/cover_34.html`（1440×1080）
    两份 HTML 各自排版，共享同一套视觉基因（配色/幕底/主视觉/钩子文案）。
    重排的核心动作是**改变构型**，不只是改间距：
    悖论视觉从「右侧左右并置」→「上方竖排堆叠」；钩子从「左下两行」→「下方三行」。
    实测踩到的两个坑（都已修）：
      · 钩子每行字数是硬约束 —— 16:9 版 ≤7 字/行、3:4 版 ≤5 字/行。
        超了会出现孤字断行（「错在哪」的「哪」单独成行），极难看。
        **可反算**：行宽 ≈ 字数 × 字号 × (1 + letter-spacing)，必须 ≤ 容器宽，
        否则浏览器在任意字间断行。所以字号上限 = 容器宽 ÷ (最长行字数 × (1+ls))。
        例：16:9 钩子第 2 行 7 字、ls=-0.022、容器 920px → 字号 ≤ 920/(7×0.978) ≈ 134，
        取 126 留余量（实测：134px/880px 时末行出孤字，改 126/920 后通过）。
      · 两份的底部元素位置**必须各自算**。3:4 版钩子占位更满，
        直接沿用 16:9 的 `bottom:104px` 会跟末行大字重叠（实测撞了）。
        3:4 版钩子 118px 三行时，角标必须压到 `bottom:52px`。

26. **封面渲染器（`cover_build.mjs`）复用场景渲染器底座，三处差异**：
    ① 不注入字幕层/进度条（封面不要字幕）→ 底部**无禁区**，但仍留 ≥96px 平台安全边距
    ② 不逐帧，只 seek 一个「封面时刻」：默认 `--at last`（`tl.duration()`，取完整态）；
       `--at 0.8` 可挑入场动画中间态（更有张力，适合动感题材）
    ③ 输出单张 PNG，默认 `--scale 2` 出 2 倍图（3840×2160 / 2880×2160）应付平台压缩
    封面帧**允许纯静态**（没有 `window.__tl` 也不报错）——比场景帧宽松，
    因为有的封面就是一张静图。但仍建议挂一条 1.2s 的短时间轴，好在 `--at` 时点微调。

27. **★★（2026-09-20 实测确诊）`tl.pause(t)` 会掐掉本次 seek 的回调 —— 数字滚动/末态回调全失效**：
    GSAP 签名是 `pause(atTime, suppressEvents)`，**第二参默认 `true`**，含义是「本次跳转触发的
    `onStart`/`onUpdate`/`onComplete` 一律不触发」。于是最自然的写法

    ```js
    var p = {v:0}; tl.to(p, {v:100, duration:2, ease:'none',
      onUpdate:function(){ el.textContent = Math.round(p.v); }});
    ```

    在渲染器下 **`el.textContent` 永远是 `0`** —— 补间本身算到了 100，但写 DOM 的那行从不执行。
    症状极隐蔽：不报错、截图照写、体积正常、成片只有「数字不动」，静态合规检查也查不出来。

    **判定证据**（用一个探针脚本 `.mjs` 复现与渲染器逐字一致的 seek）：

    | 写法 | seek 后 `#a` 的值 | 结论 |
    |---|---|---|
    | `onUpdate` + `pause(t)` | `"0"` ❌ | 回调被抑制 |
    | `onUpdate` + `pause(t, false)` | `"100"` ✅ | 确诊 = suppressEvents |
    | `transform` + `pause(t)` | 位移到位 ✅ | 不依赖回调，稳 |

    **两处修法**（本技能采用①+②双保险）：
    ① 渲染器/封面器改 `tl.pause(t, false)`（根因修复，一次性生效于所有帧）
    ② 帧里做数字滚动改用**纯 transform 的「数字卷轴」**（不依赖任何回调，任何 seek 方式都成立）：
       外层 `.strip{overflow:hidden}`，内层 `.val{display:block}`（inline 元素不吃 transform），
       `tl.fromTo('.strip .val', {y:0}, {y:-steps*ITEM, duration:1.4, ease:'power2.out'})`。

    **顺带结论**：`tl.pause()` 无参时不影响；但凡是「seek 到某时刻并期望伴随副作用」的写法，
    都要显式传 `false`。**注意**：放行回调意味着 `onUpdate` 每帧都会跑一次，帧里写 `onUpdate`
    必须保证幂等（只赋值、不 append DOM），否则整片几千帧会累积出灾难。

28. **（2026-09-20 补）#18 的孪生坑：`deviceScaleFactor` 传给 `chromium.launch()` 会被静默忽略**：
    `viewport` / `deviceScaleFactor` 都是 **context 级**选项，只能给 `newPage()`（或 `newContext()`）。
    传给 `launch()` 不报错、不生效 → 封面出成 1 倍图（1920×1080 而非承诺的 3840×2160），
    日志还自欺写着「输出倍率 2x」。**自查手法：渲完立刻 `PIL.Image.open(...).size` 核尺寸，
    别信日志。** 修复：`newPage({ viewport, deviceScaleFactor })` + `screenshot({ scale: 'device' })`。

29. **（2026-09-20 补）QC 抽帧曾只覆盖前 ~1/4 片**：`qc_check.py` 按「字幕块起点」抽样，
    但写成 `pts[:samples]` = **取前 N 块**。一条 39 块的实测片取 12 → 只抽 0.25–23.86s，
    后半段 6 个场景一帧没抽，「全部通过」是假的放心。
    修法：块数多于样本数时**按步长均匀挑**（`pts[int(i*len/N)]`），既覆盖全片又仍落在字幕边界。
    **教训：抽样逻辑写完要 sanity check 一次「最后一个样本的时间 ≈ 片尾」**

30. **（2026-09-20 补）封面排版验收要量终态、不量中间态**：页内脚本若写了
    `if (!__MG_RENDER__) tl.play(0)` 自动起播，则**直接 load 完就量**得到的是 `fromTo` 的
    起始值（`.foot` 会多出 +16px 之类的假偏移，`.paradox` 会 -17px）。
    验收脚本必须先 `addInitScript('window.__MG_RENDER__=true')` 再 `tl.pause(tl.duration(), false)`，
    与 cover_build 的 seek 完全一致 —— 否则你会去「修」一个根本不存在的布局 bug。
    附：写一个十几行的终态测量脚本即可（行数 / 四边边距 / 元素重叠 / 钩子字号全判）。

31. **（2026-09-20 补，v1.2.2）`speech_end_sec` 在「首跑（现合成）」与「重跑（走缓存）」下不一致**：
    `_result()` 里量的是**已经裁过首尾**的 `out_path`（`trim_edges` 原地替换过），
    所以 `speech_window()` 返回的 `de` **已经在裁后坐标系里**，原代码又写了
    `"speech_end_sec": de - head_cut` → **重复扣一次首裁量**。
    症状：同一段解说，首跑报 `语音止 7.541s`、重跑（缓存命中走 `head_cut=0.0` 分支）报 `7.696s`，
    差 0.155s = 首裁量；末块字幕提前消失，且**「跑两遍逐帧一致」的承诺被打破**。
    修法：`"speech_end_sec": de if trimmed else round(dur, 3)`（`de` 已是裁后坐标，不再减）。
    **自查手法**：连跑两次 `tts_build.py`，逐段比对 `speech_end_sec` —— 两次必须完全相同。
    另注：`container_duration_sec`（帧长口径）与 `boundaries`（词边界，原始坐标）都不受影响，
    所以这个 bug **只影响末块字幕收尾与 `__SEG__.speech_end`**，不会造成音画漂移。

32. **★（2026-09-21 实测）`--preview` 渲完会删帧 —— 想留 PNG 必须显式 `--keep-frames`**：
    `render_video.mjs` 尾部有

    ```js
    if (!args.keepFrames && preview != null) { /* 遍历 framesDir 逐个 unlinkSync */ }
    ```

    设计意图是「预览模式顺手清草稿帧省盘」，但**它对已经合成完、正准备复用的帧一视同仁地删掉**。
    本次踩法：为「只重渲 outro 一段」而用 `--preview 15.1` 跑临时项目，成片正常产出、
    日志一切正常，**帧目录被清掉了 49 张**（第 50 张被宿主的安全删除守卫拦下才暴露）。
    症状极隐蔽：`✓ 场景 outro：453 帧` 的日志是真的，帧也确实渲过，只是结尾被删了。
    **规则：只要帧还要用于「拼接 / QC / 封面 / 复核」，一律加 `--keep-frames`。**
    另注：完整渲（不带 `--preview`）不触发这段清理，所以「全片重渲」反而比「局部重渲」安全。

33. **★（2026-09-21 新增工作流）改单场画面后「只补渲这一场」的标准做法 —— 临时项目法**：
    `render_video.mjs` 的 `order` 就是全部场景，改一帧就要全片重渲（一条实测片 3802 帧 ≈ 15 分钟）。
    **改的是末场时优先用 `--only <场景id>`（见第 45 条），比本法省事**；本法适用于
    **被改场景不在末位**、或需要精确控制全局帧号的情形。
    用法是用临时项目精确复现该场景的**全局帧号**，渲完贴回主序列：

    1. 建 `<项目>/render/_fix/`，拷进 `theme.css`、`assets/gsap.min.js`、
       `frames/<id>.html`、`frames/<id>.beats.js`（帧里的 `../theme.css` / `../assets/` 相对路径靠目录深度对齐）；
    2. 写 `project.json`（`order` 只放目标场景，其余字段照抄主项目，**`gap` 必须一致**）
       + `layout.json`（只放目标场景的 `start_sec/duration_sec`）；
    3. **帧号对齐靠两个数**：主序列里该场景的 `gf = round(start_sec × fps)`，
       场景帧数 `n = min(总帧数, round((start_sec+duration+gap)×fps)) − gf`。
       `n` 比 `round(duration×fps)` 大（末尾那段 gap 被并入前一场景），
       所以临时项目里要么加一个 **`duration_sec: 0` 的占位场景**凑出同样的 `totalFrames`，
       要么用 `--preview <n/fps>` 直接把帧数卡到 `n`；
    4. 渲完（**带 `--keep-frames`**）把 `f_000001..f_0000nn` 贴成主序列的 `f_<gf+1>..f_<gf+n>`；
    5. 用主项目的 `ffmpeg` 口径重合成（见下），再跑 `qc_check.py`。

    本片实测：hook 291 帧 + outro 453 帧≈ 90s+130s，相比全片重渲 924s 省掉约 12 分钟。
    **主序列的合成命令**（与 `render_video.mjs` 逐字一致）：
    `-framerate 30 -i f_%06d.png -i audio/narration-full.mp3 -c:v libx264 -preset medium -crf 18
     -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 160k -af apad -t <renderSec>`

    > **别用 `-shortest`。** 它按音轨长度收尾，而 layout 的 `video_duration_sec` 比音轨多出
    > 一段片尾留白（末块字幕的收尾余韵），`-shortest` 会把这段留白连同最后一块字幕一起切掉。
    > 正解是 `-af apad -t <renderSec>`：音轨不足处补静音，成片长度由 layout 唯一决定。

34. **★（2026-09-21）冷开场：短视频前 0.5 秒必须有主体，`opacity` 淡入是最慢的入场**：
    本片 hook 初版把三行巨型标题放在 `t1（1.154s，第一句解说词起播）`，配 `power3.out` 0.72s 淡入。
    抽帧一看 **0.1s / 0.5s / 1.0s 三帧几乎全黑**（只有角标 + 日期戳），1.4s 才有字 —— 信息流里这是硬伤。
    两个改法叠加即可：① 入场起点从「第一句解说词」提前到 **`t0 + 0/0.14/0.28`**（`t0` = 首字起播），
    别再等解说词；② 缓动换 **`power4.out` + 0.5s**（起手极快，0.15s 就走完七成），
    `opacity` 淡入退居次要 —— **遮罩上推（`overflow:hidden` + `y:104%→0`）本身就提供遮挡，
    不需要再叠一层从 0 开始的透明度**，叠了就会让首帧必然全黑。
    修后实测：0.10s 已能看到字头、0.35s 两行到位、0.70s 三行齐 —— 首帧体积也从 28KB 升到 37KB，
    `qc_check.py` 的抽帧体积列可以直接当「冷开场是否空屏」的回归指标用。
    附：`peek_frame.mjs` 的 `--at` 是**百分比**不是帧号（`--at 2,5,10` = 2%/5%/10% 轴长），
    查冷开场要传 `--at 1,3,6` 这种小的百分数。

35. **★（2026-09-21）入场动画有「截止时刻」，不是「起始时刻」——挂在最后一句上的收尾元素等于没出现**：
    介绍片的 outro 结尾有 3 个 chip（`MIT © 2026 Moh` / `v1.2.2` / `23 种风格`），
    挂在了最后一拍 `B('去试试吧') = 5.763s`，而该场景帧长 6.53s、成片实际收在 107.65s
    —— 留给它们的只有 **0.35s**（还要叠 0.07s×2 的 stagger）。抽帧看：整片结束前它们只露出半个头。
    病根是把「这句解说词在说什么」当成了动画时点，而**帧尾还有 `tail`（约 0.15s）+ 音轨与视频
    的 0.4s 差**，最后一拍的落点几乎贴着片尾。

    **规则：任何入场动画的最晚触发点应 ≥1.2s 早于 `speech_end`**；越靠后的元素越要挂到
    前一句（本片改挂 `B('仓库地址在简介里') + 0.45`，获得 1.45s 展示时间）。
    想在最后一句「再给一次响应」而不占用时间，就用**已经在场元素**的微动作（如 `.repo` 的
    `scale 1 → 1.03 → 1`），不要引入新元素。

    **★ 配套的验收方法（比 `qc_check` 的默认抽帧更狠）**：`qc_check.py` 只均匀抽 12 帧，
    本片最后一个样本落在 **92%** 处（99.55s / 107.65s）——片尾三秒根本没被看到。
    补一招：**按 `layout.json` 算出每个场景 `speech_end` 前 0.15s 的全局时刻，
    逐点抽帧拼成一张 contact sheet，一次过 11 个场景的「终态」**。本片 11 帧一次过，
    只有 outro 露出问题。命令形状（ffmpeg 走 `imageio_ffmpeg`）：

    ```bash
    FF=$(python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
    for t in 6.9 17.8 31.2 44.5 51.9 60.7 71.8 79.6 89.6 100.6 107.35; do
      "$FF" -y -loglevel error -ss $t -i out/<slug>.mp4 -frames:v 1 "render/end_check/e$t.png"
    done   # 再用 PIL 拼成一张 4 列 contact sheet 肉眼看
    ```

36. **（2026-09-21）多 agent 并行建帧前，先落一份 `frames/kit.css` 共享视觉基座**：
    本片 11 个场景、3 个并行 agent，**`lint_frames.py` 一次过、零违规、跨帧风格统一**，
    与前几片动辄返工形成对比。做法：把幕底（`.bg`/`.grid`）、章节角标（`.sec`）、
    卡片（`.card` / `.card--focus` / `.card--dim`）、文字层级（`.h1/.h2/.h3/.body/.tiny/.mono`）、
    配件（`.chip/.tag/.rule`）、禁区之上的信息条（`.foot`，`bottom:186px`）、
    媒体卡（`.shot`）一次写死，帧文件只引用 class。要点：

    - `kit.css` **不是**第四份契约文件，它和 `theme.css` 一样是共用层 —— 帧里
      `<link ../theme.css>` 之后紧跟 `<link kit.css>`；**`lint_frames.py` 只扫 `frames/*.html`，
      不扫 `kit.css`，所以共享层里更要自律**（本片 `kit.css` 同样只用 theme 变量）。
    - 派 agent 的 prompt 里把「底对齐用 `top` 定位、内容 `bottom ≥ 180px`、禁色值字面量、
      `B()` 取 `frames/<id>.beats.js` 原文」写成硬要求 + 违反即返工，比事后 lint 返工便宜得多。
    - agent 会自行补「居中章节标题」等版式细节 —— 只要风格统一就放行，别逐帧纠偏。

    **配额提醒**：本片一次全片重渲 3242 帧花了 780s；而上面第 33 条已经写好了
    「临时项目法按全局帧号补渲再贴回」的完整流程（约省 12 分钟）。
    **发现只有一两个场景要改时，先翻第 33 条，不要直接全片重渲。**

37. **（2026-09-22）帧内的「统一生长」辅助函数必须用 `querySelectorAll`。**
    常见写法 `function grow(sel, t){ var el = document.querySelector(sel + ' .bar'); ... }`
    传单个 id（`'#s1'`）没问题，但传**多匹配选择器**（如 `'.row:not([id])'`）时
    只会动到第一个元素 —— 其余柱子永远停在 `width:0`。
    **症状极具迷惑性**：零报错、零 lint 违规、帧也不静止，只是「有几根柱子丢了」。
    正解：`querySelectorAll(sel)` + 逐项 `offset`，`tl.fromTo()` 在循环内各自注册。
    → 凡是「一组元素一起动」的辅助函数，一律 `All` + `for`，不要图省事。

38. **绝对定位元素的 `top` 是相对**它自己的定位框**，不是相对页面。**
    compare 帧要把徽标放到「双卡下方」，直接写 `top:384px` → 实际落在
    `容器 top(196) + 384 = 580`，跑进了下一区块并压住柱状图。
    正确值 = `容器高度 + 留白`（本例 `176 + 6 = 182px`）。
    → 给绝对定位子元素写坐标前，**先确认它挂在哪个定位祖先上**；
      `peek_frame` 出图后拿实际像素反查一次最稳。

39. **数字卷轴（odometer）在 seek 渲染下的可靠写法。**
    第 9 条说「数字滚动用纯 transform 数字卷轴」，这里给出可直接抄的实现：

    ```html
    <span class="reel"><b class="rack"><i>0</i><i>1</i>…<i>9</i></b></span>
    ```
    ```css
    .reel { display:inline-block; height:1em; overflow:hidden; }
    .reel .rack { display:block; }
    .reel .rack i { display:block; height:1em; line-height:1em; font-style:normal; }
    ```
    ```js
    tl.fromTo(rack, { y:'0em' }, { y:'-3em', duration:1.5, ease:'power2.out' }, t);
    ```
    要点：① 每位数字一个 `.reel`，`y` 走到 `-N em` 即显示数字 N；
    ② **完全不用 `onUpdate` 回调**，因此不受 `tl.pause(t, true)` 抑制影响（对比第 27 条）；
    ③ 外层数字用 `display:flex; align-items:flex-start` 保证多位等齐，
       货币符号等窄字用 `align-self:center` + 小字号，别混进 rack。
    本片 liverl 的 30 / 347 / 75 三个数都靠它，终态逐位正确。

40. **暗底上的光晕别写 `rgba()` 字面量。**
    `box-shadow: 0 0 40px rgba(214,137,81,.45)` 会被 `lint_frames.py` 按契约 3 拦下。
    直接 `box-shadow: 0 0 40px var(--signal)` / `var(--accent-glow)` 即可 ——
    theme 变量本身就是带 alpha 的色，效果一样且换肤自动跟随。

41. **`peek_frame --at` 是百分比，判「元素缺失」前先换算成秒。**
    `--at 92` ≈ `时长 × 0.92`。本片 models 的 `20×`、perf 的底部结论条、
    compare 的 `1/20 ~ 1/60` 都在 peek 时点之后才入场 ——
    看到「应该有的东西没有」时，先 `时长 × 百分比` 算一下时点，再决定要不要改版。
    想复核终态直接给 `--at 99`。

42. **亮底「编辑插页」是最好用的节奏工具。**
    全片 10 场景里只把 2 个纯数据场景（排名柱图、差距图）做成亮底
    （`--paper` + `--ink` + `--accent-on-paper`），其余全暗底 ——
    比「全亮」或「全暗」都更抓人，且换肤只动 `theme.css` 一处。
    注意：亮底帧**必须自己铺 `--paper` 背景**，否则会露出暗色幕底。

43. **★ 「A 或者不 A」不是选择，是同义反复 —— 结尾最常见的废句。**
    真实案例：结尾三行写成 `结婚或者不结婚` / `买房或者不买房` / `留在城市，或者回到县城`，
    观众读完的反馈是「说了跟没说一样」。**因为它的信息量严格为零**：
    每条都穷尽了全部可能性，等于什么都没说，只是把句法凑得像选项。
    同类废句还有两种，一起拉黑：

    | 废句类型 | 例子 | 为什么废 |
    |---|---|---|
    | 同义反复 | `结婚或者不结婚` | 穷尽全部可能 = 零信息 |
    | 自指复读 | `这就是一个普通人的一生` | 把标题当结论念了一遍 |
    | 鸡汤留白 | `没有人知道你会走到哪里，包括你自己` | 听起来像总结，其实没有指向任何事 |

    **正确写法：不总结、不升华、不判断，只把「还没有结果的具体的事」按它本来的样子列出来。**
    落点必须是**可核查的具体物**（一条没回的消息 / 一栏空着的三方协议 / 下周的复查），
    而不是处境的名字。判据一句话：**把这句话里的名词换成任何其他片子也成立，就是废句。**
    结构上让它成立的做法是**前面埋钩子、结尾不回收**——
    全片早段写过「还有一个，在等消息」，结尾不是给答案，而是让这条消息**仍然悬着**。

    配套的画面写法（比文字更省事）：把结尾做成一页**勾选框全空的待办清单**
    （`☐ 那条消息 ⋯⋯ 未回`），每行随念到它的那一句落下，一条都不打勾。
    「未完成」不用靠形容词，靠空框本身。

44. **极简帧里同一信息只准出现一次。**
    上一条的同一个镜头里，全片固定的左下角日期戳是 `2026 · 你 21 岁`，
    右栏又放了一个 `.min-age` 写着同一句 —— peek 出图才发现画面上有两处一模一样的字。
    极简帧元素少，重复格外显眼。定稿前**通读一遍画面上所有文字**（含全局固定元素：
    左上系列标、左下日期、右下场次），逐个确认没有同义重复。同类：右上小标题与场次标记撞词。

45. **`--only <场景id>` 局部重渲的前提，和它的必然后续。**
    改一句旁白不必重渲整片（本片 14 场 6194 帧，全渲 20 分钟，重渲末场 78 秒）：

    ```bash
    node scripts/render_video.mjs . --only <场景id>     # 只重渲这一场
    node scripts/render_video.mjs . --mux-only          # 用现有帧重新合成
    ```

    两个前提，缺一个就会出错：
    ① **只有末场安全**。脚本会提示被改场景是否为末场；非末场一旦时长变化，
       其后所有场景的帧号整体前移，必须整片重渲。
    ② **变短之后必须清掉尾部过期帧**，否则 ffmpeg 会把旧帧一起编进去，成片比 layout 长。
       先算出新总帧数（`round((Σduration + gap×(n-1)) × fps)`）再删：

    ```python
    for f in (FRAMES := pathlib.Path('render/frames')).iterdir():
        if f.name.startswith('f_') and int(f.name[2:8]) > TOTAL: f.unlink()
    ```

    验收口径（别只看渲染日志的「✓ 成片」）：**帧号连续无缺口 + 成片时长 == layout 总长**。
    本片收尾实测 6194 帧、0 缺帧、`Duration 00:03:26.47` 与 layout 的 206.47s 逐位一致。

