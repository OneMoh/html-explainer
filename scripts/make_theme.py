#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_theme.py —— 主题配色：预设四档 + 按主题词现推一套，写 theme.css。

【血统】配色语义与色值预设移植自 anything2explainer 的 theme.ts /
make_theme.py（violet/cyan/amber/mono 四档 + custom 生成器），输出从
TS 模块改成 **CSS 变量单文件**（theme.css）——HTML 场景一律
<link rel="stylesheet" href="../theme.css">，画面代码禁止写死色值，
换主题 = 重写这一个文件。

颜色即语义（全主题一致）：
  accent = 重点/我们的   signal = 指标/另一方   warn = 警示/错误
  ok = 正确   灰系 = 未激活（中性色不参与换肤）

三条硬约束（custom 生成时校验，不满足自动修）：
  ① accent 饱和度 > 0.25（柔光必须带色，灰光不算光）
  ② accent 与 signal/warn/ok 的色相距离 ≥ 60°（暖色主题用亮度分离兜底）
  ③ accent 亮度（0.299r+0.587g+0.114b）∈ (55, 175)

用法：
  python make_theme.py --project . --list                # 主题联想表 + 预设
  python make_theme.py --project . --preset amber        # 用预设
  python make_theme.py --project . --topic "医疗"        # 按主题推导（推荐）
  python make_theme.py --project . --hue 190 --name 深青 # 直接给色相
  python make_theme.py --project . --seed "#1FA8C9"      # 从色号反推
