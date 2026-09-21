#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lint_frames.py —— 场景帧静态体检（渲染前跑，比渲完全片再发现问题便宜得多）。

检查项（全部来自 references/frame-contract.md 的八条契约 + 已知踩坑）：
  1. 画布：html,body 是否声明 1920×1080（或 project.json 的尺寸）
  2. 外部字体 / CDN：<link href="http...">、fonts.googleapis、@import url(http
  3. 色值字面量：#RRGGBB / rgb() / rgba() 出现在 CSS 里（theme.css 变量之外）
     —— 例外：纯黑/纯白阴影 rgba(0,0,0,x) 允许（阴影不是"配色"）
  4. 时间轴注册：window.__tl = （或 window.__timelines）
  5. GSAP 本地引用：../assets/gsap.min.js（禁 CDN）
  6. 墙钟逻辑：setInterval / setTimeout(数字) / requestAnimationFrame 计数
  7. CSS transition 入场
  8. B() 兜底：B('x') || 数字
  9. 字幕带禁区：CSS 里 bottom < 176px 的规则且带内容属性（启发式，转人工确认）
 10. 字体栈：必须含中文字体族（Microsoft YaHei / PingFang 等）

用法：
  python lint_frames.py --project .            # 全量
  python lint_frames.py --project . --only hook,decision
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGBA = re.compile(r"\brgba?\([^)]*\)")
FONT_LINK = re.compile(r"<link[^>]+href\s*=\s*[\"']https?://", re.I)
IMPORT_HTTP = re.compile(r"@import\s+url\(\s*[\"']?https?://", re.I)
GSAP_CDN = re.compile(r"<script[^>]+src\s*=\s*[\"']https?://", re.I)
B_FALLBACK = re.compile(r"B\([^)]*\)\s*\|\|")
WALLCLOCK = re.compile(r"setInterval\s*\(|setTimeout\s*\(\s*[a-zA-Z_]|requestAnimationFrame\s*\(\s*(?!function)")
CSS_TRANSITION = re.compile(r"transition\s*:", re.I)
BOTTOM_RULE = re.compile(r"(?<![-\w])bottom\s*:\s*(-?\d+)(px|%)")
CJK_FONT = re.compile(r"YaHei|PingFang|Noto Sans CJK|Source Han|Hiragino|SimHei|SimSun")

# 允许出现的颜色字面量（阴影/透视遮罩，不参与配色语义）
ALLOWED_RGBA_PREFIX = ("rgba(0,0,0", "rgba(0, 0, 0", "rgba(255,255,255", "rgba(255, 255, 255")


def check_file(path: str, want_w: int, want_h: int, is_cover: bool = False) -> list[str]:
    src = open(path, encoding="utf-8").read()
    name = os.path.basename(path)
    out: list[str] = []

    # 1. 画布（封面有自己的规格：16:9 版 1920×1080 / 3:4 版 1440×1080）
    if is_cover:
        if not re.search(r"width\s*:\s*\d+px", src) or not re.search(r"height\s*:\s*\d+px", src):
            out.append("封面：未见 width/height 像素声明")
    elif not re.search(rf"width\s*:\s*{want_w}px", src) or not re.search(rf"height\s*:\s*{want_h}px", src):
        out.append(f"画布：未见 width:{want_w}px / height:{want_h}px 声明")

    # 2. 外部字体 / 远程资源
    if FONT_LINK.search(src):
        out.append("外部 <link href=http…>（字体/样式）→ 违反契约 2（渲染器 5s 字体硬顶）")
    if IMPORT_HTTP.search(src):
        out.append("@import url(http…) → 违反契约 2")
    if GSAP_CDN.search(src):
        out.append("<script src=http…> → 违反契约 8（必须用 ../assets/gsap.min.js）")

    # 3. 色值字面量
    for m in HEX.finditer(src):
        val = m.group(0)
        # 允许在注释里说明用（如出处署名），其余算违规
        out.append(f"色值字面量 {val} → 违反契约 3（颜色只取 theme.css 变量）")
    for m in RGBA.finditer(src):
        v = m.group(0).replace(" ", "").lower()
        if v.startswith(ALLOWED_RGBA_PREFIX):
            continue
        if "var(" in v:      # rgba(var(--signal-rgb), .4) —— 取自主题变量，合规
            continue
        out.append(f"色值字面量 {m.group(0)} → 违反契约 3")

    # 4/5. 时间轴 + GSAP
    if "window.__tl" not in src and "window.__timelines" not in src:
        out.append("未见 window.__tl 注册 → 渲染器找不到时间轴（契约 4）")
    if "gsap" in src.lower() and "../assets/gsap.min.js" not in src:
        out.append("用了 gsap 但没引 ../assets/gsap.min.js")

    # 6/7. 墙钟 / transition
    if WALLCLOCK.search(src):
        out.append("疑似墙钟逻辑（setInterval / setTimeout / rAF）→ seek 渲染下必然失控")
    if CSS_TRANSITION.search(src):
        out.append("CSS transition: → 逐帧 seek 不生效，入场必须用 GSAP")

    # 8. B() 兜底
    if B_FALLBACK.search(src):
        out.append("B('…') || 数字 兜底写法 → 禁止（beats 缺失要在构建期暴露）")

    # 9. 字幕带禁区（启发式）
    for m in BOTTOM_RULE.finditer(src):
        v = int(m.group(1))
        unit = m.group(2)
        if unit == "px" and 0 <= v < 176:
            # 取该行上下文，判断是不是有内容的容器
            line_start = src.rfind("\n", 0, m.start()) + 1
            line_end = src.find("\n", m.end())
            line = src[line_start:line_end].strip()
            out.append(f"bottom:{v}px 落在字幕带/进度条禁区 → {line[:70]}")
    for m in re.finditer(r"bottom\s*:\s*calc\([^)]*\)", src):
        out.append(f"bottom:calc(…) 请人工核对是否 ≥176px → {m.group(0)[:70]}")

    # 10. 中文字体栈
    if CJK_FONT.search(src) is None:
        out.append("字体栈里没看到中文字体族 → 可能落到默认字体")

    return [f"{name}: {x}" for x in sorted(set(out))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--only", default="")
    ap.add_argument("--include-covers", action="store_true")
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    pj = json.load(open(os.path.join(proj, "project.json"), encoding="utf-8"))
    W, H = pj.get("width", 1920), pj.get("height", 1080)

    frames_dir = os.path.join(proj, "frames")
    names = sorted(f for f in os.listdir(frames_dir) if f.endswith(".html"))
    skip = {"_template.html"} | (set() if args.include_covers else {"cover_169.html", "cover_34.html"})
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    names = [n for n in names if n not in skip and (not only or n[:-5] in only)]

    all_issues: list[str] = []
    for n in names:
        all_issues += check_file(os.path.join(frames_dir, n), W, H, is_cover=n.startswith("cover_"))

    print(f"[lint] 检查 {len(names)} 个帧 · 画布 {W}×{H}")
    if not all_issues:
        print("[lint] ✓ 无契约违规")
        return 0
    for line in all_issues:
        print("  ✗", line)
    print(f"[lint] 共 {len(all_issues)} 条待确认")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
