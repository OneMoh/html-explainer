# 几何体检的证伪样本（geometry-fixture）

**用途**：验证 `scripts/check_layout.mjs` 真的能抓到错 —— 不是「跑通了」，是「抓得准」。

一个检查类工具拿合格项目跑出「0 ERROR」是**待证实**，不是**通过**：
第一版 `check_layout.mjs` 就在真实项目上报 0 ERROR，其实重叠检查因为传错参数
（`inter(a, b)` 而不是 `inter(a.r, b.r)`，`a.rr` 恒为 `undefined`）**从来没运行过**
（见 `references/lessons.md` #76）。

## 怎么用

```bash
node ../scripts/check_layout.mjs .       # 站在本目录，或在技能根传路径
```

**期望输出：ERROR 2 · WARN 0 · INFO 1**，逐条对应 issue #1 里用户报的三类症状：

| 期望条目 | 对应症状 |
|---|---|
| `侵入字幕禁区` — `.intrude` 底边 y=1040，侵入 130px | 内容压进字幕带 |
| `文字被遮挡` — `.axis`「700nm · 红光450nm · 蓝光」被 `.evidence` 盖住 | issue #1 的「遮挡」 |
| `疑似未对齐` — `.dot` 中心距 SVG 内容中心 63px | issue #1 的「元素错位」 |

数字（130px / 63px）是刻意留的余量，不是精确到像素的断言 —— 校验时看**级别和条目**
是否齐，别把具体像素当回归基线。

## 改动这个样本时注意

`frames/broken.html` 里的三处「坏」是**故意**的，不是待修的 bug：

- `.chart` 容器高度只算柱区、`.axis` 溢出到容器外 → 被 `.evidence` 压住；
- `.intrude` 钉在 `bottom:40px`；
- `.dot` 是 HTML 绝对定位、与 SVG 内画的射线**不共坐标系**。

把任一处「修好」都会让对应条目消失 —— 那正是这个文件存在的意义。
