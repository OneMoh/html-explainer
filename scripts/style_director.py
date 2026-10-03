#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""style_director.py —— 主题驱动的画面风格编排器（v2.0 新增）。

【它解决什么问题】
v1.4.x 的用法是「挑一个模板风格 → 整片都用它」。结果是：每期视频长得一样、开头永远一样、
模板在支配主题而不是主题在支配模板。23 个风格里只用 1 个，等于浪费了 22 个。

本脚本读**解说词本身**（不是让用户填表），推断每一场在片子里扮演什么角色、情绪多重、
节奏多快，然后：
  1. 给每一场**挑一个主风格**（primary）——按角色/时长/内容关键词打分，不按固定映射；
  2. opportunistically 给需要的场**搭一个次风格**（accent）做局部替换
     （例如主风格是瑞士网格，但中间那格大数字借 Pentagram Stat 的排版 DNA）；
  3. 决定**开场变体**（opener variant）——由主题哈希轮换，不是写死的那个；
  4. 决定**场间转场**（transition）——由相邻两场的能量差决定，不是全都淡入淡出；
  5. 决定**动效强度**（motion_intensity 0–1）——给渲染器与作者读，用于校准画面动势；
  6. 施加**多样性约束**：全片风格数有上限、连续同风格有上限、开场风格≠第二场风格。

【可配置】
  --styles auto|N        全片最多用几种风格（默认 auto = 按片长 3~4）
  --pin id=style         钉死某一场的风格（可重复；用户拍板时用）
  --mood  calm|neutral|high      覆盖情绪（默认从文本推断）
  --pace  slow|medium|fast       覆盖节奏
  --audience general|pro|youth   覆盖受众（影响风格池）
  --seed N               固定哈希种子（默认取 slug）
  --dry-run              只打印，不写盘

【产物】
  <project>/style-plan.json    给渲染器/作者读的机器可读计划
  <project>/script/style-plan.md  人类可读的分镜画面指引

用法：
  python scripts/style_director.py --project . [--styles 4] [--pin intro=frame-kinetic-type]
  python scripts/style_director.py --project . --mood high --pace fast
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(SKILL_ROOT, "references", "style-catalog.json")


# ───────────────────────────── 读入 ─────────────────────────────

