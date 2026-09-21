#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
import_styles.py —— 【移植期一次性工具，非运行时依赖】

把已安装的 html-video 仓库里的模板设计规范（`SKILL.md` 的画布/字体/时间轴/配色
纪律 + 每个模板的元数据）**抄成纯文本**，输出到本技能的：

    references/style-catalog.md
    references/style-catalog.json

【为什么叫"抄"不叫"导入"】
这是**知识提取**，不是代码依赖。跑完本脚本，技能就永久拥有了 23 个模板的风格知识，
之后**做视频完全不需要 html-video 存在** —— 类比：去餐厅把菜谱抄回家，
以后自己做菜不需要那家餐厅营业。

验证零依赖：
    grep -rn "html-video" scripts/ assets/ references/ \\
        --include="*.py" --include="*.mjs" --include="*.html" --include="*.md"
    → 只会命中注释署名，没有 import / 没有读文件 / 没有 subprocess

【什么时候才需要跑它】
  仅当你想**从上游 html-video 更新风格目录**时。日常做视频永远不需要。
  目标机器上没装 html-video → 本脚本用不了 → 但技能照跑不误。

用法：
  python import_styles.py --from "<html-video 仓库>/templates" [--out <技能>/references]
  python import_styles.py --from "D:/tools/html-video/templates"        # 示例（换成你的路径）
  python import_styles.py --from <dir> --out <技能>/references
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 分类中文名（模板 yaml 的 category → 人话）
CAT_ZH = {
    "presentation": "演示 / 标题卡",
    "data-viz": "数据可视化",
    "explainer": "图解 / 流程",
    "ambient": "氛围 / 空镜",
    "marketing": "营销 / Hero",
    "intro-outro": "片头片尾",
    "social-shorts": "社媒竖版",
    "product-demo": "产品演示",
    "audio": "音频驱动",
}


def parse_yaml_lite(text: str) -> dict:
    """
    极简 YAML 读取（只取点分路径的标量），不依赖 pyyaml。

    · 支持任意层级（按缩进栈推路径），所以 `output.duration.min_sec` 能取到
    · 支持 `>` / `|` 块标量（取后续更深缩进的正文行，拼成一行）
    · 支持行内数组 `[a, b]`（原样返回字符串）
    """
    out: dict = {}
    stack: list[tuple[int, str]] = []   # (indent, key)
    i = 0
    lines = text.splitlines()
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()

        # 弹栈：同层或更浅层的旧键
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = ".".join([k for _, k in stack] + [key])

        if val in (">", "|", ">-", "|-", ">+", "|+"):
            # 块标量：收后续缩进更深（或空行）的行
            buf = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == "":
                    buf.append("")
                    i += 1
                    continue
                nind = len(nxt) - len(nxt.lstrip())
                if nind <= indent:
                    break
                buf.append(nxt.strip())
                i += 1
            out[path] = " ".join(x for x in buf if x).strip()
            continue

        out[path] = val
        if val == "":
            stack.append((indent, key))
    return out


def unquote(s: str) -> str:
    return (s or "").strip().strip('"').strip("'")


def clean_list(s: str) -> str:
    """`["16:9", "9:16"]` → `16:9 · 9:16`"""
    s = (s or "").strip()
    s = s.strip("[]")
    parts = [p.strip().strip('"').strip("'") for p in s.split(",")]
    return " · ".join(p for p in parts if p)


