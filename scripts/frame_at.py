#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
frame_at.py —— **定点排查**：把一个「第几分几秒出问题了」的口头反馈，
落到具体的「场景 / 帧 / 当刻字幕块 / 裁好的图」，交给带视觉能力的模型看。

这条流水线是**静默**失败的：一个坏掉的帧照样能产出一条看着挺像样的视频，
所以反馈能不能被精确定位，直接决定修复要不要重跑整片。本工具就是那个转接头。

用法：
  python scripts/frame_at.py --project . --at 1:23          # 1 分 23 秒
  python scripts/frame_at.py --project . --at 83.5          # 也认纯秒
  python scripts/frame_at.py --project . --at 0:14 --box 900,200,1900,900
  python scripts/frame_at.py --project . --list             # 先看全片时间表

产出（全部落在 out/probe/）：
  at_<标签>_full.png   整帧（缩到 1280 宽，视觉模型友好的尺寸）
  at_<标签>_band.png   底部 0–260px 禁区带 **1:1 原像素**（字幕压字/错位在这里最明显）
  at_<标签>_final.png  同一场景的**终态帧** —— 判「代码错」还是「动画时序错」的关键
  at_<标签>_box.png    可选 --box 指定区域，1:1 原像素（放大看某个图元）
  at_<标签>.md         上面这些的事实清单，可直接贴进 issue

★ 为什么必须同时给「当刻帧」和「终态帧」：
  · 终态对齐、中途错位  → 是**入场动画时序**问题（两个元素给了不同的 delay/ease）
  · 终态也错位          → 是**坐标基准**问题（两个元素各用各的 left/top）
  只报中途帧，这两种根因分不开，容易改错地方（见 lessons #76）。

帧从哪来：
  优先用 render/frames/f_<n>.png（渲染产物，无损）；
  帧目录已被清掉时，回退到从 out/<slug>.mp4 现场抽帧（会明说这是有损回退）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


# ── 每个项目的画布高度可能不同，但这两条带子是契约固定的（见 frame-contract.md） ──
PROGRESS_BAND_PX = 12      # 0–12px 进度条带
SUBTITLE_BAND = (80, 170)  # 80–170px 字幕带
SAFE_BOTTOM_PX = 176       # 内容必须收在 bottom ≥ 176px 之上（证据条所在高度）
BAND_CROP_HEIGHT = 260     # 反馈用截图：底部 0–260px 一次把这三条带都框进来


def ffmpeg_exe() -> str:
    from shutil import which
    p = which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def parse_at(text: str) -> float:
    """把 `1:23` / `1:23.5` / `83` / `83.5` 都解析成秒。"""
    t = text.strip()
    if ":" in t:
        parts = t.split(":")
        if len(parts) != 2:
            raise ValueError(f"看不懂的时间：{text!r}（支持 `分:秒` 或纯秒）")
        m, s = parts
        return int(m) * 60 + float(s)
    return float(t)


