#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
qc_check.py —— 成片体检 + 抽帧速览图。

检查项（全部来自两个血统项目的实战教训）：
  ① 流：必须有 h264 video + aac audio 两条流
  ② 时长：成片 vs 音轨 vs layout.json 期望帧数 —— 差 >0.5s 判 FAIL
     （差 ~0.9s×N 段 = 帧时长用了词边界而非容器时长的典型症状）
  ③ 音量：成片 mean_volume 与源音轨差 >3dB 判 FAIL（静音轨/占位轨）
  ④ 抽帧：按字幕切换点 + 每场景中段抽帧，纯背景帧（体积过小）判 FAIL
     （1920×1080 纯背景 PNG ≈ 90KB 上下；有内容通常 220KB+）
  ⑤ 速览图：6 列 contact sheet → out/qc_sheet.jpg（肉眼过一遍字幕带/构图）

用法：
  python qc_check.py --project . [--samples 12]
产出：
  out/qc_report.md + out/qc_frames/*.jpg + out/qc_sheet.jpg
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


def probe(ff, path):
    """返回 (duration_sec, streams[], 容器行列表)。"""
    r = subprocess.run([ff, "-hide_banner", "-i", path],
                       capture_output=True, text=True, errors="replace")
    lines = r.stderr.splitlines()
    dur = 0.0
    for line in lines:
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            dur = int(h) * 3600 + int(m) * 60 + float(s)
    streams = [l.strip() for l in lines if "Stream #" in l]
    return dur, streams, lines


def mean_volume(ff, path):
    r = subprocess.run([ff, "-hide_banner", "-i", path, "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True, errors="replace")
    for line in r.stderr.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].replace("dB", "").strip())
    return None


def extract_frame(ff, video, sec, out_png):
    r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y",
                        "-i", video, "-ss", f"{sec:.3f}", "-frames:v", "1", out_png],
                       capture_output=True)
    return r.returncode == 0 and os.path.exists(out_png)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--samples", type=int, default=12)
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    pj = json.load(open(os.path.join(proj, "project.json"), encoding="utf-8"))
    slug = pj.get("slug") or "video"
    ff = ffmpeg_exe()
    video = os.path.join(proj, "out", f"{slug}.mp4")
    audio = os.path.join(proj, "audio", "narration-full.mp3")
    layout = os.path.join(proj, "layout.json")
    subs = os.path.join(proj, "subs.json")

    report, fails, warns = [], [], []

    def sec(title):
        report.append(f"\n## {title}\n")

    if not os.path.exists(video):
        print(f"✗ 找不到成片 {video}（先渲染）", file=sys.stderr)
        return 1

    # ① 流
    sec("流")
    vdur, streams, _ = probe(ff, video)
    has_v = any("Video:" in s and "h264" in s for s in streams)
    has_a = any("Audio:" in s and "aac" in s for s in streams)
    for s in streams:
        report.append(f"- `{s}`")
    (report if has_v else fails).append("✓ 视频流 h264" if has_v else "video 流缺失或非 h264")
    if not has_a:
        warns.append("无 aac 音轨（还没配音？）")
    report.append(f"- 成片时长 {vdur:.2f}s")

    # ② 时长对齐
    sec("时长对齐（两级时钟口径）")
    expect = None
    if os.path.exists(layout):
        lay = json.load(open(layout, encoding="utf-8"))
        expect = lay.get("_total", {})
        report.append(f"- layout 期望：视频 {expect.get('video_duration_sec')}s / "
                      f"{expect.get('total_frames')} 帧 · 音轨 {expect.get('audio_duration_sec')}s")
        d = abs(vdur - float(expect.get("video_duration_sec", vdur)))
        if d > 0.5:
            fails.append(f"成片与期望时长差 {d:.2f}s（>0.5s）—— 查帧时长口径是否用了容器时长")
        else:
            report.append(f"- ✓ 与期望差 {d:.2f}s")
    if os.path.exists(audio):
        adur, _, _ = probe(ff, audio)
        d = abs(vdur - adur)
        report.append(f"- 音轨 {adur:.2f}s，成片差 {d:.2f}s")
        if d > 0.5:
            fails.append(f"音画时长差 {d:.2f}s —— 典型原因：帧时长用了词边界时长（每段少 ~0.86s）")

    # ③ 音量
    sec("音量")
    if os.path.exists(audio):
        mv_v, mv_a = mean_volume(ff, video), mean_volume(ff, audio)
        report.append(f"- 成片 mean_volume {mv_v} dB · 源 {mv_a} dB")
        if mv_v is not None and mv_a is not None and abs(mv_v - mv_a) > 3:
            fails.append(f"音量差 {abs(mv_v - mv_a):.1f} dB（静音轨或占位轨？）")

    # ④ 抽帧（字幕切换点 + 场景中段）
    sec("抽帧体检")
    qc_dir = os.path.join(proj, "out", "qc_frames")
    os.makedirs(qc_dir, exist_ok=True)
    times = []
    if os.path.exists(subs):
        sd = json.load(open(subs, encoding="utf-8"))
        pts = sorted({round(b['global_start_sec'] + 0.25, 2)
                      for s in sd['segments'] for b in s['blocks']})
        # ★ 全片均匀取 N 个（不是前 N 个）：块数多于抽样数时按步长挑，
        #   否则 QC 只覆盖前 ~1/4 片，后半段场景（本例 world→outro）抽不到。
        #   见 lessons.md #29。
        if len(pts) > args.samples:
            step = len(pts) / args.samples
            pts = [pts[int(i * step)] for i in range(args.samples)]
        times = pts
    if not times:
        times = [round(vdur * (i + 1) / (args.samples + 1), 2) for i in range(args.samples)]

    sizes = []
    for i, t in enumerate(times):
        if t >= vdur - 0.1:
            continue
        p = os.path.join(qc_dir, f"q{i:02d}_{int(t * 1000):07d}ms.jpg")
        if extract_frame(ff, video, t, p):
            sz = os.path.getsize(p)
            sizes.append((t, sz, p))

    # 阈值必须随主题底色自适应：暗底主题压缩后体积天然很小，
    # 用固定 100KB 会把「黑底 + 稀疏文字」的合规画面全判成空画面（假阳性）。
    # 做法：取本片所有抽帧体积的中位数作参考，低于中位数 35% 的帧才是可疑帧。
    # 若全部帧都极暗（中位数本身就小），再叠加一个绝对下限兜底。
    if sizes:
        med = sorted(s for _, s, _ in sizes)[len(sizes) // 2]
        floor = max(12_000, int(med * 0.35))
        report.append(f"- 抽了 {len(sizes)} 帧 → out/qc_frames/"
                      f"（本片抽帧体积中位数 {med // 1024}KB，可疑线 {floor // 1024}KB）")
        for t, sz, _ in sizes:
            flag = "  ← 可疑" if sz < floor else ""
            report.append(f"  - {t:>6.2f}s  {sz // 1024:>4}KB{flag}")
            if sz < floor:
                warns.append(f"{t}s 抽帧 {sz // 1024}KB，低于本片中位数 {med // 1024}KB 的 35%"
                             f" —— 疑似空画面（主角没渲出来？核对 out/qc_frames/ 该帧）")
    else:
        report.append("- 未能抽到任何帧")

    # ⑤ contact sheet
    sec("速览图")
    sheet = os.path.join(proj, "out", "qc_sheet.jpg")
    try:
        from PIL import Image
        imgs = [(t, p) for t, _, p in sizes]
        if imgs:
            cols = 6
            rows = (len(imgs) + cols - 1) // cols
            tw, th = 480, 270
            sheet_im = Image.new("RGB", (cols * tw, rows * th), (16, 16, 16))
            for i, (t, p) in enumerate(imgs):
                im = Image.open(p).resize((tw, th))
                sheet_im.paste(im, ((i % cols) * tw, (i // cols) * th))
            sheet_im.save(sheet, quality=85)
            report.append(f"- out/qc_sheet.jpg（{rows}×{cols}，时间点见 qc_frames 文件名）")
    except Exception as e:
        warns.append(f"速览图失败：{e}")

    # 汇总
    head = [f"# QC 报告 · {slug}", f"成片：{video}", f"时长 {vdur:.2f}s"]
    rep = "\n".join(head + report)
    if fails:
        rep += "\n\n## FAIL\n" + "\n".join(f"- ✗ {f}" for f in fails)
    if warns:
        rep += "\n\n## WARN\n" + "\n".join(f"- ⚠ {w}" for w in warns)
    if not fails and not warns:
        rep += "\n\n## 结论：全部通过 ✓（速览图仍需肉眼过一遍字幕带与构图）"
    open(os.path.join(proj, "out", "qc_report.md"), "w", encoding="utf-8", newline="\n").write(rep)
    print(rep)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
