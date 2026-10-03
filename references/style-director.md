# 模板编排 —— `scripts/style_director.py`（v2.0 新增）

> 一句话：**读解说词本身，推断每一场在片子里扮演什么角色，再挑风格 —— 让主题支配模板，而不是反过来。**

---

## 1. 它解决什么问题

旧用法是「挑一个模板风格 → 整片都用它」。结果是：

- 每期视频长得一样、开头永远一样；
- 23 个风格里只用 1 个，等于浪费了 22 个；
- 讲数据的场和讲原理的场用同一套画面语法（本该不同）。

本编排器不做「模板套用」，做**编排**：给每场挑主风格 + 按需搭次风格 + 决定开场变体、
场间转场、动效强度。

---

## 2. 输入与输出

**输入**：`narration.json`（`[{id, text}]`，`|` 分隔句）+ `project.json`（`order`）。可选 `brief`。

**输出**：`style-plan.json`（写在项目根目录，与 `layout.json` / `subs.json` 同级）

```jsonc
{
  "version": "2.0",
  "generator": "style_director.py",
  "seed": "demo|",
  "brief": { "topic": null, "mood": "auto", "pace": "auto", "audience": "general", "aspect": "16:9" },
  "global": {
    "distinct_styles": 6, "max_styles": 4,
    "styles": ["frame-data-chart-nyt", "frame-swiss-grid", "..."],
    "opener_variant": "kinetic-cascade",
    "diversity_notes": ["..."],
    "theme_hint": { "accent_suggest": ["#7C5CFF", "#F5F5F7"], "note": "..." }
  },
  "scenes": [
    {
      "id": "intro", "role": "opener", "role_zh": "开场钩子",
      "duration_sec": 11.22, "pace": "medium", "motion_intensity": 0.67,
      "primary": "frame-liquid-bg-hero", "primary_name": "Liquid Background Hero",
      "accent": null, "accent_use": null,
      "transition_out": "cut", "engine": "hyperframes",
      "colors": "#1e1b4b #fafaf8 #a78bfa #7c5cff #ec4899",
      "why": ["类别 marketing 命中角色「开场钩子」首选", "..."],
      "text_head": "一款药，从实验室到患者手里，平均要烧掉 26 亿美元。这"
    }
  ],
  "_motion": { "intro": 0.67, "scale": 0.53, "..." }
}
```

`why` 字段是**可解释的**：每个决定都写清为什么。出片前你能一眼看出"这场为什么被挑中"。

---

## 3. 八种角色（按位置 + 文本线索判定）

位置是硬约束（第一场必是开场、最后一场必是结尾），文本线索决定中间各场：

| 角色 | 中文 | 倾向的画面语法 | 触发线索（节选） |
|---|---|---|---|
| `opener` | 开场钩子 | hero / 标题卡 / 电影感 | 第一场（硬约束） |
| `statement` | 陈述 | 陈述标题 / 社论 / 大图 | 默认兜底 |
| `data` | 数据 | 柱状图 / 统计卡 / 社论 | `%`、倍、亿、增长、占比、统计… |
| `mechanism` | 原理解释 | 流程图 / 概念图 | 因为、所以、原理、机制、如何、本质… |
| `evidence` | 例证 | 柱状图 / 社论 | 例如、比如、案例、典型、实测… |
| `contrast` | 转折/反差 | 标题卡 / 粗体条 | 但是、然而、并非、相反、表面/实际… |
| `conclusion` | 收束 | 标题卡 / 引用卡 | 总之、综上、结论、核心是、回到… |
| `outro` | 结尾落版 | outro / 落版 | 关注、下期、评论区、谢谢观看… |

**专用角色受保护**：`data` / `mechanism` / `evidence` 语义强绑定某个风格类别，
**多样性约束不许动它们** —— 讲数据的场被换成"标题卡"就是把意思讲歪了。

---

## 4. 打分维度（`score_style`）