def fmt(t: float) -> str:
    m = int(t // 60)
    s = t - m * 60
    return f"{m}:{s:05.2f}"


def load_scenes(proj: str):
    """读 layout.json → [(id, start, dur, end)]，end 已吸收场景间 gap。

    渲染器给每个场景渲的是 `duration_sec + gap` 秒的帧
    （render_video.mjs：gfEnd = round((cursorSec + dur + gap) * fps)），
    所以场景之间的空档**属于前一个场景的帧范围**，不能当"无场景"丢掉。
    """
    path = os.path.join(proj, "layout.json")
    if not os.path.exists(path):
        raise SystemExit("✗ 找不到 layout.json —— 先跑 timeline_build.py")
    lay = json.load(open(path, encoding="utf-8"))
    rows = sorted(
        ((k, v["start_sec"], v["duration_sec"])
         for k, v in lay.items()
         if isinstance(v, dict) and "start_sec" in v),
        key=lambda x: x[1])
    out = []
    for i, (sid, start, dur) in enumerate(rows):
        nxt = rows[i + 1][1] if i + 1 < len(rows) else start + dur
        out.append((sid, start, dur, max(start + dur, nxt)))
    return out, lay.get("_total", {})


def active_block(segments, sid, t):
    """返回 (块序号 0基, 块文本, 该块全局起止)。找不到返回 (None, None, None)。"""
    for seg in segments:
        if seg.get("id") != sid:
            continue
        for i, b in enumerate(seg.get("blocks", [])):
            g0 = b.get("global_start_sec")
            g1 = b.get("global_end_sec")
            if g0 is None or g1 is None:
                continue
            if g0 <= t < g1:
                return i, b.get("text", ""), (g0, g1)
        # 落在块与块之间的静音缝里 → 给最后一块
        bs = seg.get("blocks") or []
        if bs:
            return len(bs) - 1, bs[-1].get("text", ""), (
                bs[-1].get("global_start_sec"), bs[-1].get("global_end_sec"))
    return None, None, None


def grab(n: int, frames_dir: str, ext_pref=("png", "jpg")):
    for ext in ext_pref:
        p = os.path.join(frames_dir, f"f_{n:06d}.{ext}")
        if os.path.exists(p):
            return p, None
    return None, f"render/frames/f_{n:06d}.png 不存在（帧目录被清过？）"


def cut(src_png: str, out_png: str, mode: str, size, ff=None, video=None, at=None, box=None):
    """裁图。mode: full | band | box。src_png 为 None 时从 video 抽。"""
    from PIL import Image

    if src_png:
        im = Image.open(src_png).convert("RGB")
    else:
        tmp = out_png + ".src.png"
        r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss",
                            f"{at:.3f}", "-i", video, "-frames:v", "1", tmp],
                           capture_output=True)
        if r.returncode != 0 or not os.path.exists(tmp):
            return False
        im = Image.open(tmp).convert("RGB")
        os.remove(tmp)

    W, H = im.size
    if mode == "band":
        top = max(0, H - BAND_CROP_HEIGHT)
        im.crop((0, top, W, H)).save(out_png)
    elif mode == "box":
        x0, y0, x1, y1 = box
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x1), min(H, y1)
        im.crop((x0, y0, x1, y1)).save(out_png)
    else:  # full
        im.resize((1280, max(1, round(H * 1280 / W))), Image.LANCZOS).save(out_png)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="把「几分几秒」定位到具体帧 + 裁图")
    ap.add_argument("--project", default=".")
    ap.add_argument("--at", help="时间点：`1:23` 或 `83.5`（秒）")
    ap.add_argument("--box", help="额外裁一块区域，格式 x0,y0,x1,y1（原像素）")
    ap.add_argument("--list", action="store_true", help="只打印全片场景时间表")
    ap.add_argument("--no-images", action="store_true", help="只出文字清单，不裁图")
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    pj = json.load(open(os.path.join(proj, "project.json"), encoding="utf-8"))
    fps = float(pj.get("fps") or 30)
    slug = pj.get("slug") or "video"
    frames_dir = os.path.join(proj, "render", "frames")
    video = os.path.join(proj, "out", f"{slug}.mp4")

    scenes, total = load_scenes(proj)
    tot_frames = int(total.get("total_frames") or 0)

    if args.list:
        print(f"全片 {len(scenes)} 个场景 · {total.get('video_duration_sec')}s · "
              f"{tot_frames} 帧 @{fps:g}fps\n")
        print(f"{'场景':<16}{'起':>9}{'止':>9}{'时长':>8}{'起帧':>8}{'止帧':>8}")
        for sid, s, d, e in scenes:
            # ★ 帧号口径必须和渲染器一致：gf = round(cursorSec * fps)，
            #   场景帧范围 = [gf+1, gfEnd]，所以起帧用 round 而不是 int
            #   （用 int 会在 30fps 下每幕错开 1 帧，正好是最难发现的那种偏差）。
            print(f"{sid:<16}{fmt(s):>9}{fmt(e):>9}{d:>7.2f}s"
                  f"{round(s * fps) + 1:>8}{max(1, round(e * fps)):>8}")
        return 0

    if not args.at:
        print("✗ 需要 --at（如 `--at 1:23`）或 --list", file=sys.stderr)
        return 2
    t = parse_at(args.at)
    if t < 0:
        print("✗ 时间不能是负数", file=sys.stderr)
        return 2

    hit = None
    for sid, s, d, e in scenes:
        if s <= t < e:
            hit = (sid, s, d, e)
            break
    if hit is None:
        print(f"✗ {fmt(t)} 超出全片长度（{fmt(scenes[-1][3])}）", file=sys.stderr)
        return 2
    sid, s, d, e = hit

    n = max(1, min(round(t * fps) + 1, tot_frames or 10 ** 9))
    n_final = max(1, min(round(e * fps), tot_frames or 10 ** 9))
    src, miss = grab(n, frames_dir)
    src_final, _ = grab(n_final, frames_dir)
    falling_back = src is None and os.path.exists(video)
    ff = ffmpeg_exe() if (falling_back or args.box or not args.no_images) else None

    segs = []
    sp = os.path.join(proj, "subs.json")
    if os.path.exists(sp):
        segs = json.load(open(sp, encoding="utf-8")).get("segments", [])
    bi, btext, bspan = active_block(segs, sid, t)

    tag = args.at.replace(":", "-").replace(".", "_")
    probe_dir = os.path.join(proj, "out", "probe")
    os.makedirs(probe_dir, exist_ok=True)

    # ── 文字清单 ──────────────────────────────────────────────
    L = []
    L.append(f"# 定点排查 · {fmt(t)}\n")
    if t >= e:
        L.append(f"> 注意：{fmt(t)} 落在场景 {sid} 的**空档区**里（场景语声止于 {fmt(s + d)}），"
                 f"这段是场景间 gap，画面仍属 {sid} 的帧范围。\n")
    L.append(f"- **时间**：{fmt(t)}（{t:.2f}s）")
    L.append(f"- **场景**：`{sid}` · 场景内 {t - s:.2f}s / 共 {d:.2f}s")
    if bi is not None:
        L.append(f"- **当刻字幕块**：第 {bi + 1} 块 `{btext}`"
                 f"（{fmt(bspan[0])}–{fmt(bspan[1])}）→ 对应代码里的 "
                 f"`B('{btext}')`")
    L.append(f"- **帧号**：{n}" + (f" · 场景终态帧 {n_final}" if n_final != n else ""))
    L.append(f"- **场景源文件**：`frames/{sid}.html`"
             + (f" · 节拍 `frames/{sid}.beats.js`" if os.path.exists(
                 os.path.join(proj, "frames", f"{sid}.beats.js")) else ""))
    L.append("")
    L.append("## 判据：先看终态，再看中途\n")
    L.append(f"- **{fmt(t)} 的当刻帧**：入场动画可能还没走完，元素位置**本来就该**和终态不同，"
             f"单看它分不清是代码错还是动画错。")
    L.append(f"- **场景终态帧（{fmt(e)}）**：这才是「代码写对没有」的判据 —— "
             f"终态对齐/不遮挡 = 只是动画时序问题；终态也错 = 是布局本身。")
    L.append("")
    L.append("## 契约对照（frame-contract.md）\n")
    L.append(f"- 内容必须收在 `bottom ≥ {SAFE_BOTTOM_PX}px` 之上；"
             f"字幕带 {SUBTITLE_BAND[0]}–{SUBTITLE_BAND[1]}px 与进度条带 "
             f"0–{PROGRESS_BAND_PX}px 都是禁区。")
    L.append(f"- 底部 {BAND_CROP_HEIGHT}px 的裁图（`*_band.png`）就是拿来看这条的："
             f"里面只该有字幕和进度条，**不该有任何画面元素**。")
    L.append("")

    if not args.no_images:
        imgs = []
        full = os.path.join(probe_dir, f"at_{tag}_full.png")
        if cut(src, full, "full", None, ff, video, t):
            imgs.append(("整帧（缩到 1280 宽）", full))
        band = os.path.join(probe_dir, f"at_{tag}_band.png")
        if cut(src, band, "band", None, ff, video, t):
            imgs.append((f"底部 0–{BAND_CROP_HEIGHT}px 禁区带（1:1 原像素）", band))
        if src_final:
            fin = os.path.join(probe_dir, f"at_{tag}_final.png")
            if cut(src_final, fin, "full", None, ff, video, e):
                imgs.append((f"场景终态帧（{fmt(e)}）", fin))
        if args.box:
            try:
                box = tuple(int(x) for x in args.box.split(","))
                assert len(box) == 4
            except Exception:
                print("✗ --box 需要 4 个整数：x0,y0,x1,y1", file=sys.stderr)
                return 2
            bx = os.path.join(probe_dir, f"at_{tag}_box.png")
            if cut(src, bx, "box", None, ff, video, t, box):
                imgs.append((f"指定区域 {box}（1:1 原像素）", bx))
        if imgs:
            L.append("## 裁图\n")
            for label, p in imgs:
                L.append(f"- {label} → `{os.path.relpath(p, proj).replace(os.sep, '/')}`")
            L.append("")
        if falling_back:
            L.append("> ⚠ 帧目录里没有这一帧，裁图是**从成片 mp4 现场抽的**（有损）。"
                     "想要无损帧就重渲一次（`render_video.mjs` 默认保留帧）。\n")
    elif miss:
        L.append(f"> ⚠ {miss}\n")

    md = os.path.join(probe_dir, f"at_{tag}.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"清单 → {os.path.relpath(md, proj).replace(os.sep, '/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
