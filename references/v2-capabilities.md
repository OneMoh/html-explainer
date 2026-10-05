# v2.0 新增能力对照表与验收清单

> 本文档回答三个问题：**新增了什么、怎么用、怎么验收。**
> 所有能力都是可选开关 —— 不带任何新参数跑，行为与 v1.4.3 一致。

---

## 1. 新增能力对照表

| # | 能力 | 实现文件 | 入口 / 命令 | 详细文档 |
|---|---|---|---|---|
| 1 | **动效库**（40+ 动作词汇，5 组） | `assets/motion.js` | `window.HXM`（浏览器）/ `require`（Node） | `references/motion-library.md` |
| 2 | **主题驱动风格编排** | `scripts/style_director.py` | `--mood / --pace / --audience / --pin / --seed` | `references/style-director.md` |
| 3 | **多风格混用 + 局部替换** | `scripts/style_director.py` | 自动（`accent` 字段） | `references/style-director.md` §5 |
| 4 | **动态开头 + 动态转场** | `scripts/style_director.py` | 自动（`opener_variant` / `transition_out`） | `references/style-director.md` §6 |
| 5 | **画质 × 帧率档位** | `scripts/render_video.mjs` | `--profile` / `--quality` / `--fps` | `references/render-profiles.md` |
| 6 | **快门运动模糊**（线性光积分） | `scripts/render_video.mjs` + `scripts/blur_integrate.py` | `--shutter 180` | `references/render-profiles.md` |
| 7 | **多浏览器进程级并行** | `scripts/render_video.mjs` | `--workers N` | `references/render-profiles.md` |
| 8 | **断点续渲 + 定期重启浏览器** | `scripts/render_video.mjs` | `--resume` / `--recycle N` | `references/render-profiles.md` |
| 9 | **PNG 提速 / JPEG 中间帧** | `scripts/render_video.mjs` | `--png-fast` / `--jpeg --jpeg-quality N` | `references/render-profiles.md` |
| 10 | **渲染基准工装** | `scripts/bench_render.py` | `--configs legacy,draft,balanced,shutter,4k30,4k60,master` | `references/render-profiles.md` |
| 11 | **★ 渲染通道确认**（渲染前必问用户：`jpeg q95`（★推荐）/ `png-fast` / `png` / `jpeg q82`） | `consent.json` 的 `render_channel` + `scripts/gate_check.py` | `gate_check.py --phase render` | `SKILL.md` 确认点 5 · `references/render-profiles.md` §0 |
| 12 | **★ 快门样本磁盘护栏**（`--shutter-flush <GB>`：攒够阈值就全体停手积分+清理，把峰值从"全片之和"压到"阈值×1"） | `scripts/render_video.mjs` + `scripts/blur_integrate.py` | `--shutter-flush N`（0=关；默认取可用磁盘 25%，夹 1–8 GB） | `references/render-profiles.md` §6 |
| 13 | **★ 快门只开在该开的地方**（场景级白名单 + 帧级位移闸门，不把 8× 成本花在静态帧上） | `scripts/render_video.mjs` | `--shutter-only <id,id>` / `--motion-hold <px>` | `SKILL.md`「只在需要的那几场开」· `references/render-profiles.md` §3 |

---

## 2. 逐项验收清单

### 2.1 动效（能力 1）

- [ ] `node tests/test_motion.mjs` → **断言全绿**
- [ ] 库里 5 组动作均可用：`enter` / `carry` / `contact` / `camera` / `ambience`
- [ ] `HXM.ease` 曲线端点严格 0→1；`ease.back` 是工厂函数（`back(2.2)(u)`）
- [ ] `seededRng` 可重复（同 seed 同序列）
- [ ] `spring` 收敛到 1、`settle` 返回有限秒数
- [ ] 坐标互转 `toScreen(toWorld(p)) ≈ p`

### 2.2 模板编排（能力 2–4）