def parse_frontmatter(md: str) -> dict:
    """取 SKILL.md frontmatter 的标量键（含 zh_name / emoji / recommended）。"""
    m = re.match(r"^---\s*\n(.*?)\n---", md, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = unquote(mm.group(2))
    return fm


def parse_style_body(md: str) -> dict:
    """从 SKILL.md 正文提炼画布/字体/时间轴/配色纪律要点。"""
    body = re.sub(r"^---\s*\n.*?\n---", "", md, flags=re.S)
    info = {}
    for key, pat in [
        ("canvas", r"【画布】\s*(.+?)(?:\n\n|\n【|$)"),
        ("fonts", r"【字体】\s*(.+?)(?:\n\n|\n【|$)"),
        ("timeline", r"【主结构[^】]*】\s*(.+?)(?:\n\n|\n【|$)"),
        ("palette", r"【配色纪律】\s*(.+?)(?:\n\n|\n【|$)"),
        ("content", r"【内容纪律】\s*(.+?)(?:\n\n|\n【|$)"),
    ]:
        m = re.search(pat, body, re.S)
        if m:
            info[key] = " ".join(m.group(1).split())
    return info


def collect(tpl_root: str) -> list[dict]:
    rows = []
    for name in sorted(os.listdir(tpl_root)):
        d = os.path.join(tpl_root, name)
        yml = os.path.join(d, "template.html-video.yaml")
        if not os.path.isfile(yml):
            continue
        try:
            ytext = open(yml, encoding="utf-8").read()
        except OSError:
            continue
        y = parse_yaml_lite(ytext)

        skill_md = os.path.join(d, "SKILL.md")
        fm, body = {}, {}
        if os.path.isfile(skill_md):
            md = open(skill_md, encoding="utf-8").read()
            fm = parse_frontmatter(md)
            body = parse_style_body(md)

        # best_for 是 yaml 里的字符串列表：
        #   best_for:
        #     - "Section / chapter divider"
        best_for: list[str] = []
        m_bf = re.search(r"^best_for:\s*$", ytext, re.M)
        if m_bf:
            for line in ytext[m_bf.end():].splitlines():
                s = line.strip()
                if s.startswith("- "):
                    best_for.append(unquote(s[2:]))
                elif s and not s.startswith("#"):
                    break

        # 上游来源（via_skill.name）——用于署名
        via_skill = ""
        m_via = re.search(r"via_skill:\s*\n(?:.*\n)*?\s+name:\s*(.+)", ytext)
        if m_via:
            via_skill = unquote(m_via.group(1))

        src = None
        for cand in (os.path.join(d, "source", "index.html"),
                     os.path.join(d, "index.html")):
            if os.path.isfile(cand):
                src = cand
                break
        kf_count, color_sample = 0, ""
        multi = False
        if src:
            html = open(src, encoding="utf-8", errors="replace").read()
            kf_count = html.count("@keyframes")
            # 多 composition 结构：index.html 引 compositions/*.html 或 data-composition-src
            multi = bool(re.search(r'data-composition-src|compositions/[a-z\-]+\.html', html))
            # 抓几个十六进制色值当配色线索（最多 5 个）
            cols = re.findall(r"#[0-9a-fA-F]{6}\b", html)
            seen, uniq = set(), []
            for c in cols:
                cl = c.lower()
                if cl not in seen and cl not in ("#ffffff", "#000000"):
                    seen.add(cl)
                    uniq.append(c)
                if len(uniq) >= 5:
                    break
            color_sample = " ".join(uniq)

        rows.append({
            "id": unquote(y.get("id", name)),
            "name": unquote(y.get("name", name)),
            "zh_name": fm.get("zh_name", ""),
            "emoji": fm.get("emoji", ""),
            "category": unquote(y.get("category", "")),
            "subcategory": unquote(y.get("subcategory", "")),
            "engine": unquote(y.get("engine", "hyperframes")),
            "description": unquote(y.get("description", fm.get("description", ""))),
            "zh_description": fm.get("zh_description", ""),
            "dmin": unquote(y.get("output.duration.min_sec", "")),
            "dmax": unquote(y.get("output.duration.max_sec", "")),
            "aspects": clean_list(unquote(y.get("output.resolution.supported_aspects", "")))
                        or "16:9",
            "recommended": fm.get("recommended", ""),
            "style": body,
            "best_for": best_for,
            "kf": kf_count,
            "colors": color_sample,
            "multi": multi,
            "license": unquote(y.get("license.spdx", "")),
            "via": via_skill,
            "has_src": bool(src),
            "has_skill_md": bool(fm),
        })
    return rows


def classify(r: dict) -> str:
    """模板的复刻难度分级。

    rich  —— 单文件 + 纯 CSS @keyframes 时间轴。**可直接 seek 渲染，零改动**。
    gsap  —— 多 composition + GSAP（CDN 加载），或 Remotion 引擎。需重写为单文件
             （见 `lessons.md` #9 的 `__hvUnfreeze` 整类坑）。
    """
    if r.get("engine") == "remotion":
        return "gsap"
    if r.get("multi"):
        return "gsap"
    if r["kf"] >= 1 and r["has_src"]:
        return "rich"
    return "gsap"


def to_markdown(rows: list[dict]) -> str:
    L = []
    L.append("# 画面风格目录（从 html-video 模板库导入）")
    L.append("")
    L.append("> **这是风格知识，不是代码依赖。**")
    L.append("> html-explainer 运行时不引用 html-video 仓库；本目录用于挑选画面语言，")
    L.append("> 复刻时须由 agent 改写成「离线 + 纯 CSS keyframes + 字幕带禁区」的合规帧。")
    L.append("> 复刻契约见 `references/frame-contract.md`；本目录由 `scripts/import_styles.py` 生成。")
    L.append("")
    n_rich = sum(1 for r in rows if classify(r) == "rich")
    n_gsap = len(rows) - n_rich
    L.append(f"共 **{len(rows)}** 个风格，覆盖 {len({r['category'] for r in rows})} 个类别。")
    L.append("")
    L.append("### 两类模板（复刻成本不同，先看这个）")
    L.append("")
    L.append(f"| 类型 | 数量 | 结构 | 适配 seek 渲染器 |")
    L.append("|---|---|---|---|")
    L.append(f"| **rich（推荐）** | {n_rich} | 单文件 + 纯 CSS `@keyframes` 时间轴；"
             f"带完整风格规范（时间轴/配色/字体）| **零改动可渲染**，只需换字体栈 + 让出字幕带 |")
    L.append(f"| **gsap** | {n_gsap} | 多 composition + CDN 加载 GSAP | "
             f"须重写为单文件 + 本地 GSAP（见 `lessons.md` #9 的 `__hvUnfreeze` 整类坑）|")
    L.append("")
    L.append("> **rich 为什么零改动可用**：seek 渲染器用 "
             "`document.getAnimations().currentTime = t*1000` 驱动 CSS 动画，"
             "时间轴已由 CSS `animation-delay` 声明，天然确定性。"
             "gsap 型的多 composition 结构在单帧里没有起播钩子，"
             "正是 `__hvUnfreeze` 静默失败的来源。")
    L.append("")

    # 速查表
    L.append("## 速查表")
    L.append("")
    L.append("| id | 名称 | 类别 | 时长档 | 画幅 | 类型 | 说明 |")
    L.append("|---|---|---|---|---|---|---|")
    for r in rows:
        dur = f"{r['dmin']}–{r['dmax']}s" if r["dmin"] else "可变"
        typ = "★rich" if classify(r) == "rich" else "gsap"
        L.append(f"| `{r['id']}` | {r['emoji']} {r['zh_name'] or r['name']} | "
                 f"{CAT_ZH.get(r['category'], r['category'])}/{r['subcategory']} | {dur} | "
                 f"{r['aspects']} | {typ} | {(r['zh_description'] or r['description'])[:40]} |")
    L.append("")

    # 分类索引
    L.append("## 按用途挑风格")
    L.append("")
    bycat: dict[str, list[dict]] = {}
    for r in rows:
        bycat.setdefault(r["category"], []).append(r)
    for cat, items in sorted(bycat.items()):
        L.append(f"### {CAT_ZH.get(cat, cat)}")
        L.append("")
        for r in items:
            L.append(f"- **`{r['id']}`** — {r['zh_name'] or r['name']}")
            if r["zh_description"] or r["description"]:
                L.append(f"  - {r['zh_description'] or r['description']}")
        L.append("")

    # 风格基因详表
    L.append("## 风格基因（复刻依据）")
    L.append("")
    L.append("每个风格给出画布 / 字体 / 时间轴 / 配色纪律 —— 这四项足以复刻视觉签名。")
    L.append("")
    for r in rows:
        cls = classify(r)
        L.append(f"### {r['emoji']} `{r['id']}` — {r['zh_name'] or r['name']}")
        L.append("")
        L.append(f"- **复刻类型**：{'★ rich（零改动可渲染）' if cls == 'rich' else 'gsap（需重写为单文件）'}")
        L.append(f"- **引擎**：{r['engine']} · **CSS 动画数**：{r['kf']}")
        dur = f"{r['dmin']}–{r['dmax']}s" if r["dmin"] else "可变"
        L.append(f"- **时长档**：{dur} · **画幅**：{r['aspects']}")
        if r.get("best_for"):
            L.append(f"- **适合**：{'；'.join(r['best_for'])}")
        if r.get("colors"):
            L.append(f"- **源码色值线索**：{r['colors']}")
        st = r["style"]
        if st.get("canvas"):
            L.append(f"- **画布**：{st['canvas']}")
        if st.get("fonts"):
            L.append(f"- **字体**：{st['fonts']}")
        if st.get("timeline"):
            L.append(f"- **时间轴**：{st['timeline']}")
        if st.get("palette"):
            L.append(f"- **配色纪律**：{st['palette']}")
        if st.get("content"):
            L.append(f"- **内容纪律**：{st['content']}")
        if cls != "rich" and not st:
            L.append("- ⚠️ 该模板为多 composition + GSAP 结构，**无现成风格规范** —— "
                     "复刻前先读 `source/index.html` 与 `compositions/*.html` 提取视觉 DNA。")
        L.append("")

    # 署名
    L.append("## 来源与署名")
    L.append("")
    L.append("画面风格提炼自 html-video 模板库（全部 Apache-2.0 / MIT，允许再分发与商用）。")
    L.append("上游设计来源见下（部分模板直接原创于 html-video 作者）：")
    L.append("")
    via_map: dict[str, list[str]] = {}
    for r in rows:
        if r.get("via"):
            via_map.setdefault(r["via"], []).append(r["id"])
    for via, ids in sorted(via_map.items()):
        L.append(f"- **{via}** → {', '.join('`' + i + '`' for i in ids)}")
    L.append("")
    L.append("> 改编自模板的帧，建议在片尾或说明里保留风格署名。")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True,
                    help="html-video 的 templates/ 目录")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None, help="同时导出 JSON 目录")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    if not os.path.isdir(src):
        print(f"✗ 不是目录：{src}", file=sys.stderr)
        return 1

    rows = collect(src)
    if not rows:
        print(f"✗ 在 {src} 没找到 template.html-video.yaml", file=sys.stderr)
        return 1

    out = args.out or os.path.join(SKILL_ROOT, "references", "style-catalog.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8", newline="\n").write(to_markdown(rows))
    print(f"✓ 风格目录：{out}（{len(rows)} 个风格）")

    if args.json:
        slim = [{k: v for k, v in r.items() if k != "style"} | {"style": r["style"]}
                for r in rows]
        open(args.json, "w", encoding="utf-8", newline="\n").write(
            json.dumps(slim, ensure_ascii=False, indent=2))
        print(f"✓ JSON 目录：{args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
