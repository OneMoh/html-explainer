#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
timeline_build.py —— 全局时间轴：layout.json + 拼接音轨。

做两件事：
  ① 按 project.json 的 order 把各段容器时长 + 段间 gap 排成全局时间轴
     → layout.json（每段 start_sec / duration_sec，渲染器与字幕都读它）
  ② 把逐段 MP3 用 ffmpeg concat + anullsrc 间隙拼成一条 narration-full.mp3
     （总长 = Σ容器时长 + gap×(n-1)，与视频帧数同口径 → 音画天然对齐）

用法：
  python timeline_build.py --project . [--gap 0.35]
产出：
  layout.json + audio/narration-full.mp3
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def ffmpeg_exe() -> str:
    from shutil import which
    p = which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_duration(path: str, ff: str) -> float:
    r = subprocess.run([ff, "-hide_banner", "-i", path],
                       capture_output=True, text=True, errors="replace")
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--gap", type=float, default=-1, help="段间静音秒（默认取 project.json 的 gap）")
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    pj = json.load(open(os.path.join(proj, "project.json"), encoding="utf-8"))
    order = pj.get("order") or []
    gap = args.gap if args.gap >= 0 else float(pj.get("gap", 0.35))

    man_path = os.path.join(proj, "audio-manifest.json")
    if not os.path.exists(man_path):
        print("✗ 先跑 tts_build.py（缺 audio-manifest.json）", file=sys.stderr)
        return 1
    man = json.load(open(man_path, encoding="utf-8"))
    by_id = {}
    for it in man.get("items", []):
        by_id[it.get("id") or os.path.splitext(os.path.basename(it["path"]))[0]] = it

    ff = ffmpeg_exe()
    layout, cursor, parts = {}, 0.0, []
    for nid in order:
        it = by_id.get(nid)
        if not it:
            print(f"✗ manifest 里没有 {nid}", file=sys.stderr)
            return 1
        dur = round(float(it.get("container_duration_sec") or it["duration_sec"]), 3)
        layout[nid] = {"start_sec": round(cursor, 3), "duration_sec": dur}
        parts.append(os.path.join(proj, "audio", f"{nid}.mp3"))
        cursor += dur + gap

    total = cursor - (gap if order else 0.0)

    # ---- 拼音轨：concat filter + anullsrc 间隙 ----
    inputs = []
    for p in parts:
        inputs += ["-i", p]
    n = len(parts)
    filters, labels = [], []
    for i in range(n):
        filters.append(f"[{i}:a]aresample=44100[a{i}]")
        labels.append(f"[a{i}]")
        if i < n - 1:
            inputs += ["-f", "lavfi", "-t", str(gap), "-i",
                       "anullsrc=channel_layout=mono:sample_rate=44100"]
            filters.append(f"[{n + i}:a]aresample=44100[g{i}]")
            labels.append(f"[g{i}]")
    fc = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"

    out = os.path.join(proj, "audio", "narration-full.mp3")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y",
           *inputs, "-filter_complex", fc, "-map", "[out]",
           "-c:a", "libmp3lame", "-b:a", "128k", out]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("✗ ffmpeg 拼接失败:\n" + (r.stderr or "")[-800:], file=sys.stderr)
        return 1

    audio_total = probe_duration(out, ff)
    layout["_total"] = {"audio_duration_sec": round(audio_total, 3),
                        "video_duration_sec": round(total, 3),
                        "gap_sec": gap, "fps": pj.get("fps", 30),
                        "total_frames": int(round(total * pj.get("fps", 30)))}
    lp = os.path.join(proj, "layout.json")
    json.dump(layout, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"[timeline] {len(order)} 段 · gap {gap}s · 视频 {total:.2f}s / "
          f"{int(round(total * pj.get('fps', 30)))} 帧 · 音轨 {audio_total:.2f}s → {lp}")
    drift = abs(audio_total - total)
    if drift > 0.5:
        print(f"  ⚠ 音轨与视频时长差 {drift:.2f}s（>0.5s，检查 gap 或音频）", file=sys.stderr)
    for nid in order:
        print(f"  {nid:<12} start {layout[nid]['start_sec']:>7.2f}s  dur {layout[nid]['duration_sec']:>6.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
