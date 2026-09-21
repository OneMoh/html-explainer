# 参与贡献

感谢你愿意花时间。本文只说实际的东西：怎么把环境跑起来、项目的硬性规则有哪些、
以及不同类型的贡献该往哪儿放。

## 可以贡献什么

| 贡献类型 | 该往哪儿放 |
|---|---|
| 报告 Bug | 用 bug 模板[开一个 issue](https://github.com/OneMoh/html-explainer/issues/new/choose) |
| 你已定位的渲染 / 同步问题 | 在 `references/lessons.md` 追加一条编号记录，**并且**修代码 |
| 新的画面风格，或更好的改编配方 | 更新 `references/style-catalog.md`，并附一个可运行的示例 |
| 文档修正 | 直接提 PR —— 改错别字不需要先讨论 |
| 新功能 | 先开 issue 把方案谈拢，再动手写 |
| 平台相关修复（macOS / Linux 路径、其它 shell） | 非常欢迎 —— 本项目在 Windows + Git Bash 上开发 |

## 开发环境

```bash
git clone https://github.com/OneMoh/html-explainer.git
cd html-explainer

# 先自检，再装缺的东西
bash setup_env.sh            # 只报告
bash setup_env.sh --install  # 安装缺失依赖

# 确认工具链正常
node -v && python -V
```

要求：Python ≥ 3.9、Node ≥ 18，以及 Chrome 或 Edge（两者几乎总是已经装好）。
`ffmpeg` 优先从 `PATH` 取，取不到则回退到 `imageio-ffmpeg` 自带的静态二进制。

### 跑一次端到端自检

```bash
python scripts/new_project.py demo --topic "人工智能"
cd demo
# 填 narration.json、写 frames/*.html、设置 project.json 的 order
python ../scripts/tts_build.py      --project .
python ../scripts/timeline_build.py --project .
python ../scripts/subs.py           --project .
python ../scripts/lint_frames.py    --project .
node   ../scripts/render_video.mjs  . --preview 30
```

如果这些全部跑完、`out/preview.mp4` 播放时音画同步，你的环境就没问题。

## 项目的硬性规则

这些不是风格偏好。违反它们会产生**静默失败** —— 视频能渲出来，但是错的。凡是能自动检查的，
都由 `scripts/lint_frames.py` 强制。

1. **任何画面帧里都不许引外部字体或 CDN 资源。** 网络字体在很多网络下不可达，而且超时是
   静默的。只用系统字体栈，GSAP 一律从随包的 `../assets/gsap.min.js` 引用。
2. **颜色只能取 `theme.css` 的 CSS 变量。** 画面代码里不许出现十六进制字面量 —— 这正是
   「换主题只改一个文件」得以成立的原因。
3. **不许有墙钟逻辑。** `setInterval` 与 `requestAnimationFrame` 计数在确定性 seek 下不可能
   工作。动画用 GSAP 或 CSS `@keyframes`。
4. **动画用 GSAP 时间轴，并注册到 `window.__tl`。** 渲染器每帧 seek 这个时间轴；没有它，
   什么都不动。
5. **动画定位用 `B('块文本')`，绝不用写死的时间。** 兜底写法 `B('x') || 3.2` 是被禁止的 ——
   块查不到就应该在构建时大声失败，而不是静默复用一具过期的数字。
6. **保持字幕禁区干净。** 底部 80–170px 不许有任何内容渲染，入场路径也不许穿过它。
7. **项目目录与输出文件一律用 ASCII 路径。** 非 ASCII 路径会让 Windows 上的 ffmpeg 出错。
   项目名与输出名保持 ASCII，要展示用的名字以后再改。

完整契约（每条规则背后的理由，以及会被打回的反例）见
[`references/frame-contract.md`](references/frame-contract.md)。

## 追加一条踩坑记录

`references/lessons.md` 是这个仓库里最值钱的文件。它之所以存在，是因为这条流水线的失败方式
是**静默**的 —— 出问题不会报错，只会产出一条看着挺像样的视频。

一条好的记录按这个顺序写：

1. **症状**，就按你最初观察到的样子 —— 包括它是怎么把你带偏的。
2. **定位过程**，以及证明病因的证据（探针、diff、测量值）。
3. **修法**，以及修完该检查什么来确认。
4. **由此得出的通用规则**（如果确实能推出的话）。

编号顺次追加。**不要给已有条目重新编号** —— 代码注释里在引用这些编号。

## 追加一种画面风格

1. 在 `references/style-catalog.md` 与 `references/style-catalog.json` 里记录规范
   （画布、字阶、时间轴结构、配色纪律）。
2. 分类为 `rich`（单文件，CSS `@keyframes` 时间轴 —— seek 渲染器零改动可驱动）或 `gsap`
   （多 composition —— 必须重写表达，不能照搬）。
3. 如果这种风格需要超出标准三步（换字体栈、把底部元素抬出字幕带、填真实内容）之外的
   处理，在 `references/template-guide.md` 里补一条改编配方。
4. 验证它能渲出来：`node scripts/peek_frame.mjs <project> <id> --at 25,50,85`。

风格标识符用 `kebab-case`，并沿用已有的命名模式（`frame-*`、`vfx-*`）。

## PR 检查清单

提 PR 之前请确认：

- [ ] `python scripts/lint_frames.py --project <project>` 对你动过的每一帧都没有 FAIL
- [ ] 你真的渲染过你的改动。画面代码「看着对」经常是不对的 —— seek 渲染有自己的失败模式
- [ ] 新增的踩坑记录已带编号写进 `references/lessons.md`
- [ ] 没有引入外部字体、CDN 引用或硬编码颜色
- [ ] 如果有再分发或再衍生的第三方内容，`THIRD_PARTY_NOTICES.md` 已更新
- [ ] 涉及使用者可见行为的改动，`README.md` 与 `README.en.md` 已同步更新

## 提交信息

建议使用 Conventional Commits（`fix:`、`feat:`、`docs:`、`chore:`）。如果这次改动修的是一个
静默失败，请写正文说明它原来错在哪、你是怎么验证修好了的。

## 范围说明

本项目刻意**不**打算成为一个框架。它是一条流水线，接口很小、很无聊：HTML 帧进，MP4 出，
音画同步稳得住。会增加构建系统、插件 API，或对云服务产生运行时依赖的功能，一般都在范围之外
—— 如果你认为有重要的例外，开个 issue 聊聊。

## 许可

提交贡献即表示你同意你的贡献以 MIT 许可授权（见 [LICENSE](LICENSE)），并确认你有权提交它们。
如果你从别的项目移植了内容，请在同一个 PR 里把它写进 `THIRD_PARTY_NOTICES.md`。