- [ ] `python tests/test_style_director.py` → **断言全绿**
- [ ] `--dry-run` 只打印不写盘；不带 `--dry-run` 产出 `style-plan.json`（落在**项目根目录**）
- [ ] 每场有 `role` / `primary` / `motion_intensity` / `transition_out` / `why`
- [ ] **专用角色受保护**：`data` / `mechanism` / `evidence` 不被跨类别替换
- [ ] 多样性约束生效：风格数 ≤ `max_styles`、连续同风格 ≤ 2、开场 ≠ 第二场
- [ ] `--pin id=style` 是硬约束（永不被改）
- [ ] `--seed` 改变画面选择；`--band 0` 结果完全确定
- [ ] `--mood high` 提升 `motion_intensity`，`--mood calm` 压低
- [ ] `opener_variant` 随主题哈希变化（不是写死的）

### 2.3 画质 / 帧率（能力 5、9）

- [ ] `node scripts/render_video.mjs . --list-profiles` 列出 5 个档位
- [ ] `--quality 1080p|2k|4k` 全部可跑；输出分辨率 = 项目尺寸 × scale
- [ ] 画质只改 `deviceScaleFactor`：**布局逐像素不变**，只是采样更密
- [ ] `--fps 30|60` 自由组合
- [ ] `--profile legacy` **逐位复现 v1.4.x 旧成片**（向后兼容硬证据）

### 2.4 运动模糊与提速（能力 6–8）

- [ ] `--shutter 0` 时无运动模糊（与旧行为一致）
- [ ] `--shutter 180` 时动帧做多样本积分；`hold` 帧直接沿用单张，不落样本、不进积分
- [ ] **三级闸门都对**：① `--shutter-only a,b` 时非名单场景的帧**不产生** `render/shutter/` 目录；
      ② 帧导出 `__motion` 时，位移 < `--motion-hold` 的帧走单张（日志「位移闸门」计数 > 0）；
      ③ 无 `__motion` 时逐字节兜底（日志「快门覆盖面」显示 100%，并以此为 ② 未生效的告警）
- [ ] `--shutter-only` 里写错 id **必须报错退出**（否则等于静默全片不开快门）
- [ ] 页面定义 `window.__motion(t0,t1)` 时样本数自适应（`--motion-gap`）
- [ ] `blur_integrate.py` 在**线性光**下平均（非 sRGB 直接平均）
- [ ] `--workers N` 真的起 N 个独立浏览器进程（日志打印"N 个**独立浏览器**"）
- [ ] `--resume` 跳过已积分的帧
- [ ] `--recycle N` 每 N 帧重启浏览器

### 2.5 基准（能力 10）

- [ ] `python scripts/bench_render.py --out .scratch/bench --scenes 3 --sec 1.2 --preview 3.6 --configs legacy,draft,balanced` 正常产出对比表
- [ ] 表格给出每档 `fps / 帧数 / 截图s / 积分s / 总s / 帧每秒 / 加速比 / 体积`

### 2.6 渲染通道确认（能力 11）

- [ ] 渲染前**先问用户**选通道（`jpeg q95`（★推荐）/ `png-fast` / `png` / `jpeg q82`），
      并给出**描述 + 逐帧耗时 + 相对速度 + 相对体积 + 推荐口径**
- [ ] 选择落到 `consent.json` 的 `render_channel`，且 `decided_by == "user"`
- [ ] `python scripts/gate_check.py --project . --phase render` 在未拍板时**退出码 1**，拍板后通过
- [ ] 打样阶段选定后可沿用同一轮；**换通道 / 换档位要重新确认**
- [ ] `consent.json` 由 `--init` 生成时 `render_channel.choice` 为**空字符串**（脚本不替用户选）

### 2.7 向后兼容（不破坏原有能力）

- [ ] 23 个模板风格目录**未被改动**（`python scripts/check_integrity.py` 通过）
- [ ] 原有流水线（tts → timeline → subs → lint → 渲染 → QC → 封面）**全部照旧可用**
- [ ] 封面 16:9 / 3:4 / 9:16 流程未动
- [ ] `--profile legacy` 复现旧成片
- [ ] 版本号一致：`check_integrity.py` 报 `版本一致：2.0.0`

