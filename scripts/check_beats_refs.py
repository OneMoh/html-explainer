#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_beats_refs.py —— B()/Be() 节拍引用的**构建期校验**（渲染前跑，秒级出结果）。

为什么需要它
------------
`B()` 的匹配规则是**前缀匹配**：
    bt === t  ||  bt.startsWith(t)  ||  t.startsWith(bt)      （归一化后）
也就是 text 必须是**块文本的开头**，或者块文本本身以 text 开头。取中间一段会抛错：

    块文本「一位父亲写下《被网游毁掉的孩子》」→  B('一位父亲写下') ✓    B('被网游毁掉的孩子') ✗

归一化会去掉 ，。、！？；：,.!?;:| 与空白（**保留数字里的小数点**、**不去《》「」**）。
拿不准就抄块文本的前 6–10 个字。

而 `B()` 抛错**只在渲染到那一帧时才发生** —— 前面几百帧白渲，长片要等十几分钟才炸。
这类「只在运行时才炸的静态错误」应当有一个构建期出口，这就是本脚本。

用法：
    python check_beats_refs.py --project .                  # 全量
    python check_beats_refs.py --project . --only hook_q,r1_data
退出码：有失配 = 1，全绿 = 0（可直接串进 CI / 流水线 && 链）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import List, Tuple

# 同时抓 B('…') 与 Be('…')，单双引号、内部可含转义
CALL = re.compile(r"\bB(?:e)?\(\s*(['\"])((?:\\.|(?!\1).)*)\1\s*\)")
BEATS_DATA = re.compile(r"window\.__BEATS__\s*=\s*(\[.*?\])\s*;", re.S)


def norm(s: str) -> str:
    """与 subs.py 生成的 beats.js 里的 norm() 逐字对齐（改一处等于没改）。"""
    s = re.sub(r"(\d)\.(\d)", lambda m: m.group(1) + "\ue000" + m.group(2), s)
    s = re.sub(r"[\s，。、！？；：,.!?;:|]", "", s)
    return s.replace("\ue000", ".")


def unescape(q: str) -> str:
    """把 JS 字符串字面量里的 \\' \\" \\\\ 还原成原字符，否则带撇号的查询会假失配。"""
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), q)


def load_beats(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    m = BEATS_DATA.search(open(path, encoding="utf-8").read())
    return json.loads(m.group(1)) if m else []


def check_one(fdir: str, sid: str) -> Tuple[int, List[str]]:
    """返回 (失配数, 报告行)。"""
    hp = os.path.join(fdir, sid + ".html")
    if not os.path.exists(hp):
        return 0, [f"  ?  {sid:<14} 无帧文件（跳过）"]

    beats = load_beats(os.path.join(fdir, sid + ".beats.js"))
    nb = [norm(b.get("text", "")) for b in beats]
    src = open(hp, encoding="utf-8").read()
    calls = [unescape(q) for _, q in CALL.findall(src)]

    lines: List[str] = []
    errs: List[str] = []

    if calls and not nb:
        errs.append("本帧有 B() 调用，但 frames/%s.beats.js 不存在或为空 —— 先跑 subs.py" % sid)
    for q in calls:
        t = norm(q)
        if not any(bt == t or bt.startswith(t) or t.startswith(bt) for bt in nb):
            errs.append(
                "B('%s') 在本帧块表里解析不到（前缀匹配失败）\n"
                "          本帧可用块：%s" % (q, [b.get("text") for b in beats])
            )

    tag = "OK " if not errs else "ERR"
    lines.append(
        f"  {tag} {sid:<14} B()/Be() 调用 {len(calls):2d} · 命中 {len(calls) - len(errs):2d} · 失配 {len(errs):2d}"
    )
    for e in errs:
        lines.append(f"        ✗ {e}")
    return len(errs), lines


def main() -> int:
    ap = argparse.ArgumentParser(description="构建期校验 B()/Be() 节拍引用")
    ap.add_argument("--project", default=".")
    ap.add_argument("--only", default="", help="逗号分隔的场景 id；缺省 = 全量")
    args = ap.parse_args()

    fdir = os.path.join(args.project, "frames")
    if not os.path.isdir(fdir):
        print(f"[beats] 找不到 {fdir}", file=sys.stderr)
        return 2

    want = [s.strip() for s in args.only.split(",") if s.strip()]
    ids = want or sorted(
        f[:-5] for f in os.listdir(fdir)
        if f.endswith(".html") and not f.startswith("_")
    )

    bad = 0
    for sid in ids:
        n, lines = check_one(fdir, sid)
        bad += n
        for ln in lines:
            print(ln)

    if bad:
        print(f"\n[beats] ✗ 失配 {bad} 处 —— B() 只在前缀处命中，改抄块文本的前 6–10 个字")
    else:
        print(f"\n[beats] ✓ {len(ids)} 个场景的节拍引用全部可解析")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
