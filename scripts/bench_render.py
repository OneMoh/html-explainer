#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bench_render.py —— 渲染管线基准测试工装。

【为什么要它】
「优化了多少」不能靠感觉。这个脚本先合成一个**复杂度可控**的项目（N 场 × M 个动元素），
然后在同一台机器上用不同档位各渲一遍，把「截图耗时 / 帧率 / 成片体积」拉成一张表。
优化前（--profile legacy = 1.4.x 行为）与优化后（draft/balanced/final）就在同一张表里。

【合成项目长什么样】
  每场一帧 HTML，含：GSAP 时间轴（平移+旋转+缩放）、CSS @keyframes、逐帧 onUpdate 计数器、
  一个 window.__motion(t0,t1)（告诉渲染器快门开合期间屏幕最远移动了多少 px）。
  --heavy 打开「满幅渐变 + 多重 shadow + 半透明叠加」，用于模拟高熵帧（照片/复杂合成），
  这是 PNG 截图最慢的场景 —— 也是 --png-fast / --jpeg 收益最大的场景。

【怎么读结果】
  fps  = 渲染帧数 / 截图耗时（不含编码、不含积分）
  相对 legacy 的加速比才是重点；绝对值随机器和帧内容变化很大。

用法：
  python scripts/bench_render.py --out .scratch/bench [--scenes 6] [--sec 2.0]
      [--configs legacy,draft,balanced,shutter,4k30,4k60] [--preview 4]
      [--heavy] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))


def node_exe():
    if os.environ.get("NODE_BIN"):
        return os.environ["NODE_BIN"]
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    cands = []
    if home:
        base = os.path.join(home, ".workbuddy", "binaries", "node", "versions")
        if os.path.isdir(base):
            for d in sorted(os.listdir(base), reverse=True):
                p = os.path.join(base, d, "node.exe" if os.name == "nt" else "bin/node")
                if os.path.exists(p):
                    cands.append(p)
    return (cands + ["node"])[0]