def _load_json(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _num(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


# ───────────────────────── 角色 / 情绪 / 节奏推断 ─────────────────────────

# 角色 → 该角色「天生适合」的风格类别（按顺序：首选 / 次选 / 避免）
ROLE_CATEGORY_FIT = {
    "opener":     (("intro-outro", "marketing", "social-shorts"), ("presentation",), ("data-viz",)),
    "statement":  (("presentation",), ("explainer", "social-shorts"), ("data-viz", "product-demo")),
    "data":       (("data-viz",), ("explainer", "presentation"), ("intro-outro", "ambient", "product-demo")),
    "mechanism":  (("explainer",), ("data-viz", "presentation"), ("ambient", "social-shorts")),
    "evidence":   (("data-viz", "explainer"), ("presentation",), ("intro-outro", "marketing")),
    "contrast":   (("presentation", "social-shorts"), ("data-viz",), ("ambient",)),
    "conclusion": (("presentation", "explainer"), ("data-viz",), ("ambient", "social-shorts")),
    "outro":      (("intro-outro",), ("social-shorts", "presentation"), ("data-viz", "ambient", "product-demo")),
}

# 角色中文名（写 md 用）
ROLE_ZH = {
    "opener": "开场钩子", "statement": "陈述", "data": "数据", "mechanism": "原理解释",
    "evidence": "例证", "contrast": "转折/反差", "conclusion": "收束", "outro": "结尾落版",
}

# 「专用角色」：它的语义强绑定某个风格类别，跨类别替换会把意思讲歪 —— 多样性约束不许动它。
SPECIALIZED_ROLES = {"data", "mechanism", "evidence"}

# 子类别级适配（比类别更细一层）。category 太粗：presentation 一个类别下有
# statement-title / hero / editorial / corporate 等 11 个子类，讲数据用 hero 是错的。
SUB_FIT = {
    "opener":     (("hero", "statement-title", "title-card", "cinematic", "section-title"),),
    "statement":  (("statement-title", "hero", "editorial", "title-card"),),
    "data":       (("bar-chart", "stat-card", "editorial"),),
    "mechanism":  (("flowchart", "concept-diagram", "editorial", "corporate"),),
    "evidence":   (("bar-chart", "editorial", "flowchart"),),
    "contrast":   (("statement-title", "title-card", "portrait-bold", "text-card", "section-title"),),
    "conclusion": (("statement-title", "quote-card", "editorial", "corporate", "hero"),),
    "outro":      (("outro", "section-title", "statement-title"),),
}

# 关键词 → 角色线索（命中越多越倾向该角色）。全部小写比较。
ROLE_KEYWORDS = {
    "data": ["%", "％", "倍", "亿", "万", "百分之", "占比", "增长", "下降", "同比", "环比",
             "gdp", "cagr", "人均", "规模", "统计", "调查", "数据", "排名", "第一", "top",
             "亿元", "美元", "元", "万人", "指数", "较去年", "翻倍"],
    "mechanism": ["因为", "所以", "原理", "机制", "流程", "步骤", "如何", "怎么", "导致",
                  "原因", "本质", "逻辑", "取决于", "依靠", "通过", "从而", "进而", "一旦",
                  "条件下", "过程", "算法", "结构", "路径", "链路", "拆解"],
    "evidence": ["例如", "比如", "举例", "案例", "以…为例", "以此为例", "典型", "实测",
                 "试点", "样本", "先例", "反例", "案例中", "拿…来说"],
    "contrast": ["但是", "然而", "反而", "却", "并非", "不是", "相反", "对比", "另一方面",
                 "与其", "不如", "表面", "实际", "看似", "真正的", "误区", "恰恰"],
    "conclusion": ["总之", "综上", "所以说", "总体", "一句话", "归根", "结论", "核心是",
                   "关键在于", "回到", "落到实处", "说到底", "本质上是"],
    "outro": ["关注", "订阅", "点赞", "下期", "转发", "评论区", "我们下", "再见", "谢谢观看",
              "一起", "保持", "理性", "留个"],
}

# 高能量词 → 动效强度 / 情绪
ENERGY_HIGH = ["震惊", "巨大", "爆", "颠覆", "首次", "突破", "史上", "前所未有", "剧变",
               "狂", "急剧", "崩", "暴涨", "暴跌", "翻番", "创纪录", "重磅", "炸", "猛",
               "极致", "顶", "最", "全速", "极速", "血洗", "重塑"]
ENERGY_LOW = ["平稳", "温和", "缓慢", "逐步", "小幅", "微", "略", "维持", "常态", "平静",
              "悄然", "安静", "冷静", "稳健", "克制", "中性", "持平"]

# 受众 → 风格池加成
AUDIENCE_BOOST = {
    "pro":    {"presentation": 4, "data-viz": 4, "explainer": 3, "social-shorts": -6, "ambient": -2},
    "youth":  {"social-shorts": 6, "marketing": 4, "presentation": 1, "data-viz": -3, "ambient": -3},
    "general": {},
}


def _hits(text: str, words) -> int:
    return sum(1 for w in words if w in text)


def infer_role(idx: int, n: int, text: str) -> str:
    """按位置 + 文本线索定角色。位置是硬约束（第一场必是开场、最后一场必是结尾）。"""
    if idx == 0:
        # 第一场：除非它就是结尾，否则必然是开场钩子
        return "outro" if n == 1 else "opener"
    if idx == n - 1:
        # 末场：有 CTA 词才是「落版」，否则是「收束」。
        # ★ 不能只看长度 —— 30 字的一句结论也会被「短=落版」误判成 outro。
        cta = _hits(text, ROLE_KEYWORDS["outro"])
        conc = _hits(text, ROLE_KEYWORDS["conclusion"])
        if cta >= 1 and cta >= conc:
            return "outro"
        if len(text) < 24 and conc == 0:      # 极短的落版句（「我们下期见。」）
            return "outro"
        return "conclusion"
    # 中间场：数据 > 例证 > 原理 > 反差 > 收束 > 陈述（数据优先级最高，因为要选 data-viz）
    scores = {r: _hits(text, ws) for r, ws in ROLE_KEYWORDS.items()}
    scores["outro"] = 0          # 中间场不当落版
    scores["data"] *= 1.25       # 数据线索给点额外权重（风格差异最大）
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "statement"


def infer_energy(text: str, role: str, mood=None) -> float:
    """0（最静）~ 1（最烈）。角色给底，文本给增量。"""
    base = {"opener": 0.72, "statement": 0.5, "data": 0.52, "mechanism": 0.48,
            "evidence": 0.5, "contrast": 0.66, "conclusion": 0.42, "outro": 0.4}[role]
    hi = _hits(text, ENERGY_HIGH)
    lo = _hits(text, ENERGY_LOW)
    # 感叹号 / 破折号 / 短句排比也是能量信号
    hi += text.count("！") + text.count("!") + text.count("——")
    lo += text.count("。") // 3
    e = base + min(0.28, hi * 0.06) - min(0.22, lo * 0.05)
    e = max(0.05, min(1.0, e))
    # mood 是**整条曲线的抬/压**，不是把每一场都夹到同一个值 ——
    # 夹平会把「开场高、收束低」的呼吸感抹掉，全片变成一条直线。
    if mood == "high":
        e = e ** 0.72
    elif mood == "calm":
        e = e ** 1.55
    return round(max(0.05, min(1.0, e)), 3)


def infer_pace(n_chars: int, dur: float) -> str:
    """字/秒 → 节奏档。中文口播正常 4~6 字/秒。"""
    if dur <= 0:
        return "medium"
    cps = n_chars / dur
    if cps >= 6.2:
        return "fast"
    if cps <= 3.8:
        return "slow"
    return "medium"


# ───────────────────────── 打分 ─────────────────────────

def _style_pool(catalog):
    """过滤掉不适合当「单场景帧」的风格（整片级的 multi-scene 需要显式指定）。"""
    pool = []
    for e in catalog:
        e = dict(e)
        e["_dmin"] = _num(e.get("dmin"), 3.0)
        e["_dmax"] = _num(e.get("dmax"), 30.0)
        e["_rec"] = _num(e.get("recommended"), 0.0)
        e["_multi"] = bool(e.get("multi"))
        e["_engine"] = str(e.get("engine") or "")
        pool.append(e)
    return pool


def score_style(e, role, text, dur, audience, pace, mood):
    """给 (风格, 场景) 打一个可解释的分。每个加减项都记在 why 里。"""
    why = []
    sc = 0.0

    prefer, second, avoid = ROLE_CATEGORY_FIT[role]
    cat = e.get("category")
    if cat in prefer:
        sc += 42
        why.append(f"类别 {cat} 命中角色「{ROLE_ZH[role]}」首选")
    elif cat in second:
        sc += 18
        why.append(f"类别 {cat} 是角色「{ROLE_ZH[role]}」次选")
    elif cat in avoid:
        sc -= 28
        why.append(f"类别 {cat} 与角色「{ROLE_ZH[role]}」不搭")

    # best_for 关键词与文本重叠（英文 best_for 对中文解说词命中率低，但偶尔能命中英文术语）
    bf = " ".join(e.get("best_for") or []).lower()
    bf += " " + str(e.get("zh_description") or "")
    t = text.lower()
    ov = sum(1 for tok in re.split(r"[^a-z0-9\u4e00-\u9fff%]+", t)
             if len(tok) >= 2 and tok in bf)
    if ov:
        sc += min(16, ov * 5)
        why.append(f"内容词与风格适用面重叠 {ov} 处")

    # 子类别级适配（类别对了但子类不对，仍然会别扭：讲数据用 hero 就是错的）
    sub = str(e.get("subcategory") or "")
    subs = SUB_FIT.get(role, ((),))[0]
    if sub and sub in subs:
        sc += 14
        why.append(f"子类别 {sub} 命中角色「{ROLE_ZH[role]}」画面语法（+14）")
    elif sub and subs and sub not in subs:
        sc -= 9
        why.append(f"子类别 {sub} 不是角色「{ROLE_ZH[role]}」的常规语法（−9）")

    # 时长契合：风格声明的 [dmin, dmax] 是否覆盖本场时长
    dmin, dmax = e["_dmin"], e["_dmax"]
    if dmin <= dur <= dmax:
        sc += 13
        why.append(f"时长 {dur:.1f}s 落在风格区间 {dmin:.0f}–{dmax:.0f}s 内")
    else:
        d = dur - dmax if dur > dmax else dmin - dur
        pen = min(30.0, d * 4.0)
        sc -= pen
        why.append(f"时长 {dur:.1f}s 偏离风格区间 {dmin:.0f}–{dmax:.0f}s（−{pen:.0f}）")

    # 策展推荐度（目录的 recommended 字段 = 官方推荐时长/质量）
    sc += min(8.0, e["_rec"])
    if e["_rec"] >= 6:
        why.append(f"目录推荐度高（{e['_rec']:.0f}）")

    # 引擎：rich（hyperframes + 有 keyframes）改编成本低；remotion 系明确「不要搬代码」
    if e["_engine"] == "remotion":
        sc -= 12
        why.append("remotion 引擎：只取视觉 DNA，不搬代码（−12）")
    elif int(e.get("kf") or 0) > 0:
        sc += 4
        why.append("单文件 + CSS keyframes，改编成本低")

    # 整片级合成风格（multi）：它本身含多个 composition，单场只取其一 —— 轻罚，
    # 因为「取其一」常常正是我们要的（例如 Swiss Grid 的 corporate 版式）。
    if e["_multi"]:
        sc -= 4
        why.append("整片级合成风格，单场取其一个 composition（−4）")

    # 受众
    for k, v in AUDIENCE_BOOST.get(audience, {}).items():
        if cat == k:
            sc += v
            if v:
                why.append(f"受众「{audience}」对 {cat} 偏好 {v:+d}")

    # 节奏：快节奏偏好 kinectic/glitch/social，慢节奏偏好 ambient/minimal
    sid = e.get("id", "")
    fast_ok = any(k in sid + sub for k in ("kinetic", "glitch", "play-mode", "signal", "vignelli", "cursor"))
    calm_ok = any(k in sid + sub for k in ("minimal", "light-leak", "warm-grain", "organic", "swiss", "nyt"))
    if pace == "fast":
        sc += 7 if fast_ok else (-5 if calm_ok else 0)
        if fast_ok:
            why.append("快节奏 + 该风格偏动感")
    elif pace == "slow":
        sc += 7 if calm_ok else (-5 if fast_ok else 0)
        if calm_ok:
            why.append("慢节奏 + 该风格偏沉静")

    # 情绪：高能偏好烈，低能偏好静
    if mood == "high" and fast_ok:
        sc += 4
    if mood == "calm" and calm_ok:
        sc += 4

    return sc, why


# ───────────────────── 多样性与混用 ─────────────────────

def accent_candidates(pool, primary, role, dur, used_ok):
    """给一场挑「次风格」——只用来做局部替换（一个大数字 / 一条分隔线 / 一个统计块）。
    要求：与主风格不同类别（否则不构成混用），且它的子类别得是「能当局部元素」的那类。"""
    # 角色 → 局部队列用哪种局部元素最顺
    want_sub = {
        "data": ("bar-chart", "stat-card", "editorial"),
        "evidence": ("bar-chart", "stat-card", "editorial"),
        "conclusion": ("quote-card", "stat-card", "editorial"),
        "contrast": ("stat-card", "quote-card", "editorial", "concept-diagram"),
    }
    out = []
    for e in pool:
        if e["id"] == primary["id"]:
            continue
        if e.get("category") == primary.get("category"):
            continue
        prefer, second, avoid = ROLE_CATEGORY_FIT[role]
        if e.get("category") not in (prefer + second):
            continue
        if e["_multi"]:
            continue
        if e["id"] not in used_ok:
            continue
        sub = str(e.get("subcategory") or "")
        if sub not in want_sub.get(role, ()):
            continue
        out.append(e)
    return out


def pick_transition(prev_e, cur_e, prev_style, cur_style, is_last):
    """场间转场由能量差决定，而不是全片统一淡入淡出。"""
    if is_last:
        return "iris-out"
    if prev_style == cur_style:
        return "match-cut"           # 同风格相邻 → 匹配剪辑，省一次「重新起范」
    d = cur_e - prev_e
    if d >= 0.30:
        return "whip-pan"            # 能量上扬 → 甩镜
    if d >= 0.10:
        return "push-up"             # 温和上扬
    if d <= -0.30:
        return "dissolve-soft"       # 能量落回 → 柔化叠化，给观众喘口气
    if d <= -0.10:
        return "fade-through-black"
    return "cut"


OPENER_VARIANTS = [
    "kinetic-cascade",   # 逐字冲击下落
    "iris-reveal",       # 从一点张开
    "title-slam",        # 大字砸下 + 震屏
    "grid-unfold",       # 网格延展生长
    "light-leak-rise",   # 漏光升起
    "type-on",           # 打字机 + 光标
    "mask-wipe",         # 形状遮罩横扫
    "stack-drop",        # 分块堆叠落位
]


def pick_opener_variant(seed_text: str) -> str:
    h = hashlib.sha1(seed_text.encode("utf-8")).hexdigest()
    return OPENER_VARIANTS[int(h[:8], 16) % len(OPENER_VARIANTS)]


def diversify(assign, pool, max_styles, role_of, pin, used_ok, max_loss=10.0):
    """在满足多样性约束的前提下，把「同风格连排」和「风格太多」压下去。

    ★ 一条铁律：**风格替换只在同一类别内发生**。
      把「数据场」从 data-viz 换成 presentation 能让风格数达标，但会让这一场讲歪 ——
      这不是优化，是损伤。宁可超一个风格，也不做跨类别替换。

    约束（全部可解释）：
      C1 全片不同风格数 ≤ max_styles —— **软目标**：只在同类别内做合并；达不到就如实报出来
      C2 同一风格连续出现 ≤ 2 场（第 3 场必须换）
      C3 开场风格 ≠ 第二场风格
      C4 用户 --pin 是硬约束，永不被改
      C5 专用角色（data / mechanism / evidence）不被 C1 动
    """
    n = len(assign)
    changes = []

    def distinct():
        return {a["primary"] for a in assign if a["primary"]}

    cat_of = {e["id"]: e.get("category") for e in pool}

    # C1：风格太多 → 只在「同类别」内把某个单例风格并到该类别里已在用的风格上
    guard = 0
    while len(distinct()) > max_styles and guard < 200:
        guard += 1
        counts = {}
        for a in assign:
            if a["primary"]:
                counts[a["primary"]] = counts.get(a["primary"], 0) + 1
        used = distinct()

        # 每个「单例风格 + 非专用角色 + 未 pin」的场，找一个同类别、已在用的替代风格
        options = []
        for i, a in enumerate(assign):
            if not a["primary"] or a["id"] in pin:
                continue
            if role_of(a) in ("opener", "outro") or role_of(a) in SPECIALIZED_ROLES:
                continue
            if counts.get(a["primary"], 0) != 1:
                continue
            cur_cat = cat_of.get(a["primary"])
            # 同类别、且在别处已经用过的风格 —— 并过去不会新增类别数，才是有效合并
            best = None
            for sid, sc in a["_ranked"]:
                if sid == a["primary"] or cat_of.get(sid) != cur_cat:
                    continue
                if sid in used:
                    best = (sid, sc)
                    break
            if best:
                loss = a["_score"] - best[1]
                # 合并代价闸门：为一个风格数指标牺牲 10 分以上的画面契合度，不值。
                if loss <= max_loss:
                    options.append((i, best[0], best[1], loss))
        if not options:
            # 没有合法的同类合并（或合并代价过高）→ 停止，并把超出的风格数如实记下来
            changes.append(f"多样性：目标 ≤{max_styles} 种，实得 {len(distinct())} 种 —— "
                           f"再做合并要么跨类别（讲歪）、要么代价 >{max_loss:.0f} 分（不值），因此保留")
            break
        # 选「语义损失最小」的那个合并
        options.sort(key=lambda o: o[3])
        i, target, _, loss = options[0]
        old = assign[i]["primary"]
        assign[i]["primary"] = target
        assign[i]["_why"] = [f"多样性合并（同类 {cat_of.get(target)}）：{old} → {target}，"
                             f"评分仅降 {loss:.1f}"] + assign[i]["_why"]
        changes.append(f"多样性：{assign[i]['id']} 的 {old} → {target}（同类合并，评分 −{loss:.1f}）")

    # C2：连续同风格 ≥3 → 换掉中间那场（同样只在同类别内换）
    run = 1
    for i in range(1, n):
        if assign[i]["primary"] and assign[i]["primary"] == assign[i - 1]["primary"]:
            run += 1
        else:
            run = 1
        if run >= 3 and assign[i]["id"] not in pin:
            a = assign[i]
            cur_cat = cat_of.get(a["primary"])
            for sid, sc in a["_ranked"]:
                if sid != a["primary"] and cat_of.get(sid) == cur_cat:
                    changes.append(f"节奏：{a['id']} 的 {a['primary']} → {sid}（同类，打断 3 连同风格）")
                    a["primary"] = sid
                    break
            run = 1

    # C3：开场 ≠ 第二场（第二场在同类内换；同类换不动就保留，开场差异化比硬换更重要）
    if n >= 2 and assign[0]["primary"] and assign[0]["primary"] == assign[1]["primary"]:
        a = assign[1]
        if a["id"] not in pin:
            cur_cat = cat_of.get(a["primary"])
            for sid, sc in a["_ranked"]:
                if sid != assign[0]["primary"] and cat_of.get(sid) == cur_cat:
                    changes.append(f"开场差异化：{a['id']} 的 {a['primary']} → {sid}")
                    a["primary"] = sid
                    break

    return changes


# ───────────────────────── 主流程 ─────────────────────────

def build_plan(project, args):
    pj = _load_json(os.path.join(project, "project.json"), {}) or {}
    narr = _load_json(os.path.join(project, "narration.json"), []) or []
    layout = _load_json(os.path.join(project, "layout.json"), {}) or {}
    brief = _load_json(os.path.join(project, "brief.json"), {}) or {}
    catalog = _load_json(CATALOG, []) or []
    if not catalog:
        raise SystemExit(f"✗ 找不到风格目录：{CATALOG}")
    if not narr:
        raise SystemExit("✗ narration.json 为空 —— 先定稿解说词（每场一条 {{id, text}}）")

    order = pj.get("order") or [s["id"] for s in narr]
    by_id = {s["id"]: s for s in narr}
    scenes_in_order = [by_id[i] for i in order if i in by_id]
    if not scenes_in_order:
        raise SystemExit("✗ project.json.order 与 narration.json 的 id 对不上")

    mood = args.mood or brief.get("mood")
    audience = args.audience or brief.get("audience") or "general"
    pace_over = args.pace or brief.get("pace")
    seed_text = args.seed or (pj.get("slug") or "explainer") + "|" + str(brief.get("topic") or "")

    pool = _style_pool(catalog)
    used_ok = set(args.allow or [e["id"] for e in pool])   # --allow 可把候选池收窄

    # 场时长：优先 layout.json 的实测，否则按字数估（中文 ~4.8 字/秒 + 0.8s 尾）
    n = len(scenes_in_order)
    assign = []
    for idx, s in enumerate(scenes_in_order):
        text = str(s.get("text") or "").replace("|", "")
        dur = _num((layout.get(s["id"]) or {}).get("duration_sec"))
        if dur is None:
            dur = round(max(2.0, len(text) / 4.8 + 0.8), 2)
        role = infer_role(idx, n, text)
        energy = infer_energy(text, role, mood)
        pace = pace_over or infer_pace(len(text), dur)

        ranked = []
        for e in pool:
            if e["id"] not in used_ok:
                continue
            sc, why = score_style(e, role, text, dur, audience, pace, mood)
            ranked.append((e["id"], sc, why, e))
        ranked.sort(key=lambda x: -x[1])
        if not ranked:
            raise SystemExit("✗ 候选池为空（--allow 收得太窄？）")

        # ★ 容差带内按主题哈希轮换 —— 这是「同一题材不会每期长得一样」的机制。
        #   语义由评分保证（band 内的候选都是这一场讲得通的画面），
        #   在讲得通的几个里选哪个，交给主题哈希决定：换一期主题 = 换一套画面语法，
        #   但永远不跳出「这一场该有的画面语法」。
        band = args.band
        top = ranked[0][1]
        tied = [r for r in ranked if top - r[1] <= band]
        pick = tied[int(hashlib.sha1(f"{seed_text}|{s['id']}|primary".encode()).hexdigest()[:8], 16) % len(tied)]
        if len(tied) > 1:
            pick_why = [f"容差带内 {len(tied)} 个候选（≤{band:.0f} 分差），"
                        f"按主题哈希选中（同题材换期=换画面语法）"] + pick[2]
        else:
            pick_why = pick[2]

        assign.append({
            "id": s["id"], "role": role, "dur": dur, "energy": energy, "pace": pace,
            "text_head": text[:28],
            "primary": pick[0], "_ranked": [(r[0], r[1]) for r in ranked],
            "_why": pick_why, "_score": pick[1],
            "_tie_band": [r[0] for r in tied],
        })

    # --pin 硬约束
    pin = {}
    for spec in (args.pin or []):
        if "=" not in spec:
            raise SystemExit(f"✗ --pin 格式应为 id=style，收到 {spec!r}")
        k, v = spec.split("=", 1)
        if v not in {e["id"] for e in pool}:
            raise SystemExit(f"✗ --pin 的风格不存在：{v}")
        pin[k.strip()] = v.strip()
    for a in assign:
        if a["id"] in pin:
            a["primary"] = pin[a["id"]]
            a["_why"] = [f"用户 --pin 钉死为 {pin[a['id']]}"]

    # 多样性
    max_styles = args.styles if args.styles and args.styles > 0 else (
        4 if n <= 8 else (5 if n <= 14 else 6))
    max_styles = max(1, min(max_styles, n))
    changes = diversify(assign, pool, max_styles, lambda a: a["role"], pin, used_ok)

    # 混用（accent）—— 预算制：全片最多 ~1/4 的场带次风格。
    # 混用是「手艺」不是「堆料」：满片都是混搭会失焦，所以先算所有合格候选，
    # 再按动效强度取前 k 个。
    idx_by_id = {e["id"]: e for e in pool}
    accent_eligible = []
    for i, a in enumerate(assign):
        prim = idx_by_id[a["primary"]]
        if a["role"] not in ("data", "evidence", "conclusion", "contrast"):
            continue
        if prim.get("category") == "data-viz":
            continue          # 主风格本身就是数据语法，再叠一个数据次风格是冗余
        accent_eligible.append((a["energy"], i))
    accent_budget = max(1, n // 4) if n >= 4 else n
    accent_ids = {i for _, i in sorted(accent_eligible, reverse=True)[:accent_budget]}
    for i, a in enumerate(assign):
        prim = idx_by_id[a["primary"]]
        a["accent"] = None
        if i in accent_ids:
            cands = accent_candidates(pool, prim, a["role"], a["dur"], used_ok)
            if cands:
                cands.sort(key=lambda e: -e["_rec"])
                a["accent"] = cands[0]["id"]
                a["accent_use"] = _accent_use_for(cands[0])
        a["transition_out"] = pick_transition(
            assign[i - 1]["energy"] if i > 0 else a["energy"] - 0.1,
            a["energy"],
            assign[i - 1]["primary"] if i > 0 else None,
            a["primary"],
            is_last=(i == n - 1),
        )
        a["motion_intensity"] = a["energy"]

    opener_variant = pick_opener_variant(seed_text)

    styles_used = sorted({a["primary"] for a in assign})
    plan = {
        "version": "2.0",
        "generator": "style_director.py",
        "seed": seed_text,
        "brief": {"topic": brief.get("topic"), "mood": mood or "auto",
                  "pace": pace_over or "auto", "audience": audience,
                  "aspect": brief.get("aspect") or "16:9"},
        "global": {
            "distinct_styles": len(styles_used),
            "max_styles": max_styles,
            "styles": styles_used,
            "opener_variant": opener_variant,
            "diversity_notes": changes,
            "theme_hint": _theme_hint(styles_used, idx_by_id),
        },
        "scenes": [
            {
                "id": a["id"], "role": a["role"], "role_zh": ROLE_ZH[a["role"]],
                "duration_sec": a["dur"], "pace": a["pace"],
                "motion_intensity": a["motion_intensity"],
                "primary": a["primary"], "primary_name": idx_by_id[a["primary"]].get("name"),
                "accent": a["accent"],
                "accent_use": a.get("accent_use"),
                "transition_out": a["transition_out"],
                "engine": idx_by_id[a["primary"]].get("engine"),
                "colors": idx_by_id[a["primary"]].get("colors"),
                "why": a["_why"][:4],
                "text_head": a["text_head"],
            } for a in assign
        ],
    }
    # 扁平锚点：每场的动效强度（渲染器/作者按 id 直读）
    plan["_motion"] = {a["id"]: a["motion_intensity"] for a in assign}
    return plan, assign, idx_by_id


def _accent_use_for(e):
    sub = str(e.get("subcategory") or "")
    return {
        "bar-chart": "只用它的大数字排版与量化对比，图表本体仍用主风格",
        "stat-card": "只借它的单个巨型数字排版做局部强调块",
        "editorial": "只借它的图表/线型风格做一张插图",
        "concept-diagram": "只借它的节点-连线语言画一张示意图",
        "flowchart": "只借它的流程块与箭头语言",
        "quote-card": "只借它的一句引文排版",
    }.get(sub, "只借一个局部元素（数字/分隔线/标签）的排版 DNA，不要整屏套用")


def _theme_hint(styles_used, idx_by_id):
    """从入选风格里抽一个最高频的强调色，作为 theme.css 的建议 accent。
    这只是**建议** —— make_theme.py 仍按 --topic 决定最终配色，避免画面与配色打架。"""
    from collections import Counter
    c = Counter()
    for sid in styles_used:
        for hexc in str(idx_by_id[sid].get("colors") or "").split():
            if re.fullmatch(r"#[0-9A-Fa-f]{6}", hexc):
                c[hexc.upper()] += 1
    return {"accent_suggest": [h for h, _ in c.most_common(3)],
            "note": "建议值；主题配色仍由 make_theme.py --topic 决定"}


def render_md(plan, assign, idx_by_id):
    L = []
    L.append("# 分镜画面指引（style_director 生成）\n")
    b = plan["brief"]
    L.append(f"- 主题：{b.get('topic') or '（未填，见 brief.json）'}")
    L.append(f"- 情绪：{b.get('mood')} · 节奏：{b.get('pace')} · 受众：{b.get('audience')} · 画幅：{b.get('aspect')}")
    g = plan["global"]
    L.append(f"- 全片风格：{g['distinct_styles']} 种（上限 {g['max_styles']}）→ {', '.join(g['styles'])}")
    L.append(f"- 开场变体：**{g['opener_variant']}**（由主题哈希轮换，不是固定开场）")
    if g["diversity_notes"]:
        L.append("- 多样性调整：")
        for c in g["diversity_notes"]:
            L.append(f"  - {c}")
    L.append("\n## 每场画面\n")
    L.append("| # | 场 | 角色 | 时长 | 动效强度 | 主风格 | 次风格（局部） | 出场转场 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for i, s in enumerate(plan["scenes"], 1):
        acc = f"{s['accent']}" if s["accent"] else "—"
        L.append(f"| {i} | {s['id']} | {s['role_zh']} | {s['duration_sec']}s | "
                 f"{s['motion_intensity']:.2f} | `{s['primary']}` | {acc} | `{s['transition_out']}` |")
    L.append("\n<details><summary>为什么这么选（可解释）</summary>\n")
    for s in plan["scenes"]:
        L.append(f"**{s['id']}**（{s['role_zh']}｜{s['primary']}）")
        for w in s["why"]:
            L.append(f"- {w}")
        if s["accent"]:
            L.append(f"- 次风格用法：{s['accent_use']}")
        L.append("")
    L.append("</details>\n")
    L.append("## 怎么用这份计划")
    L.append("1. 每个场景一个 `frames/<id>.html`，按下表的**主风格**改编模板"
             "（改编细则见 `references/template-guide.md`）；")
    L.append("2. 有**次风格**的场，只在指定局部用它的排版 DNA（`accent_use` 那行），不要整屏套用；")
    L.append("3. 开场场用 `opener_variant` 指定的动效语法（见 `references/motion-library.md`）；")
    L.append("4. `motion_intensity` 是该场的动效强度（0–1）——按它校准画面动势的轻重；")
    L.append("5. 转场写在该场**画面尾部**（`transition_out`），渲染器靠帧序列呈现，不需要额外代码。")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="主题驱动的画面风格编排器")
    ap.add_argument("--project", default=".")
    ap.add_argument("--styles", type=int, default=0, help="全片最多几种风格（0=auto）")
    ap.add_argument("--band", type=float, default=5.0,
                    help="容差带：评分在最高分 band 分内的候选，按主题哈希轮换（0=永远取最高分）")
    ap.add_argument("--pin", action="append", default=[], help="id=style，钉死某场风格（可重复）")
    ap.add_argument("--allow", action="append", default=[], help="把候选池收窄到这些风格 id（可重复）")
    ap.add_argument("--mood", choices=["calm", "neutral", "high"], default=None)
    ap.add_argument("--pace", choices=["slow", "medium", "fast"], default=None)
    ap.add_argument("--audience", choices=["general", "pro", "youth"], default=None)
    ap.add_argument("--seed", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    project = os.path.abspath(a.project)
    plan, assign, idx_by_id = build_plan(project, a)
    md = render_md(plan, assign, idx_by_id)

    if a.dry_run:
        sys.stdout.write(md)
        return 0

    out_json = os.path.join(project, "style-plan.json")
    out_md = os.path.join(project, "script", "style-plan.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    with open(out_md, "w", encoding="utf-8", newline="\n") as f:
        f.write(md)

    g = plan["global"]
    print(f"✓ 风格计划：{out_json}")
    print(f"✓ 分镜指引：{out_md}")
    print(f"  {len(plan['scenes'])} 场 · {g['distinct_styles']} 种风格：{', '.join(g['styles'])}")
    print(f"  开场变体 {g['opener_variant']}（哈希轮换）")
    for s in plan["scenes"]:
        acc = f" +{s['accent']}" if s["accent"] else ""
        print(f"  · {s['id']:14} {s['role_zh']:6} {s['primary']}{acc}  [{s['transition_out']}]  k={s['motion_intensity']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
