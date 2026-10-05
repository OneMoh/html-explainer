#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate_check.py —— 六个确认点的硬闸门（v2.0）

为什么需要它
------------
SKILL.md 里写了「确认点必须停下等用户回话」，但**纸面规则会被静默跳过**——
agent 直接跑 style_director.py 就自选了风格，用户事后才发现「你没问过我」；
渲染同理：默认 PNG 一路渲完，用户才发现「你没问过我用哪条通道」。

本脚本把那条规则变成**挡在流水线前面的闸门**：
    进「场景构建」之前必须跑一次；不过就不许写 frames/。
    渲染之前必须再跑一次 `--phase render`；render_channel 没拍板就不许渲染。

用法
----
    python gate_check.py --project .                  # 校验（缺项即 ERROR，退出码 1）
    python gate_check.py --project . --init           # 生成 consent.json 模板（不含任何默认选择）
    python gate_check.py --project . --show           # 打印当前确认记录
    python gate_check.py --project . --phase render   # 只查渲染前必须拍板的那几项

判据（全部为 ERROR 即退出 1）
---------------------------
1. 项目根存在 `consent.json`
2. 下列每一项都有 `choice`（非空）且 `decided_by == "user"`
   - `theme`           配色方向（色号 + 气质描述）
   - `style`           风格候选的最终选定（可含 style_director 的建议，但选择权在用户）
   - `form`            影片形态（纯视觉 / 主视觉+章节讲解 / …）
   - `voice`           配音方案 + 音色
   - `duration_sec`    目标时长
   - `cover`           封面规格（哪几张）
   - `render_channel`  渲染通道（png / png-fast / jpeg q95 / jpeg q82）★ 渲染前必问
3. 若某项 `decided_by != "user"` → **停下**，把候选列给用户，拿到答复再改这个字段

设计原则：**脚本不替用户做任何选择**，`--init` 生成的模板里 choice 全为空字符串。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REQUIRED = [
    ("theme", "配色方向（色号 + 一句气质描述）"),
    ("style", "风格候选的最终选定（可含建议，但选择权在用户）"),
    ("form", "影片形态（纯视觉 / 主视觉+章节讲解 / …）"),
    ("voice", "配音方案 + 音色（edge / 火山，及具体音色 ID）"),
    ("duration_sec", "目标时长（秒）"),
    ("cover", "封面规格（16:9 / 3:4 / 9:16 各几张）"),
    ("render_channel", "渲染通道（png / png-fast / jpeg q95 / jpeg q82）—— 渲染前必须问，见 SKILL.md 确认点 5"),
]

# --phase render 只查这几项（其余早已在场景构建前定下）
RENDER_PHASE = ["render_channel"]

TEMPLATE = {
    "_note": "确认点的记录。choice 必须由用户给出；decided_by 只能是 'user'。缺任何一项 gate_check 会拒绝放行。",
    "theme": {"choice": "", "decided_by": "", "at": ""},
    "style": {"choice": "", "decided_by": "", "at": ""},
    "form": {"choice": "", "decided_by": "", "at": ""},
    "voice": {"choice": "", "decided_by": "", "at": ""},
    "duration_sec": {"choice": "", "decided_by": "", "at": ""},
    "cover": {"choice": "", "decided_by": "", "at": ""},
    "render_channel": {"choice": "", "decided_by": "", "at": ""},
}

# 渲染通道的候选（仅用于提示，选择权在用户）
CHANNEL_HINT = (
    "渲染通道候选（★推荐第 1 条）：jpeg q95（×13、体积 1/5 —— 失真低于成片自身编码失真，"
    "成片里不可观测）· png-fast（中间帧逐像素无损，×4.4，但慢 3×/占盘 8×，成片画质无可观测收益）"
    "· png（最慢，只在要逐位复现 1.4.x 老成片时选）· jpeg q82（×14，只适合打样）"
)


def _path(proj: str) -> str:
    return os.path.join(proj, "consent.json")


def cmd_init(proj: str) -> int:
    p = _path(proj)
    if os.path.exists(p):
        print(f"consent.json 已存在，未覆盖：{p}")
        return 0
    with open(p, "w", encoding="utf-8") as f:
        json.dump(TEMPLATE, f, ensure_ascii=False, indent=2)
    print(f"已生成确认模板：{p}")
    print("→ 请把每个 choice 与用户确认后填入，decided_by 写 'user'。")
    return 0


def cmd_show(proj: str) -> int:
    p = _path(proj)
    if not os.path.exists(p):
        print(f"缺 {p}")
        return 1
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    for key, label in REQUIRED:
        v = data.get(key, {})
        mark = "OK " if (v.get("choice") and v.get("decided_by") == "user") else "!! "
        print(f"[{mark}] {key:<14} {v.get('choice') or '(未确认)'}")
        print(f"        └ {label}")
    return 0


def cmd_check(proj: str, phase: str = "all") -> int:
    p = _path(proj)
    errs: list[str] = []

    if not os.path.exists(p):
        print(f"ERROR  缺确认记录 {p}")
        print("       先跑：python gate_check.py --project . --init")
        print("       再逐项与用户确认后填入（脚本不替你选）。")
        return 1

    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR  consent.json 解析失败：{e}")
        return 1

    keys = REQUIRED if phase == "all" else [r for r in REQUIRED if r[0] in RENDER_PHASE]

    for key, label in keys:
        item = data.get(key)
        if not isinstance(item, dict):
            errs.append(f"缺字段 {key}（{label}）")
            continue
        choice = str(item.get("choice", "")).strip()
        by = str(item.get("decided_by", "")).strip().lower()
        if not choice:
            errs.append(f"{key} 未做选择 —— {label}")
        elif by != "user":
            errs.append(
                f"{key} 的 decided_by='{item.get('decided_by')}'，必须是 'user' —— "
                f"{label}。把候选列给用户，拿到答复再改这一项。"
            )

    if data.get("_override") == "user-said-you-decide":
        print("NOTE   用户已明确授权 agent 决定（_override=user-said-you-decide），放行。")
        return 0

    if errs:
        print("确认闸门未通过（%d 项）：" % len(errs))
        for e in errs:
            print("  ERROR  " + e)
        if phase == "render":
            print("\n→ " + CHANNEL_HINT)
            print("→ 渲染前必须先问用户选通道（SKILL.md 确认点 5），不得用默认值静默开工。")
        else:
            print("\n→ 确认点必须由用户拍板；不得凭记忆或偏好替他选（SKILL.md 确认点 0）。")
        return 1

    scope = "渲染前确认项" if phase == "render" else "全部确认点"
    print(f"确认闸门通过：{scope}均已由用户拍板。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="确认点的硬闸门")
    ap.add_argument("--project", default=".")
    ap.add_argument("--phase", choices=["all", "render"], default="all",
                    help="all=全量确认点；render=只查渲染前必须拍板的项")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--init", action="store_true", help="生成 consent.json 模板")
    g.add_argument("--show", action="store_true", help="打印当前确认记录")
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    if args.init:
        return cmd_init(proj)
    if args.show:
        return cmd_show(proj)
    return cmd_check(proj, args.phase)


if __name__ == "__main__":
    sys.exit(main())