FRAME = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<style>
  html,body{{margin:0;padding:0;overflow:hidden;background:#0b0b12;
    font-family:'Microsoft YaHei','PingFang SC',sans-serif;}}
  .stage{{position:absolute;inset:0;{bg}}}
  .card{{position:absolute;left:120px;top:180px;width:1200px;color:#fff;
    {cardextra}}}
  h1{{font-size:96px;margin:0 0 20px;letter-spacing:-2px;}}
  .sub{{font-size:34px;opacity:.82;}}
  .bars{{position:absolute;left:120px;bottom:200px;display:flex;gap:18px;align-items:flex-end;}}
  .bar{{width:{barw}px;background:linear-gradient(180deg,#ff5f6d,#ffc371);border-radius:6px;}}
  .num{{position:absolute;right:140px;top:150px;font-size:220px;font-weight:800;
    color:rgba(255,255,255,.92);}}
  @keyframes spinpulse {{ from{{transform:rotate(0) scale(1)}} to{{transform:rotate(360deg) scale(1.06)}} }}
  .orb{{position:absolute;right:320px;bottom:300px;width:200px;height:200px;border-radius:50%;
    background:radial-gradient(circle at 35% 30%,#a78bfa,#4c1d95);
    animation:spinpulse {orbs} linear infinite;{orbextra}}}
</style></head>
<body>
<div class="stage"></div>
<div class="card"><h1 id="t">场景 {i}</h1><div class="sub">deterministic frame · bench</div></div>
<div class="num" id="num">0</div>
<div class="orb"></div>
<div class="bars">{bars}</div>
<script src="../assets/gsap.min.js"></script>
<script>
  var tl = gsap.timeline({{ paused: true }});
  tl.to('#t', {{ x: {dx}, rotation: {rot}, scale: 1.18, duration: {dur}, ease: 'power2.inOut' }}, 0);
  tl.from('.bar', {{ scaleY: 0, transformOrigin: 'bottom', stagger: 0.08, duration: {dur0} }}, 0);
  tl.to('.orb', {{ x: -{dx2}, y: -80, duration: {dur} }}, 0);
  var numEl = document.getElementById('num');
  var obj = {{ v: 0 }};
  // onUpdate 写 DOM：这是 seek(t, false) 那个坑的现场 —— 若渲染器掐掉回调，数字会永远停在 0
  tl.to(obj, {{ v: {numv}, duration: {dur}, ease: 'none',
      onUpdate: function () {{ numEl.textContent = Math.round(obj.v); }} }}, 0);
  window.__tl = tl;
  // 快门自适应采样用：报告 t0..t1 之间屏幕最远位移（px）
  window.__motion = function (t0, t1) {{
    var d = Math.min(1, Math.abs(t1 - t0) / {dur});
    return {motion} * d;
  }};
  window.__SEG__ = {{ id: 's{i}', duration: {dur}, speech_end: {dur0}, tail: 0 }};
</script>
</body></html>
"""


def make_project(out, n_scenes, sec, heavy, fps, w, h):
    # ★ 不删除已有目录：沙箱/OS 对「批量删除」有保护，而且删掉上一次的基准数据也没好处。
    #   目录已存在且非空时，自动加 -2 / -3 … 后缀，每次都留一份可比对的现场。
    base = out
    k = 1
    while os.path.isdir(out) and os.listdir(out):
        if not os.path.exists(os.path.join(out, "project.json")):
            break            # 是别人的目录，别往里写
        k += 1
        out = f"{base}-{k}"
    for d in ("frames", "assets", "audio", "render", "out", "script"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    # 只清掉本次要重写的两类产物（逐文件删，不做递归批量删除）
    for sub in ("render/frames", "render/shutter", "out"):
        p = os.path.join(out, sub)
        if os.path.isdir(p):
            for name in os.listdir(p):
                q = os.path.join(p, name)
                try:
                    if os.path.isfile(q):
                        os.remove(q)
                    elif os.path.isdir(q):
                        shutil.rmtree(q, ignore_errors=True)
                except OSError:
                    pass
    shutil.copy(os.path.join(SKILL_ROOT, "assets", "gsap.min.js"),
                os.path.join(out, "assets", "gsap.min.js"))

    dur0 = max(0.5, sec * 0.55)
    layout = {"_total": {"total_frames": int(round(sec * n_scenes * fps))}}
    subs = {"fps": fps, "segments": []}
    order = []
    for i in range(1, n_scenes + 1):
        sid = f"s{i}"
        order.append(sid)
        h1 = {
            "bg": ("background:linear-gradient(135deg,#1e1b4b,#4c1d95 40%,#be123c);"
                   if i % 2 else "background:linear-gradient(135deg,#052e16,#065f46 45%,#0e7490);"),
            "cardextra": "text-shadow:0 12px 40px rgba(0,0,0,.55);" if heavy else "",
            "orbextra": "box-shadow:0 0 120px 40px rgba(167,139,250,.45);" if heavy else "",
            "barw": 70 + (i * 7) % 40,
            "bars": "".join(f'<div class="bar" style="height:{120 + ((i*53 + k*97) % 420)}px"></div>'
                            for k in range(5 if heavy else 3)),
            "i": i,
            "dx": 380 + i * 12,
            "dx2": 220 + i * 9,
            "rot": 8 + i,
            "dur": sec,
            "dur0": sec * 0.8,
            "numv": 1200 + i * 137,
            "motion": 300 + i * 20,
            "orbs": f"{sec * 0.6:.2f}s",
        }
        open(os.path.join(out, "frames", f"{sid}.html"), "w", encoding="utf-8", newline="\n"
             ).write(FRAME.format(**h1))
        layout[sid] = {"duration_sec": sec}
        subs["segments"].append({"id": sid, "blocks": [
            {"from": int(0.15 * fps), "to": int(0.55 * fps * sec / 2), "text": f"第{i}场的第一个字幕块"},
            {"from": int(0.6 * fps * sec / 2), "to": int(0.9 * fps * sec), "text": "第二个块"},
        ]})
    json.dump({"slug": "bench", "lang": "zh", "fps": fps, "width": w, "height": h,
               "gap": 0.0, "order": order, "progress": True},
              open(os.path.join(out, "project.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(layout, open(os.path.join(out, "layout.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(subs, open(os.path.join(out, "subs.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return out, n_scenes * sec


CONFIGS = {
    "legacy":   ["--profile", "legacy"],
    "draft":    ["--profile", "draft"],
    "balanced": ["--profile", "balanced"],
    "shutter":  ["--profile", "balanced", "--shutter", "180"],
    "4k30":     ["--quality", "4k", "--fps", "30", "--shutter", "180", "--workers", "8"],
    "4k60":     ["--quality", "4k", "--fps", "60", "--shutter", "180", "--workers", "8"],
    "master":   ["--profile", "master"],
}


def run_cfg(out, name, extra, preview, keep_frames, total_sec, quiet=True):
    node = node_exe()
    cmd = [node, os.path.join(HERE, "render_video.mjs"), out] + extra
    if preview:
        cmd += ["--preview", str(preview)]
    if keep_frames:
        cmd += ["--keep-frames"]
    cmd += ["--out", os.path.join("out", f"{name}.mp4")]

    # ★ 档位若覆盖了 fps，声明的总帧数（layout._total.total_frames）也得跟着变。
    #   渲染器**采信声明帧数**（这是有意的：避免帧数分歧导致 QC 假截断），所以只改 --fps
    #   而不改声明值，会让 4k60 这种档位按旧 fps 的帧数渲染 —— 时长少一半，基准就不可比了。
    layout_p = os.path.join(out, "layout.json")
    orig_layout = open(layout_p, encoding="utf-8").read() if os.path.exists(layout_p) else None
    eff_fps = None
    if "--fps" in extra:
        try:
            eff_fps = float(extra[extra.index("--fps") + 1])
        except (ValueError, IndexError):
            eff_fps = None
    try:
        if eff_fps and orig_layout is not None and not preview:
            lay = json.loads(orig_layout)
            lay.setdefault("_total", {})["total_frames"] = int(round(total_sec * eff_fps))
            json.dump(lay, open(layout_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        wall = time.time() - t0
    finally:
        if orig_layout is not None:
            open(layout_p, "w", encoding="utf-8").write(orig_layout)

    meta_p = os.path.join(out, "out", f"{name}.render.json")
    meta = json.load(open(meta_p, encoding="utf-8")) if os.path.exists(meta_p) else None
    mp4 = os.path.join(out, "out", f"{name}.mp4")
    size = os.path.getsize(mp4) if os.path.exists(mp4) else None
    return {
        "config": name, "ok": r.returncode == 0, "wall_sec": round(wall, 2),
        "capture_sec": (meta or {}).get("seconds", {}).get("capture"),
        "integrate_sec": (meta or {}).get("seconds", {}).get("integrate"),
        "frames": (meta or {}).get("frames"),
        "size_mb": round(size / 1048576, 2) if size else None,
        "size": (meta or {}).get("size"), "fps_out": (meta or {}).get("fps"),
        "shot_mode": (meta or {}).get("shot_mode"), "parallel": (meta or {}).get("parallel"),
        "workers": (meta or {}).get("workers"), "shutter": (meta or {}).get("shutter"),
        "still_frames": (meta or {}).get("still_frames"),
        "log_tail": r.stderr.strip().splitlines()[-3:] if r.returncode else [],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".scratch/bench")
    ap.add_argument("--scenes", type=int, default=6)
    ap.add_argument("--sec", type=float, default=2.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--preview", type=float, default=0.0, help="只渲前 N 秒（0=全片）")
    ap.add_argument("--configs", default="legacy,draft,balanced,shutter")
    ap.add_argument("--heavy", action="store_true")
    ap.add_argument("--keep-frames", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    out, total = make_project(out, a.scenes, a.sec, a.heavy, a.fps, a.width, a.height)
    names = [c.strip() for c in a.configs.split(",") if c.strip()]
    print(f"合成项目：{out}")
    print(f"  {a.scenes} 场 × {a.sec}s @{a.fps}fps = {total:.1f}s"
          f"{' · heavy（高熵帧）' if a.heavy else ''}"
          f"{f' · 只渲前 {a.preview}s' if a.preview else ''}\n")

    results = []
    base_fps = None
    for n in names:
        if n not in CONFIGS:
            print(f"⚠ 未知档位 {n}（可选 {', '.join(CONFIGS)}）")
            continue
        print(f"▶ {n:9} {' '.join(CONFIGS[n])}")
        r = run_cfg(out, n, CONFIGS[n], a.preview, a.keep_frames, total)
        results.append(r)
        if not r["ok"]:
            print(f"  ✗ 失败：{r['log_tail']}")
            continue
        cap = r["capture_sec"] or 0
        fpsr = (r["frames"] / cap) if (cap and r["frames"]) else 0
        if n == "legacy":
            base_fps = fpsr
        tag = ""
        if base_fps and fpsr:
            tag = f"  ×{fpsr / base_fps:.2f} vs legacy"
        print(f"  ✓ {r['frames'] if r['frames'] is not None else '?'} 帧 · 截图 {cap}s"
              f" · 积分 {r['integrate_sec']}s · 总 {r['wall_sec']}s · {fpsr:.1f} 帧/秒{tag}"
              f" · 成片 {r['size_mb']}MB")

    print("\n" + "=" * 104)
    print(f"{'档位':10} {'输出':11} {'fps':>4} {'帧数':>6} {'截图s':>7} {'积分s':>6} "
          f"{'总s':>7} {'帧/秒':>7} {'加速':>6} {'体积MB':>7} 截图模式")
    print("-" * 104)
    for r in results:
        if not r["ok"]:
            print(f"{r['config']:10} 失败")
            continue
        cap = r["capture_sec"] or 0
        fpsr = (r["frames"] / cap) if (cap and r["frames"]) else 0
        sp = f"×{fpsr / base_fps:.2f}" if (base_fps and fpsr) else "—"
        sz = "x".join(str(x) for x in (r["size"] or [])) or "?"
        print(f"{r['config']:10} {sz:11} {str(r['fps_out'] or '?'):>4} "
              f"{str(r['frames'] if r['frames'] is not None else '?'):>6} "
              f"{cap:>7.2f} {r['integrate_sec'] or 0:>6.2f} {r['wall_sec']:>7.2f} "
              f"{fpsr:>7.1f} {sp:>6} {str(r['size_mb']):>7} {r['shot_mode'] or '?'}")
    print("=" * 104)

    rep = {"project": out, "scenes": a.scenes, "sec_per_scene": a.sec, "fps": a.fps,
           "heavy": a.heavy, "preview": a.preview, "results": results}
    rp = os.path.join(out, "bench-report.json")
    json.dump(rep, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n报告：{rp}")
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
