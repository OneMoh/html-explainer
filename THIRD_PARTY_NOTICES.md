# 第三方声明

`html-explainer` 以 MIT 许可发布（见 [LICENSE](LICENSE)）。该许可覆盖本项目原创的
**代码与文档**。

它**不**覆盖下面列出的第三方组件与衍生内容 —— 那些仍适用其各自的条款，按要求在此复现。

> **如果你要再分发本项目（fork、打包 zip、发布为包、镜像，或放进某个产品里），必须把本文件
> 一起带上。**

---

## 1. 随仓库打包的组件

### GSAP 3.13.0 — `assets/gsap.min.js`

- **版权**：© 2025 GreenSock. All rights reserved. 作者 Jack Doyle。
- **许可**：GreenSock standard "no charge" 许可 —— <https://gsap.com/standard-license>
- **状态**：为离线渲染逐字内置，未做修改。
- **说明**：这**不是**一个 OSI 许可。GSAP 在其标准许可条款下可免费使用（含商业用途）。
  `assets/gsap.min.js` 里的版权头不得移除。上游 README 一并保留在 `assets/gsap-README.md`。

---

## 2. 运行时依赖（安装，而非随包内置）

这些在依赖清单中声明，由 `bash setup_env.sh --install` 拉取，**不**提交进本仓库。

| 组件 | 版本（已测） | 许可 | 上游 |
|---|---|---|---|
| `edge-tts` | 7.2.8（钉死） | LGPL-3.0 | <https://github.com/rany2/edge-tts> |
| `playwright-core` | 1.63.0 | Apache-2.0 | <https://github.com/microsoft/playwright> |
| `numpy` | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | <https://numpy.org> |
| `pillow` | 12.3.0 | MIT-CMU | <https://python-pillow.org> |
| `imageio-ffmpeg` | 0.6.0 | BSD-2-Clause | <https://github.com/imageio/imageio-ffmpeg> |
| `ffmpeg`（二进制） | 来自 `imageio-ffmpeg` | LGPL-2.1+ / GPL-2.0+（随构建而异） | <https://ffmpeg.org/legal.html> |

**关于 `edge-tts`（LGPL-3.0）与 `ffmpeg`**：本项目以**独立进程调用 / 作为未修改的库导入**
的方式使用它们，不做静态链接，也不分发修改过的副本。如果你打算再分发一个**打包的** ffmpeg
二进制构建，请先看 FFmpeg 自己的许可页面 —— 编译选项决定该二进制属于 LGPL 还是 GPL。

`edge-tts` 是**刻意**钉在 `7.2.8` 的：7.x 系列在其语音边界 API 上有过破坏性变更，而本项目
依赖 `WordBoundary` 事件。

---

## 3. 衍生内容 —— 风格目录

`references/style-catalog.md` 与 `references/style-catalog.json` 是**对第三方模板设计规范的
转写** —— 画布尺寸、字体排印、时间轴结构、配色纪律 —— 覆盖 23 种具名风格。其中**不包含**任何
上游的模板源码、标记或素材。记录的只有事实性的设计参数与风格名称，目的是让人能从零写出一个
兼容的画面帧。

该目录由 `scripts/import_styles.py` 产出：它读取一份**已安装的** html-video，把规范转写成纯
文本。**它是一个移植期的一次性工具。** 跑一条 html-explainer 视频从不读取 html-video，
任何环节都不会执行或链接 html-video 的代码。

### 3.1 `nexu-io/html-video` —— 23 个模板

- **版权**：html-video 的作者（Open Design / nexu-io）
- **许可**：Apache-2.0
- **来源**：<https://github.com/nexu-io/html-video>
- **衍生了什么**：全部 23 个模板的设计规范与风格标识符（`frame-bold-poster` …
  `vfx-text-cursor`），转写进 `references/style-catalog.*`。
- **做了哪些改动**：规范重排为扁平的 Markdown / JSON 目录；每个模板分类为 `rich`
  （单文件 CSS `@keyframes`）或 `gsap`（多 composition）；补充了改编成本与字幕禁区约束的
  标注。原始模板代码、composition 与素材**没有**被复制。
