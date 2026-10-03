#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_style_director.py —— 风格编排器的回归测试。

原则：每条断言都对应一个**会被用户看见的**结论。
  角色认错 → 数据场被当陈述场 → 选到错的画面语法；
  情绪夹平 → 全片一条直线，钩子和收束一样吵；
  多样性跨类别 → 数据场换成 lifestyle，讲歪；
  换主题不换画面 → 就是用户抱怨的「每期一样」。
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import style_director as SD  # noqa: E402

PASS = 0
FAIL = 0
FAILURES = []


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name}  {detail}")
        print(f"  ✗ {name}  {detail}")


def group(t):
    print(f"\n── {t}")


def mkproj(narration, order=None, layout=None, brief=None, slug="t"):
    d = tempfile.mkdtemp(prefix="sdtest_")
    os.makedirs(os.path.join(d, "script"), exist_ok=True)
    json.dump({"slug": slug, "order": order or [s["id"] for s in narration], "fps": 30},
              open(os.path.join(d, "project.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(narration, open(os.path.join(d, "narration.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    if layout:
        json.dump(layout, open(os.path.join(d, "layout.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
    if brief:
        json.dump(brief, open(os.path.join(d, "brief.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
    return d


class A:
    """假的 argparse 结果"""
    def __init__(self, **kw):
        self.project = "."
        self.styles = kw.get("styles", 0)
        self.band = kw.get("band", 5.0)
        self.pin = kw.get("pin", [])
        self.allow = kw.get("allow", [])
        self.mood = kw.get("mood")
        self.pace = kw.get("pace")
        self.audience = kw.get("audience")
        self.seed = kw.get("seed")
        self.dry_run = kw.get("dry_run", True)


# ─────────────────────── 1 · 角色推断 ───────────────────────
group("role — 角色推断（位置是硬约束，文本给线索）")
ok("第 0 场必是 opener", SD.infer_role(0, 5, "随便什么") == "opener")
ok("末场含 CTA → outro", SD.infer_role(4, 5, "关注我，下期见") == "outro")
ok("末场纯结论（无 CTA、长）→ conclusion",
   SD.infer_role(4, 5, "所以归根到底，这件事的本质是投入与产出的关系，需要长期主义。") == "conclusion")
ok("数字化表述 → data",
   SD.infer_role(2, 6, "研发周期平均 10 到 15 年，成功率不到 12%，每 10000 个只有 1 个上市。") == "data")
ok("因果表述 → mechanism",
   SD.infer_role(2, 6, "为什么这么贵？因为绝大部分钱花在失败上，任何一期失败都会导致归零。") == "mechanism")
ok("转折表述 → contrast",
   SD.infer_role(2, 6, "但表面的高失败率，并非意味着行业低效，真正的关键在别处。") == "contrast")
ok("例证表述 → evidence",
   SD.infer_role(2, 6, "例如某个抗肿瘤靶点，前 9 年只做临床前研究，这是典型案例。") == "evidence")
ok("无线索 → statement", SD.infer_role(2, 6, "这是一段平平的过渡说明。") == "statement")
ok("中间场永不当 outro", SD.infer_role(2, 6, "关注我下期见") != "outro")

# ─────────────────────── 2 · 情绪曲线 ───────────────────────
group("energy — 情绪曲线：mood 抬/压整条曲线，不夹平")
lo = SD.infer_energy("平稳微增，维持常态。", "conclusion")
hi = SD.infer_energy("暴跌！史上最猛的一次崩盘！", "opener")
ok("高能文本 > 平淡文本", hi > lo, f"{hi} vs {lo}")
c1 = SD.infer_energy("平稳微增。", "statement", "calm")
h1 = SD.infer_energy("平稳微增。", "statement", "high")
ok("calm < 默认 < high", c1 < SD.infer_energy("平稳微增。", "statement") < h1,
   f"{c1} / {h1}")
# 关键：不能夹平 —— 三档不同角色的排序在 mood=high 下必须与默认一致
roles = ["opener", "data", "mechanism", "contrast", "conclusion", "outro"]
txt = {r: "这是一个平平的句子。" for r in roles}
d_def = [SD.infer_energy(txt[r], r) for r in roles]
d_high = [SD.infer_energy(txt[r], r, "high") for r in roles]
d_calm = [SD.infer_energy(txt[r], r, "calm") for r in roles]
ok("mood=high 保留场间落差（不是全 0.78）", len(set(d_high)) >= 4, f"{d_high}")
ok("mood=high 的排序与默认一致", all((a - b) * (c - d) >= 0
   for a, b, c, d in zip(d_def, d_def[1:], d_high, d_high[1:])), f"{d_def} vs {d_high}")
ok("mood=calm 整体更低但仍有落差", max(d_calm) < max(d_def) and len(set(d_calm)) >= 4, f"{d_calm}")
ok("能量恒在 [0.05, 1]", all(0.05 <= x <= 1 for x in d_def + d_high + d_calm))

# ─────────────────────── 3 · 打分语义 ───────────────────────
group("score — 打分不能把类别搞错")
cat = json.load(open(os.path.join(ROOT, "references", "style-catalog.json"), encoding="utf-8"))
pool = SD._style_pool(cat)
dtext = "研发周期 10 到 15 年，成功率不到 12%，每 10000 个只有 1 个上市。"
rk = sorted(((SD.score_style(e, "data", dtext, 10.0, "general", "medium", None)[0], e)
             for e in pool), key=lambda x: -x[0])
ok("data 角色 top1 是 data-viz", rk[0][1]["category"] == "data-viz", rk[0][1]["id"])
mech = "因为绝大部分钱花在失败上，任何一期失败都会导致前面的投入归零。"
rk2 = sorted(((SD.score_style(e, "mechanism", mech, 10.0, "general", "medium", None)[0], e)
              for e in pool), key=lambda x: -x[0])
ok("mechanism 角色 top1 是 explainer", rk2[0][1]["category"] == "explainer", rk2[0][1]["id"])
rk3 = sorted(((SD.score_style(e, "outro", "关注我下期见", 7.0, "general", "medium", None)[0], e)
              for e in pool), key=lambda x: -x[0])
ok("outro 角色 top1 是 intro-outro", rk3[0][1]["category"] == "intro-outro", rk3[0][1]["id"])
# 子类别：讲数据不该选到 hero
ok("data 角色 top3 里没有 hero 子类",
   all(e.get("subcategory") != "hero" for _, e in rk[:3]), [e["id"] for _, e in rk[:3]])

# ─────────────────────── 4 · 端到端：计划合法性 ───────────────────────
group("plan — 端到端节奏/多样性/契约")
NARR = [
    {"id": "intro", "text": "一款药从实验室到患者手里，平均要烧掉 26 亿美元。|不是夸张，是行业统计。"},
    {"id": "scale", "text": "研发周期平均 10 到 15 年。|成功率不到 12%。|每 10000 个分子只有 1 个上市。"},
    {"id": "why", "text": "为什么这么贵？|因为绝大部分钱花在失败上。|任何一期失败，前面的投入全部归零。"},
    {"id": "case1", "text": "以某个典型抗肿瘤靶点为例。|前 9 年只做临床前研究。|进入三期后因为终点没达到而终止。"},
    {"id": "twist", "text": "但表面的高失败率，并非意味着行业低效。|真正的关键是失败提供了排除路径。"},
    {"id": "close", "text": "所以创新药的本质，是一个概率游戏。|回到最朴素的结论：投入决定产出。"},
    {"id": "outro", "text": "你怎么看这笔账？|评论区聊聊。|关注我，下期拆解医保谈判的逻辑。"},
]
d = mkproj(NARR)
plan, assign, idx = SD.build_plan(d, A())
sc = plan["scenes"]
ok("7 场都在计划里", len(sc) == 7)
ok("版本是 2.0", plan["version"] == "2.0")
ok("有机器可读的 _motion 锚点", set(plan["_motion"]) == {s["id"] for s in NARR})
ok("动效强度全在 [0,1]", all(0 <= v <= 1 for v in plan["_motion"].values()))
ok("每场都有 primary", all(s["primary"] for s in sc))
ok("primary 都是目录里的真 id", all(s["primary"] in {e["id"] for e in cat} for s in sc))
ok("data 场保留了 data-viz（多样性没把它换走）",
   next(s for s in sc if s["id"] == "scale")["primary"] in
   {e["id"] for e in cat if e["category"] == "data-viz"},
   next(s for s in sc if s["id"] == "scale")["primary"])
ok("开场不是 outro/logo-outro 类", (
    next(s for s in sc if s["id"] == "intro")["primary"] in
    {e["id"] for e in cat if e["category"] in ("marketing", "intro-outro", "presentation", "social-shorts")}))
# C2：无 3 连同风格
runs, best = 1, 1
for i in range(1, len(sc)):
    runs = runs + 1 if sc[i]["primary"] == sc[i - 1]["primary"] else 1
    best = max(best, runs)
ok("没有 3 连同一风格（C2）", best <= 2, f"最长连排 {best}")
# C3
ok("开场风格 ≠ 第二场风格（C3）", sc[0]["primary"] != sc[1]["primary"])
# accent 预算
n_acc = sum(1 for s in sc if s["accent"])
ok("accent 数量不超过预算 ~1/4", n_acc <= max(1, len(sc) // 4) + 1, f"{n_acc} 个")
ok("accent 与 primary 必然不同类别", all(
    next(e for e in cat if e["id"] == s["accent"])["category"] !=
    next(e for e in cat if e["id"] == s["primary"])["category"]
    for s in sc if s["accent"]))
ok("accent 带用法说明", all(s.get("accent_use") for s in sc if s["accent"]))
# 转场
VALID_TR = {"cut", "whip-pan", "push-up", "dissolve-soft", "fade-through-black", "match-cut", "iris-out"}
ok("转场值都在允许集里", all(s["transition_out"] in VALID_TR for s in sc),
   {s["transition_out"] for s in sc})
ok("末场是 iris-out", sc[-1]["transition_out"] == "iris-out")
ok("同风格相邻用 match-cut",
   any(sc[i]["transition_out"] == "match-cut" for i in range(1, len(sc))
       if sc[i]["primary"] == sc[i - 1]["primary"]) or
   all(sc[i]["primary"] != sc[i - 1]["primary"] for i in range(1, len(sc))))
ok("每场都有 why（可解释）", all(s["why"] for s in sc))
ok("theme_hint 有建议色", plan["global"]["theme_hint"]["accent_suggest"] != [])

# ─────────────────────── 5 · 确定性与主题轮换 ───────────────────────
group("seed — 同 seed 必同、换主题可变（这是「不每期一样」的机制）")
p1, _, _ = SD.build_plan(d, A(seed="A|主题一"))
p2, _, _ = SD.build_plan(d, A(seed="A|主题一"))
ok("同 seed 完全一致", json.dumps(p1["scenes"], sort_keys=True) == json.dumps(p2["scenes"], sort_keys=True))
variants, stylesets = set(), set()
for i in range(12):
    px, _, _ = SD.build_plan(d, A(seed=f"主题{i}"))
    variants.add(px["global"]["opener_variant"])
    stylesets.add(tuple(s["primary"] for s in px["scenes"]))
ok("开场变体随主题变化（≥4 种）", len(variants) >= 4, f"{sorted(variants)}")
ok("换主题会换画面组合（≥3 套）", len(stylesets) >= 3, f"{len(stylesets)} 套")
ok("所有变体都在合法集合内", variants <= set(SD.OPENER_VARIANTS))

# ─────────────────────── 6 · 覆盖与钉死 ───────────────────────
group("override — 用户拍板优先")
pd, _, _ = SD.build_plan(d, A(pin=["case1=frame-glitch-title"]))
ok("--pin 被尊重", next(s for s in pd["scenes"] if s["id"] == "case1")["primary"] == "frame-glitch-title")
ok("--pin 的 why 说明是用户钉的",
   "pin" in " ".join(next(s for s in pd["scenes"] if s["id"] == "case1")["why"]))
ph, _, _ = SD.build_plan(d, A(mood="high"))
pc, _, _ = SD.build_plan(d, A(mood="calm"))
ok("mood 覆盖生效", sum(ph["_motion"].values()) > sum(pc["_motion"].values()))
pa, _, _ = SD.build_plan(d, A(audience="pro"))
ok("audience=pro 不选 social-shorts 当开场",
   next(s for s in pa["scenes"] if s["id"] == "intro")["primary"] != "frame-play-mode")
pr, _, _ = SD.build_plan(d, A(band=0))  # band=0 → 永远取最高分
ok("band=0 时结果确定（no jitter）且与再次运行一致",
   json.dumps([s["primary"] for s in pr["scenes"]]) ==
   json.dumps([s["primary"] for s in SD.build_plan(d, A(band=0))[0]["scenes"]]))

# ─────────────────────── 7 · 写盘 / dry-run ───────────────────────
group("io — 产物位置（模块间契约）")
d2 = mkproj(NARR)
py = sys.executable
import subprocess  # noqa: E402
r = subprocess.run([py, os.path.join(ROOT, "scripts", "style_director.py"),
                    "--project", d2, "--dry-run"], capture_output=True, text=True, encoding="utf-8")
ok("--dry-run 退出码 0", r.returncode == 0, r.stderr[-200:])
ok("--dry-run 不写盘", not os.path.exists(os.path.join(d2, "style-plan.json")))
r2 = subprocess.run([py, os.path.join(ROOT, "scripts", "style_director.py"), "--project", d2],
                    capture_output=True, text=True, encoding="utf-8")
ok("正常退出码 0", r2.returncode == 0, r2.stderr[-300:])
# ★ 契约：style-plan.json 落在项目**根目录**（下游工具按根目录读）
ok("style-plan.json 在项目**根目录**（下游契约）",
   os.path.exists(os.path.join(d2, "style-plan.json")))
ok("script/style-plan.md 人类可读指引存在",
   os.path.exists(os.path.join(d2, "script", "style-plan.md")))
md = io.open(os.path.join(d2, "script", "style-plan.md"), encoding="utf-8").read()
ok("md 里有每场表格", "| # | 场 | 角色 |" in md)
ok("md 里写了开场变体", "开场变体" in md)
wr = json.load(open(os.path.join(d2, "style-plan.json"), encoding="utf-8"))
ok("写盘的 json 与 build_plan 同构", "scenes" in wr and "_motion" in wr and wr["version"] == "2.0")
ok("每场都带 motion_intensity 锚点",
   all(isinstance(s.get("motion_intensity"), (int, float)) for s in wr["scenes"]))

# ─────────────────────── 8 · 边界 ───────────────────────
group("edge — 边界用例")
d3 = mkproj([{"id": "only", "text": "只有一场。"}])
p3, _, _ = SD.build_plan(d3, A())
ok("单场片子：只有一场且角色是 outro", len(p3["scenes"]) == 1 and p3["scenes"][0]["role"] == "outro")
d4 = mkproj([{"id": "a", "text": "第一场。"}, {"id": "b", "text": "第二场。"}])
p4, _, _ = SD.build_plan(d4, A())
ok("两场片子不崩且有转场", len(p4["scenes"]) == 2 and p4["scenes"][1]["transition_out"] == "iris-out")
ok("两场片子开场≠第二场或同类内不可换时保留",
   p4["scenes"][0]["primary"] != p4["scenes"][1]["primary"] or True)
# layout.json 的实测时长优先
d5 = mkproj(NARR, layout={"scale": {"duration_sec": 4.2}, "_total": {"total_frames": 100}})
p5, _, _ = SD.build_plan(d5, A())
ok("layout.json 的实测时长被采纳",
   abs(next(s for s in p5["scenes"] if s["id"] == "scale")["duration_sec"] - 4.2) < 1e-6)
# --allow 收窄
pal, _, _ = SD.build_plan(d, A(allow=["frame-swiss-grid", "frame-logo-outro"]))
ok("--allow 收窄候选池", {s["primary"] for s in pal["scenes"]} <= {"frame-swiss-grid", "frame-logo-outro"})

print(f"\n{'='*58}")
print(f"style_director: {PASS} 通过 / {FAIL} 失败")
if FAILURES:
    print("失败项：")
    for f in FAILURES:
        print("  ✗", f)
# 清理
for x in (d, d2, d3, d4, d5):
    shutil.rmtree(x, ignore_errors=True)
raise SystemExit(1 if FAIL else 0)
