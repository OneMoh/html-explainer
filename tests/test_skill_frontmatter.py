#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SKILL.md frontmatter 的回归测试（零依赖，直接 python tests/test_skill_frontmatter.py）。

守的是一条**本地不可观测**的不变式：

  frontmatter 的 description 必须 ≤ 1024 字符。

为什么值得单独守：description 超限时，本技能在本地一切正常 —— 脚本能跑、单元测试全绿、
CI 全绿；只有在按 1024 字符规则扫描的加载器里（Claude Code / ZCode 等），
**整个 skill 才会被静默丢弃**：列表里没有、也永远触发不了，而且不报任何错。
所以缺陷只能在「换一个加载器」时才暴露，代价是维护者收到一条 issue（见 issue #3）。

两段：
  A. 真实 SKILL.md 的不变式（长度上限 / name 不变 / 触发词仍在 / YAML 平面标量安全）
  B. **闸门本身能不能红** —— 用合成夹具分别喂超长与合规的 description，
     断言 check_integrity 的检查函数在超长时确实报 fail。
     （没有 B，A 全绿也可能只是「这道闸门从来没生效过」。）

失败即以非零码退出（CI 直接吃退出码）。
"""
from __future__ import annotations

import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 加载器的硬上限；与 scripts/check_integrity.py 的 DESC_LIMIT 必须一致
DESC_LIMIT = 1024
# description 至少要有这么多字，否则等于没写（触发说明会退化成噪音）
DESC_MIN = 80
# 触发词：这些是「用户在对话里真会说的话」，压缩时最容易顺手删掉、删掉就再也搜不到
TRIGGERS = ["html-explainer", "explainer video", "MG 视频", "HTML 讲解视频", "科普", "讲解", "视频"]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ci = _load("check_integrity", "scripts/check_integrity.py")

fails: list[str] = []


def check(label, got, want):
    if got != want:
        fails.append(f"{label}\n    得到: {got!r}\n    应为: {want!r}")
    else:
        print(f"  OK  {label}")


def frontmatter(path):
    text = io.open(path, encoding="utf-8").read()
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    return m.group(1) if m else None


def field(fm, key):
    m = re.search(r"^%s:[ \t]*(.*)$" % key, fm, re.M)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------- A. 真实文件
print("A. SKILL.md frontmatter（真实文件）")
skill = os.path.join(ROOT, "SKILL.md")
fm = frontmatter(skill)

check("frontmatter 存在且可切出", fm is not None, True)
if fm is None:
    print("\nfrontmatter 都切不出来，后面的检查没有意义")
    sys.exit(1)

name = field(fm, "name")
version = field(fm, "version")
desc = field(fm, "description")

# name 是加载器的键：改名 = 老用户的配置/引用全部失效
check("name 未变", name, "html-explainer")
check("version 是 x.y.z", bool(re.fullmatch(r"\d+\.\d+\.\d+", version or "")), True)
check("description 存在", desc is not None and len(desc) > 0, True)

n = len(desc or "")
nb = len((desc or "").encode("utf-8"))
print(f"      description = {n} 字符 / {nb} 字节（上限 {DESC_LIMIT}）")

# ---- 长度：上不超加载器上限、下有下限 ----
check("description ≤ 1024 字符（加载器上限）", n <= DESC_LIMIT, True)
check("description ≥ 80 字符（没被削成噪音）", n >= DESC_MIN, True)

# ---- YAML 平面标量安全 ----
# `: `（ASCII 冒号+空格）会被 YAML 当成新键的开头；全角「：」不受影响
check("description 不含 ASCII「冒号+空格」", ": " in (desc or ""), False)
check("description 不以 YAML 特殊字符开头",
      (desc or "")[:1] in ('"', "'", ">", "|", "-", "?", ":", ""), False)

# ---- 触发词：压缩时最容易顺手删掉的部分 ----
for t in TRIGGERS:
    check(f"触发词仍在：{t}", t in (desc or ""), True)

# ---- 曾经只写在 description 里的细节，现在必须在正文 ----
body = io.open(skill, encoding="utf-8").read()
for token, why in [
    ("references/style-catalog.md", "风格目录落点"),
    ("style_director.py", "v2.0 模板编排"),
    ("png-fast", "渲染通道口径"),
    ("1080×1920", "9:16 封面规格"),
]:
    check(f"正文仍覆盖：{why}", token in body, True)

# ---------------------------------------------------- B. 闸门本身能被触发
print("\nB. check_integrity.check_description_length（合成夹具）")
tmp = tempfile.mkdtemp(prefix="hxe-fmtest-")
try:
    def fixture(desc_text):
        d = tempfile.mkdtemp(dir=tmp)
        io.open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8", newline="").write(
            "---\nname: html-explainer\nversion: 9.9.9\ndescription: %s\n---\n\nbody\n" % desc_text
        )
        return d

    # 超长 → 必须红（这是 issue #3 的实际形态）
    long_desc = "科普讲解视频。" * 200          # 1400 字符
    d_long = fixture(long_desc)
    f1: list[str] = []
    ci.check_description_length(d_long, f1)
    check("超长 description → 报 fail", len(f1) >= 1, True)
    check("报的正是长度那条", any("超过" in x and "1024" in x for x in f1), True)

    # 合规 → 必须绿（否则闸门是「永远红」，同样没鉴别力）
    d_ok = fixture("把主题做成讲解视频并渲染成 MP4。触发场景：要做科普/讲解/教学类视频。")
    f2: list[str] = []
    ci.check_description_length(d_ok, f2)
    check("合规 description → 不报 fail", f2, [])

    # 缺字段 → 必须红
    d_missing = tempfile.mkdtemp(dir=tmp)
    io.open(os.path.join(d_missing, "SKILL.md"), "w", encoding="utf-8", newline="").write(
        "---\nname: html-explainer\nversion: 9.9.9\n---\n\nbody\n"
    )
    f3: list[str] = []
    ci.check_description_length(d_missing, f3)
    check("缺 description → 报 fail", len(f3) >= 1, True)

    # 边界：正好 1024 字符 → 绿；1025 → 红
    d_edge = fixture("科" * DESC_LIMIT)
    f4: list[str] = []
    ci.check_description_length(d_edge, f4)
    check(f"正好 {DESC_LIMIT} 字符 → 不报 fail（边界含等号）", f4, [])

    d_over = fixture("科" * (DESC_LIMIT + 1))
    f5: list[str] = []
    ci.check_description_length(d_over, f5)
    check(f"{DESC_LIMIT + 1} 字符 → 报 fail", len(f5) >= 1, True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fails:
    print(f"\n失败 {len(fails)} 项：\n")
    for f in fails:
        print("  ✗ " + f)
    sys.exit(1)
print("\n全部通过")