- Apache-2.0 要求衍生作品的接收者获得一份许可副本。逐字副本见
  [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt)。上游仓库不含 `NOTICE` 文件，
  因此不涉及 `NOTICE` 传递（Apache-2.0 §4(d)）。

### 3.2 html-video 模板的上游

`references/style-catalog.json` 为每种风格记录了 `via` 字段，保留了 html-video 为其模板附带的
来源信息。23 种风格中有 7 种可追溯到更早的 MIT 许可项目。由于本项目的目录描述了同样的风格，
这些声明在此一并复现。

按目录中记录的精确对应关系：

#### `frontend-slides` —— 4 种风格

- **版权**：Zara Zhang © 2025
- **许可**：MIT
- **来源**：<https://github.com/zarazhangrui/frontend-slides>
- **风格**：`frame-bold-poster`、`frame-bold-signal`、`frame-creative-voltage`、
  `frame-electric-studio`

#### `huashu-design` —— 3 种风格

- **版权**：alchaincyf（花叔 · 花生）© 2026
- **许可**：MIT
- **来源**：<https://github.com/alchaincyf/huashu-design>
- **风格**：`frame-build-minimal`、`frame-pentagram-stat`、`frame-takram-organic`

#### `hyperframes-student-kit`（Nate Herk）—— 1 种风格

- **版权**：Nate Herk
- **许可**：MIT（按目录中该条目的 `license` 字段记录）
- **风格**：`frame-product-promo-30s` —— 上游记录为 `linear-promo-30s` 的 fork，
  品牌相关的文案与素材已替换为通用占位内容。

html-video 自己的 `ATTRIBUTIONS.md` 记录了前两个上游，并给出了它对此类模板的处理原则：静态
幻灯片设计被重新表达为原创的 CSS/SVG 关键帧时间轴，配以新的示例数据，不做逐字源码复制；部分
风格上挂着的设计事务所名字（Pentagram、Build、Takram）记录为**仅表灵感来源，绝不表示隶属或
背书**。本项目沿用这一立场。

上述三个上游的 MIT 许可声明：

```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### 3.3 设计事务所名称 —— 仅表灵感，无隶属关系

部分风格名引用了真实的设计事务所或出版物，作为风格灵感来源的记录（Pentagram、Build、
Takram、NYT、Vignelli、Swiss Grid）。这些**仅为事实性的灵感说明**。本项目 —— 以及它之前的
html-video —— **与其中任何一方均无隶属、背书或赞助关系**。项目中不含任何第三方的 logo、
字标、字体文件或品牌素材；所有画面都用系统字体从零创作。

---

## 4. 方法论上的思路来源

解说与音画同步方法论（词边界字幕、两级时钟、语速标定、QC 判据）参考了下列项目，它们
**由不同作者独立开发，与本项目不是同一作者**：

- **[Vincentwei1021/anything2explainer](https://github.com/Vincentwei1021/anything2explainer)**
  —— Remotion + TypeScript 路线。本项目从其承继了「解说 + 音画同步」这套工程方法论。
- **[nexu-io/html-video](https://github.com/nexu-io/html-video)** —— Apache-2.0。除第 3.1 节
  所述的风格目录外，其「在本机把 HTML 变成 MP4」的整体工程取舍亦有参考价值。

原始思路作者亦在自己的私有工作中做过 WorkBuddy 平台的适配版本（`anything2explainer` 技能的
本地特化版、`html-video-workbuddy-driver`）。**这些适配版不随本仓库分发，运行时也不需要。**
名字仅出现在注释与历史记录中。

**本项目自己的设计**：确定性 seek 渲染器、`B()` 节拍锚定、封面双方案，以及
`lint_frames.py` / `qc_check.py` 的判据。

---

## 再分发者须知

| 必须随你的副本一起提供 | 原因 |
|---|---|
| `LICENSE` | 原创代码的 MIT 条款 |
| `THIRD_PARTY_NOTICES.md`（本文件） | Apache-2.0 §4 + MIT 通知保留要求 |
| `licenses/Apache-2.0.txt` | Apache-2.0 §4(a) 要求附带一份许可副本 |
| `assets/gsap-README.md` | GSAP 许可参考；并保持 `gsap.min.js` 内的版权头完整 |

*最后审阅：2026-09-21。*
