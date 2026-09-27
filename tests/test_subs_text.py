#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""subs 文本规则的回归测试（零依赖，直接 python tests/test_subs_text.py）。

守的是一条不变式：

  去句读标点，但**小数点不是标点**。

五个出口共用这一个定义 —— 屏幕字幕、SRT/VTT、B() 节拍匹配、火山长文本切句、
以及给下游读的 subs.json。任何一处把小数点当标点删掉，屏幕上就会出现
「念 2.4%、写 24%」这种差一个数量级的假数字；这类错不会报错，只会静静地骗人。

失败即以非零码退出（CI 直接吃退出码）。
"""
from __future__ import annotations

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


subs = _load("subs", "scripts/subs.py")
tts_volcano = _load("tts_volcano", "scripts/tts_volcano.py")

fails: list[str] = []


def check(label, got, want):
    if got != want:
        fails.append(f"{label}\n    得到: {got!r}\n    应为: {want!r}")
    else:
        print(f"  OK  {label}")


# ---- 屏幕文本：小数点保留 ----
print("屏幕文本 clean_sub_text")
check("数字间小数点保留", subs.clean_sub_text("涨了2.4%，注意"), "涨了2.4%注意")
check("纯小数", subs.clean_sub_text("2.4%"), "2.4%")
check("多位小数", subs.clean_sub_text("3.14159"), "3.14159")
check("版本号（两个点都在数字间）", subs.clean_sub_text("升到1.2.3"), "升到1.2.3")
check("英文数字（lang=en 保留词间空格）", subs.clean_sub_text("up 2.5x", "en"), "up 2.5x")
check("句号仍删（数字后不是数字）", subs.clean_sub_text("结束了."), "结束了")
check("省略号仍删", subs.clean_sub_text("等等..."), "等等")
check("前导小数点仍删", subs.clean_sub_text("口径.5"), "口径5")
check("逗号仍删（用户要求）", subs.clean_sub_text("1,234万"), "1234万")
check("冒号仍删（用户要求）", subs.clean_sub_text("12:30 开播"), "1230开播")
check("句号仍删", subs.clean_sub_text("甲、乙。"), "甲、乙")
check("全角数字也认", subs.clean_sub_text("涨２.４％"), "涨２.４％")

# ---- 对齐用的去标点：同一套规则 ----
print("对齐用 _PUNCT_RE")
check("小数点不被吃", subs._PUNCT_RE.sub("", "涨2.4%"), "涨2.4%")
check("句末点被吃", subs._PUNCT_RE.sub("", "结束."), "结束")
check("逗号被吃", subs._PUNCT_RE.sub("", "1,234"), "1234")
# 注意这个正则是「匹配用归一化」：连空格一起削（两侧同规则，所以照样对得上）。
# 屏幕文本那条路（clean_sub_text）才管空格，别把两者混为一谈。
check("中英混排（空格也归一化）", subs._PUNCT_RE.sub("", "a. 2.4% b"), "a2.4%b")
# ↓ 两条专门钉住「断言写在点之前还是之后」：写反了它们会静默通过。
# `X(?<!\d)` 断言的是 X 右边的字符，所以「点的左边是数字」根本管不住。
check("点左边非数字 → 删", subs._PUNCT_RE.sub("", "a.2"), "a2")
check("点右边非数字 → 删", subs._PUNCT_RE.sub("", "2.a"), "2a")
check("两点夹数字 → 留", subs._PUNCT_RE.sub("", "2.4"), "2.4")
check("点多侧数字（版本号）→ 全留", subs._PUNCT_RE.sub("", "1.2.3"), "1.2.3")

# ---- 火山长文本切句：不在小数点处切 ----
print("火山 split_long_text")
long_text = "营收增长2.4%，其中线上部分贡献了大头，这一段的文字故意写得很长" * 4
parts = tts_volcano.split_long_text(long_text, limit=40)
check("切分后无碎片以数字点收尾", any(p.endswith("2.") for p in parts), False)
check("切分不丢字（拼回等于原文）", "".join(parts), long_text)
check("短文本原样返回", tts_volcano.split_long_text("2.4%", limit=40), ["2.4%"])

# ---- 节拍模板：B() 的归一化不削小数点 ----
print("beats.js 模板自洽")
beats_tmpl = subs.BEATS_TMPL
check("模板含 norm()", "function norm(" in beats_tmpl, True)
check("norm 保护数字间小数点", "(\\d)\\.(\\d)" in beats_tmpl, True)
check("模板仍会丢弃逗号冒号", ",.!?;:|" in beats_tmpl, True)

if fails:
    print(f"\n失败 {len(fails)} 项：\n")
    for f in fails:
        print("  ✗ " + f)
    sys.exit(1)
print("\n全部通过")