| 维度 | 作用 |
|---|---|
| 类别契合 | `ROLE_CATEGORY_FIT`：首选类别 +14，次选 +6，回避类别 −10 |
| **子类别契合** | `SUB_FIT`：比类别细一层（`presentation` 下有 11 个子类，讲数据用 `hero` 是错的，用 `stat-card` 才对） |
| 时长适配 | 风格目录的 `dmin/dmax`；落在区间内加分，超出扣分 |
| 内容词重叠 | 解说词与风格适用面的关键词重叠 |
| 受众加成 | `AUDIENCE_BOOST`：`pro` 偏 presentation/data-viz，`youth` 偏 social-shorts/marketing |
| 节奏 | 快节奏偏好 kinetic/glitch/social，慢节奏偏好 ambient/minimal |
| 改编成本 | 单文件 + CSS keyframes > 多 composition |

---

## 5. 混用与局部替换（accent）

主风格之外，按需给某些场搭一个**次风格**，做**局部替换**（不是整场换皮）：

> 例：主风格是瑞士网格，但中间那格大数字借 Pentagram Stat 的排版 DNA。

- 只在需要的场给（含数字/需要强调的场），且主风格不是 `data-viz`；
- 次风格须与主风格**不同类别**（同类不算混用）；
- **按能量取前 1/4 场**作为预算 —— 不是每场都混，避免花。

`accent_use` 字段说明这个次风格用在哪个局部。

---

## 6. 多样性约束（全部可解释）

| 约束 | 说明 |
|---|---|
| C1 全片风格数 ≤ `max_styles` | 默认按片长 3~4 种 |
| C2 同一风格连续 ≤ 2 场 | 第 3 场必须换 |
| C3 开场风格 ≠ 第二场风格 | 防止开头雷同 |
| C4 `--pin` 是硬约束 | 用户拍板的永不被改 |

合并风格时**只允许同类别内合并**（跨类别会把意思讲歪），且**合并代价 > 10 分就放弃合并**
—— 为一个风格数指标牺牲画面契合度不值。此时会如实记录：

```
"多样性：目标 ≤4 种，实得 6 种 —— 再做合并要么跨类别（讲歪）、要么代价 >10 分（不值），因此保留"
```

**防雷同**：容差带（`--band`）内的候选按**主题哈希**轮换 —— 同一题材每次跑会换一批画面，
而不是永远选同一个。`--band 0` 则永远取最高分（完全确定，适合回归测试）。

---

## 7. 命令行

```bash
# 默认：从解说词推断一切
python scripts/style_director.py --project .

# 只预览不写盘
python scripts/style_director.py --project . --dry-run

# 覆盖情绪 / 节奏 / 受众
python scripts/style_director.py --project . --mood high --pace fast --audience pro

# 钉死某场风格（用户拍板）
python scripts/style_director.py --project . --pin intro=frame-swiss-grid

# 收窄候选池
python scripts/style_director.py --project . --allow frame-swiss-grid --allow frame-data-chart-nyt

# 控制风格总数与轮换带
python scripts/style_director.py --project . --styles 3 --band 5

# 换主题（改变画面选择）
python scripts/style_director.py --project . --seed "另一期|医疗器械"
```

| 参数 | 说明 |
|---|---|
| `--styles auto\|N` | 全片最多用几种风格（默认 auto = 按片长 3~4） |
| `--band` | 容差带（分），带内按主题哈希轮换，默认 5.0 |
| `--pin id=style` | 钉死某场风格（可重复） |
| `--allow id` | 把候选池收窄到这些风格 id（可重复） |
| `--mood calm\|neutral\|high` | 覆盖情绪 |
| `--pace slow\|medium\|fast` | 覆盖节奏 |
| `--audience general\|pro\|youth` | 覆盖受众 |
| `--seed` | 换主题字符串（改变容差带内轮换） |
| `--dry-run` | 只打印不写盘 |

---

## 8. 与其他模块的契约

```
narration.json ─┐
project.json  ──┴─→ style_director.py ─→ style-plan.json ─┬─→ 画面构建（选 primary + accent，套用风格）
                                                           ├─→ 作者（读 motion_intensity，校准画面动势）
                                                           └─→ render_video.mjs（读 opener_variant / transition）
```

`style-plan.json` 写在**项目根目录**（与 `layout.json` / `subs.json` 同级），
下游模块按此路径读取。

---

## 9. 自测

```bash
python tests/test_style_director.py     # 60 条断言
```

覆盖：角色推断（位置硬约束 + 关键词）、专用角色跨类别保护、时长区间、多样性约束
（C1~C4）、`--pin` 硬约束、band=0 确定性、混用预算、产物字段完整性。