**一键跑全部自测：**

```bash
node tests/test_motion.mjs
node tests/test_beats_norm.mjs
python tests/test_style_director.py
python tests/test_subs_text.py
python scripts/check_integrity.py
```

---

## 3. 端到端示例

一个最小但完整的 v2.0 演示（7 场「创新药」题材，含编排 → 渲染）：

```bash
PY=<venv python 绝对路径>
SKILL=<skill 根目录>

# 0) 建项目（把 narration.json 填好：一句话一行，| 分隔句）
"$PY" $SKILL/scripts/new_project.py .scratch/demo demo --topic "创新药"

# 1) 配音 → 时间轴 → 字幕
"$PY" $SKILL/scripts/tts_build.py      --project .scratch/demo --provider edge
"$PY" $SKILL/scripts/timeline_build.py --project .scratch/demo
"$PY" $SKILL/scripts/subs.py           --project .scratch/demo

# 2) ★ 风格编排：读解说词挑风格（先 --dry-run 看结果，满意再去掉）
"$PY" $SKILL/scripts/style_director.py --project .scratch/demo --dry-run
"$PY" $SKILL/scripts/style_director.py --project .scratch/demo

# 3) （按 style-plan.json 写 frames/*.html，见 references/style-director.md）

# 4) ★ 渲染通道闸门：render_channel 必须已由用户拍板（SKILL.md 确认点 5）
"$PY" $SKILL/scripts/gate_check.py --project .scratch/demo --phase render

# 5) ★ 渲染：可选档位 + 通道。先 draft 看节奏，定稿用 balanced / final
node $SKILL/scripts/render_video.mjs .scratch/demo --profile draft --preview 10
node $SKILL/scripts/render_video.mjs .scratch/demo --profile balanced \
     --jpeg --jpeg-quality 95 --audio audio/narration-full.mp3
# 只有几场要拖影？用白名单，其余场零成本；帧里导出 __motion 时再靠 --motion-hold 自动摘静态帧
node $SKILL/scripts/render_video.mjs .scratch/demo --shutter-only hook,cta --motion-hold 1 \
     --jpeg --jpeg-quality 95 --audio audio/narration-full.mp3

# 6) 出 4K60 终稿（硬件要求见 references/render-profiles.md）
node $SKILL/scripts/render_video.mjs .scratch/demo --profile final \
     --audio audio/narration-full.mp3 --workers 8 --resume
```

**演示要展示的四件事**：

| 要展示的 | 看哪里 |
|---|---|
| 动效 | 场景 HTML 里 `HXM.riseWord / landHit / camTrack` 的组合；帧间无跳变（快门开着） |
| 模板混用 | `style-plan.json` 里每场的 `primary` + `accent`（局部替换） |
| 主题化艺术设计 | 每场 `why` 字段的解释；`opener_variant` 随 `--seed` 变化 |
| 4K60 选项 | `--list-profiles` 与 `references/render-profiles.md` 的档位表与基准 |

---

## 4. 与 v1.4.3 的兼容承诺

| 承诺 | 保证方式 |
|---|---|
| 旧命令行照旧可用 | 所有新参数都是可选的；缺省走 `balanced`，行为等价于旧默认（1080p30） |
| 旧成片逐位复现 | `--profile legacy` = 1.4.x 行为（单浏览器 + 场景级并发 + 精细 PNG） |
| 23 个模板未动 | `references/style-catalog.*` 未修改，`check_integrity.py` 校验 |
| 封面流程未动 | `cover_build.mjs` / `check_cover.mjs` 未修改 |
| 不新增运行时组件 | v2.0 未引入任何新的 Python 运行时依赖（`numpy` 等随 v1.x 已有） |
| 确定性不变 | 动效库消除 `Math.random()`，走 `seededRng`，同输入同输出 |