"""
from __future__ import annotations

import argparse
import json
import os
import re

# ---------------- 颜色数学（与 anything2explainer 同口径） ----------------


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def hsl_to_rgb(h, s, l):
    h = h % 360 / 360.0
    if s <= 0:
        v = int(round(l * 255))
        return (v, v, v)
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def ch(t):
        t = t % 1.0
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    return tuple(int(round(ch(h + o) * 255)) for o in (1 / 3, 0, -1 / 3))


def hex2rgb(h):
    h = h.lstrip('#')
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    n = int(h, 16)
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255)


def rgb2hex(rgb):
    return '#%02X%02X%02X' % tuple(clamp(int(round(c)), 0, 255) for c in rgb)


def lum255(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def sat_of(rgb):
    mx, mn = max(rgb), min(rgb)
    return (mx - mn) / mx if mx else 0.0


def hue_of(rgb):
    r, g, b = [c / 255 for c in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return 0.0
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return (h * 60) % 360


def hdist(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def fit_lum(rgb, lo=55, hi=175):
    l = lum255(rgb)
    if lo <= l <= hi:
        return rgb
    target = lo if l < lo else hi
    s = 1.0
    for _ in range(40):
        cand = hsl_to_rgb(hue_of(rgb), sat_of(rgb), target / 255.0 * s)
        if abs(lum255(cand) - target) < 2:
            return cand
        s *= 0.97
    return cand


# ---------------- 预设（色值移植自 anything2explainer theme.ts） ----------------
PRESETS = {
    'violet': {
        'label': '紫', 'fit': '科技 / AI / 互联网 / 数字产品',
        'bg0': '#000000', 'bg1': '#0E0A18', 'accent': '#6630F8',
        'accentLight': '#A175F1', 'accentDeep': '#5A3AD5', 'accentPale': '#E6DCFF',
        'signal': '#F05F41', 'warn': '#EC081F', 'ok': '#8FF740',
        'glitchA': '#D100D6', 'glitchB': '#58FFEE',
    },
    'cyan': {
        'label': '青蓝', 'fit': '医疗 / 生物 / 健康 / 临床 / 科研',
        'bg0': '#05090E', 'bg1': '#071118', 'accent': '#1FA8C9',
        'accentLight': '#6FD8EE', 'accentDeep': '#14708A', 'accentPale': '#DCF4FA',
        'signal': '#F0873F', 'warn': '#E5323C', 'ok': '#7FE05A',
        'glitchA': '#E0409B', 'glitchB': '#B9F26A',
    },
    'amber': {
        'label': '琥珀', 'fit': '能源 / 工业 / 金融 / 历史 / 财经',
        'bg0': '#0A0705', 'bg1': '#14100A', 'accent': '#E8912B',
        'accentLight': '#F5C46B', 'accentDeep': '#9A5A12', 'accentPale': '#FBEBD2',
        'signal': '#3E8FD8', 'warn': '#A31621', 'ok': '#6FCF5A',
        'glitchA': '#C2185B', 'glitchB': '#4FC3D9',
    },
    'mono': {
        'label': '素白', 'fit': '严肃议题 / 新闻调查 / 纪实',
        'bg0': '#000000', 'bg1': '#111111', 'accent': '#FFFFFF',
        'accentLight': '#E8E8E8', 'accentDeep': '#A0A0A1', 'accentPale': '#2A2A2A',
        'signal': '#E24B4A', 'warn': '#C81E1E', 'ok': '#6FCF5A',
        'glitchA': '#D100D6', 'glitchB': '#58FFEE',
    },
}

# 主题词 → 色相联想（anything2explainer 的 12 类对照表精简版）
TOPIC_HUES = [
    (('医疗', '医学', '药', '健康', '临床', '生物', '中医', '医院'), 195),
    (('能源', '工业', '制造', '机械', '电力', '钢铁'), 32),
    (('金融', '财经', '货币', '银行', '股市', '经济', '基金', '历史'), 42),
    (('航天', '太空', '宇宙', '天文', '物理'), 262),
    (('科技', 'AI', '人工智能', '互联网', '软件', '编程', '大模型', '数据'), 258),
    (('环保', '气候', '碳中和', '新能源', '生态'), 135),
    (('教育', '学习', '考试', '知识', '课程'), 215),
    (('心理', '情绪', '认知', '大脑', '神经'), 300),
    (('法律', '合规', '监管', '政策'), 220),
    (('农业', '食品', '餐饮', '烹饪'), 75),
    (('体育', '运动', '健身'), 15),
    (('艺术', '设计', '美学', '音乐'), 330),
]


def topic_to_hue(topic: str):
    for keys, hue in TOPIC_HUES:
        if any(k.lower() in topic.lower() for k in keys):
            return hue, ''.join(keys[:2])
    return None, None


def derive(hue: float, name: str = ''):
    """按色相推导全套槽位（含三条硬约束校验与修正）。

    语义槽位规则（对齐四档预设的手调规律）：
      signal = 指标/另一方 → 与 accent 相对温度：暖色主题给冷蓝，冷色主题给暖橙
      warn   = 警示/错误   → 恒定红系（与 accent 撞红时压暗做亮度分离）
      ok     = 正确        → 恒定绿系（与 accent 撞绿时偏移到黄绿/青绿）
    """
    notes = []
    accent = fit_lum(hsl_to_rgb(hue, 0.72, 0.55))
    if sat_of(accent) <= 0.25:
        notes.append(f'⚠ 饱和度 {sat_of(accent):.2f} ≤ 0.25，柔光判据会退化（mono 类主题属正常）')

    warm = hue < 100 or hue > 330          # 红/橙/黄域
    sig_hue = 210 if warm else 25          # signal 与 accent 相对温度
    signal = hsl_to_rgb(sig_hue, 0.62, 0.58)
    if hdist(hue, sig_hue) < 60:
        signal = hsl_to_rgb(sig_hue, 0.62, 0.82)
        notes.append('signal 与 accent 色相距离不足 → 亮度分离')

    warn_hue = 355
    if hdist(hue, warn_hue) < 60:
        warn = hsl_to_rgb(warn_hue, 0.78, 0.32)   # 撞红 → 压暗分离
        notes.append('warn 与 accent 撞红 → 深红亮度分离')
    else:
        warn = hsl_to_rgb(warn_hue, 0.80, 0.47)
    ok_hue = 110 if hdist(hue, 110) >= 60 else (145 if hdist(hue, 145) >= 60 else 80)
    ok = hsl_to_rgb(ok_hue, 0.60, 0.60)

    a = hex2rgb(rgb2hex(accent))
    pal = {
        'label': name or f'custom({int(hue)}°)', 'fit': f'按主题推导 · 色相 {int(hue)}°',
        'bg0': '#000000', 'bg1': rgb2hex(hsl_to_rgb(hue, 0.30, 0.055)),
        'accent': rgb2hex(a), 'accentLight': rgb2hex(hsl_to_rgb(hue, 0.62, 0.72)),
        'accentDeep': rgb2hex(hsl_to_rgb(hue, 0.68, 0.38)),
        'accentPale': rgb2hex(hsl_to_rgb(hue, 0.35, 0.90)),
        'signal': rgb2hex(signal), 'warn': rgb2hex(warn),
        'ok': rgb2hex(ok), 'glitchA': rgb2hex(hsl_to_rgb((hue + 80) % 360, 0.85, 0.58)),
        'glitchB': rgb2hex(hsl_to_rgb((hue + 180) % 360, 0.80, 0.62)),
    }
    return pal, notes


CSS_TMPL = """/* 自动生成（make_theme.py）—— 全片唯一色源，画面代码禁止写死色值。
 * 颜色即语义：accent=重点/我们的 · signal=指标/另一方 · warn=警示 · ok=正确
 * 灰系 = 未激活（不参与换肤）。换主题 = 重写本文件（make_theme.py --use）。
 * 主题：{label} · 适合：{fit} */
