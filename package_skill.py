#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
package_skill.py —— 把 html-explainer 打包成可带到任意终端的 zip。

设计取舍：
  · **排除 node/node_modules/**（14MB，且平台相关）—— setup_env.sh --install 会重装。
    这样 zip 只有几十 KB，纯文本 + 一份 GSAP。
  · **保留 assets/gsap.min.js**（72KB，离线必需，体积可接受）。
  · **保留 README / LICENSE / THIRD_PARTY_NOTICES.md / licenses/** —— 再分发时必须随包
    带上这些文件（Apache-2.0 §4 要求收到衍生作品的人同时收到许可证副本）。
  · **排除仓库卫生文件**（.github/、.gitignore、.gitattributes）—— 它们属于 GitHub
    仓库，不属于可移植的技能包。
  · 排除运行时产物（out/、audio/、*.beats.js、__pycache__、诊断脚本）。

用法：
  python package_skill.py                 # 产出 dist/html-explainer-vX.Y.zip
  python package_skill.py --with-deps     # 连 node_modules 一起打（完全离线可跑，~14MB）
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from datetime import date

SKILL_ROOT = os.path.dirname(os.path.abspath(__file__))

# 目录名匹配即整棵排除
EXCLUDE_DIRS = {
    "node_modules", "__pycache__", "dist", "out", "audio", ".git",
    ".pytest_cache", "qc_frames",
    ".github",              # 仓库卫生：CI / issue 模板不属于可移植技能包
    "render", "research", "script",   # 项目级产物（防在技能目录内建过 demo）
}
# 文件名 / 后缀排除
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".beats.js", ".mp4", ".mp3", ".wav", ".log")
EXCLUDE_NAMES = {
    "package-lock.json", ".DS_Store", "Thumbs.db", "qc_sheet.jpg", "qc_report.md",
    ".gitignore", ".gitattributes",
}


def version() -> str:
    md = os.path.join(SKILL_ROOT, "SKILL.md")
    try:
        txt = open(md, encoding="utf-8").read()
        m = re.search(r"^version:\s*(\S+)", txt, re.M)
        if m:
            return m.group(1).strip().strip('"\'')
    except OSError:
        pass
    return "1.0.0"


def should_skip(rel: str, with_deps: bool) -> bool:
    parts = rel.replace("\\", "/").split("/")
    for p in parts[:-1]:
        if p in EXCLUDE_DIRS:
            if with_deps and p == "node_modules":
                continue
            return True
    name = parts[-1]
    if name in EXCLUDE_NAMES:
        return True
    if name.endswith(EXCLUDE_SUFFIX):
        return True
    # 临时诊断脚本（下划线开头 .js/.mjs/.py，非技能正式脚本）
    if parts[0] == "scripts" and name.startswith("_"):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-deps", action="store_true",
                    help="把 node/node_modules 一起打包（离线可跑，体积 ~14MB）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ver = version()
    dist = os.path.join(SKILL_ROOT, "dist")
    os.makedirs(dist, exist_ok=True)
    tag = "-full" if args.with_deps else ""
    out = args.out or os.path.join(dist, f"html-explainer-v{ver}{tag}.zip")

    count = 0
    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(SKILL_ROOT):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS or
                       (args.with_deps and d == "node_modules")]
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, SKILL_ROOT)
                if should_skip(rel, args.with_deps):
                    continue
                arc = os.path.join("html-explainer", rel.replace("\\", "/"))
                z.write(full, arc)
                count += 1
                total += os.path.getsize(full)

    size = os.path.getsize(out)
    print(f"✓ 打包完成：{out}")
    print(f"  文件 {count} 个 · 源 {total / 1024:.0f}KB · zip {size / 1024:.0f}KB"
          f"（压缩率 {100 - size * 100 / max(total, 1):.0f}%）")
    if not args.with_deps:
        print("  注：未含 node/node_modules —— 目标机首次跑 `bash setup_env.sh --install` 装齐")
    print()
    print("  带到新终端后：")
    print("    1. 解压到 ~/.workbuddy/skills/  （或任意位置，脚本按自身路径定位）")
    print("    2. bash setup_env.sh --install")
    print("    3. python scripts/new_project.py <name> && 编辑 narration.json …")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