:root {{
  --bg-0: {bg0};
  --bg-1: {bg1};
  --bg-radial: radial-gradient(1000px 700px at 50% 44%, {accent_rgb_a14}, transparent 66%),
    linear-gradient(170deg, {bg1} 0%, {bg0} 58%, {bg1} 100%);
  --accent: {accent};
  --accent-light: {accentLight};
  --accent-deep: {accentDeep};
  --accent-pale: {accentPale};
  --accent-rgb: {accent_rgb};
  --accent-soft: rgba({accent_rgb}, .10);
  --accent-border: rgba({accent_rgb}, .55);
  --accent-glow: rgba({accent_rgb}, .55);
  --signal: {signal};
  --signal-rgb: {signal_rgb};
  --warn: {warn};
  --ok: {ok};
  --glitch-a: {glitchA};
  --glitch-b: {glitchB};
  --text: #FFFFFF;
  --text-dim: rgba(255,255,255,.55);
  --text-faint: rgba(255,255,255,.38);
  --line: rgba(255,255,255,.15);
  --line-soft: rgba(255,255,255,.08);
  --card-bg: rgba(255,255,255,.045);
  --grey: #A0A0A1;

  /* ── 亮底「编辑页」变量（NYT 风数据帧 / 样板墙 / 亮底章节卡用）──────────
   * 用法：亮底帧**必须自己铺 --paper 背景**（绝不能露出暗色幕底），
   * 文字一律用 --ink 系、描边用 --line-ink 系，强调色用 --accent-on-paper
   * （= accentDeep，保证亮底上的对比度）。暗底帧不要用这一组。 */
  --paper: #F7F5EE;
  --paper-2: #EAE5D9;
  --ink: #17140F;
  --ink-dim: rgba(23,20,15,.62);
  --ink-faint: rgba(23,20,15,.38);
  --line-ink: rgba(23,20,15,.18);
  --line-ink-soft: rgba(23,20,15,.09);
  --accent-on-paper: {accentDeep};
}}
"""


def write_css(pal, path):
    acc = hex2rgb(pal['accent'])
    sig = hex2rgb(pal['signal'])
    css = CSS_TMPL.format(
        label=pal['label'], fit=pal['fit'],
        bg0=pal['bg0'], bg1=pal['bg1'],
        accent=pal['accent'], accentLight=pal['accentLight'],
        accentDeep=pal['accentDeep'], accentPale=pal['accentPale'],
        accent_rgb=f"{acc[0]},{acc[1]},{acc[2]}",
        accent_rgb_a14=f"rgba({acc[0]},{acc[1]},{acc[2]},.14)",
        signal=pal['signal'], signal_rgb=f"{sig[0]},{sig[1]},{sig[2]}",
        warn=pal['warn'], ok=pal['ok'],
        glitchA=pal['glitchA'], glitchB=pal['glitchB'],
    )
    open(path, 'w', encoding='utf-8', newline='\n').write(css)


def main() -> int:
    ap = argparse.ArgumentParser(description="html-explainer 主题配色")
    ap.add_argument("--project", default=".")
    ap.add_argument("--preset", default="", help="violet / cyan / amber / mono")
    ap.add_argument("--topic", default="", help="按主题词推导（推荐）")
    ap.add_argument("--hue", type=float, default=-1)
    ap.add_argument("--seed", default="", help="从色号反推整套")
    ap.add_argument("--name", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--use", action="store_true", help="写 theme.css 并更新 project.json")
    args = ap.parse_args()

    if args.list or (not args.preset and not args.topic and args.hue < 0 and not args.seed):
        print("预设：")
        for k, v in PRESETS.items():
            print(f"  {k:<8} {v['label']}  —— {v['fit']}  accent {v['accent']}")
        print("\n主题联想表（--topic 命中即用）：")
        for keys, hue in TOPIC_HUES:
            print(f"  {hue:>4}°  {' / '.join(keys[:5])}")
        print("\n示例：--topic \"医疗\"  |  --hue 190 --name 深青  |  --seed \"#1FA8C9\"")
        return 0

    notes = []
    if args.preset:
        pal = PRESETS.get(args.preset)
        if not pal:
            print(f"✗ 没有预设 {args.preset}（可选：{', '.join(PRESETS)}）")
            return 1
    elif args.seed:
        hue = hue_of(hex2rgb(args.seed))
        pal, notes = derive(hue, args.name or f"seed {args.seed}")
    elif args.hue >= 0:
        pal, notes = derive(args.hue, args.name)
    else:
        hue, hit = topic_to_hue(args.topic)
        if hue is None:
            print(f"✗ 主题「{args.topic}」联想不到色相；用 --hue/--seed 直接给，或选预设")
            return 1
        pal, notes = derive(hue, args.name or args.topic)

    print(f"主题：{pal['label']}（accent {pal['accent']}，亮度 {lum255(hex2rgb(pal['accent'])):.0f}，"
          f"饱和度 {sat_of(hex2rgb(pal['accent'])):.2f}）")
    print(f"  signal {pal['signal']} · warn {pal['warn']} · ok {pal['ok']}")
    for n in notes:
        print(f"  {n}")

    if args.use:
        proj = os.path.abspath(args.project)
        css_path = os.path.join(proj, "theme.css")
        write_css(pal, css_path)
        pj_path = os.path.join(proj, "project.json")
        if os.path.exists(pj_path):
            pj = json.load(open(pj_path, encoding="utf-8"))
            pj["theme"] = pal['label']
            json.dump(pj, open(pj_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"✓ 写 {css_path}（project.json.theme = {pal['label']}）")
    else:
        print("（--use 才写盘）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
