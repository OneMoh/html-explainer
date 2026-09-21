#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tts_build.py —— html-explainer 的配音与时间轴数据源（edge-tts）。

【血统与口径】工程化外壳移植自 anything2explainer 的 tts_build.py（经
html-video-workbuddy-driver 的 tts_edges.py 二次实战），核心五件事：
  ① RATE 默认 +8%（长片解说密度；短视频高密度场景可加到 +20%~+37%，
     标定法：同一句话跨 RATE 对比，dur×(1+rate) 应为常数 → 线性可外推）
  ② 每次合成 asyncio.wait_for 硬超时 45s —— edge-tts 的 websocket 会
     偶发**永久挂起**（不抛错不返回零日志），必须把挂死变成可重试失败
  ③ 指数退避重试 4 次（微软端点连续请求会限流抛 NoAudioReceived）
  ④ 句间 0.8s 间隔 + 磁盘缓存（sig 含 boundary 与 trim —— 参数变了旧缓存自动失效）
  ⑤ 默认裁首尾静音（首回退 0.03s 保爆破音、尾保留 0.12s 保收音），
     裁完段间停顿才由 GAP 显式控制

两个 edge-tts 7.x 的坑（已处理，别删）：
  1) boundary 默认 'SentenceBoundary' → 整句一个事件，字幕节拍退化成
     按字数插值。必须显式传 boundary='WordBoundary'。
  2) 相邻数字熔成大数（「沪深300」「4479.55点」→「三百万四千…」），
     数字与数字之间补中文逗号。

时长两级口径（manifest 同时写两个，下游各取所需）：
  container_duration_sec  裁完后 MP3 容器时长 → **帧时长用这个**（音画同步）
  speech_end_sec          词边界末尾（裁后坐标系）→ **末块字幕收尾用这个**
  duration_sec            词边界末尾（原始坐标系）→ 仅排查用

用法（项目目录内）：
  python tts_build.py --project . [--rate +8%] [--voice zh-CN-YunxiNeural] [--no-trim]
产出：
  audio/<id>.mp3 + audio-manifest.json
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys

import edge_tts

DEFAULT_VOICE_ZH = "zh-CN-YunxiNeural"   # 云希，男声
DEFAULT_VOICE_EN = "en-US-GuyNeural"
DEFAULT_RATE = "+8%"
DEFAULT_VOLUME = "+0%"
DEFAULT_PITCH = "+0Hz"
DEFAULT_TIMEOUT = 45.0
DEFAULT_RETRIES = 4
RETRY_SLEEP = 0.8

TRIM_HEAD_BACKOFF = 0.03
TRIM_TAIL_KEEP = 0.12
TRIM_THRESHOLD = 0.004

_NUMERIC_RUN = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def sanitize_for_tts(text: str) -> str:
    """相邻数字之间补中文逗号，防熔读（4479.55 这种完整数字不会被拆）。"""
    tokens, last = [], 0
    for m in _NUMERIC_RUN.finditer(text):
        tokens.append(("text", text[last:m.start()]))
        tokens.append(("num", m.group(0)))
        last = m.end()
    tokens.append(("text", text[last:]))

    out: list[str] = []
    prev_kind = None
    for kind, val in tokens:
        if kind == "num" and prev_kind == "num":
            if out and not out[-1].endswith(("，", ",", "。")):
                out.append("，")
        out.append(val)
        prev_kind = kind
    return "".join(out)


def _boundary_kwarg() -> str:
    try:
        p = inspect.signature(edge_tts.Communicate.__init__).parameters
        return "WordBoundary" if "boundary" in p else "n/a"
    except Exception:
        return "n/a"


def ffmpeg_exe() -> str:
    from shutil import which
    p = which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def container_duration(path: str) -> float:
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path],
                       capture_output=True, text=True, errors="replace")
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return round(int(h) * 3600 + int(m) * 60 + float(s), 3)
    return 0.0


def decode_pcm(path: str, sr: int = 48000):
    import numpy as np
    r = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", path, "-f", "f32le",
                        "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def speech_window(path: str, sr: int = 48000):
    import numpy as np
    x = decode_pcm(path, sr)
    if x.size == 0:
        return 0.0, 0.0
    idx = np.where(np.abs(x) > TRIM_THRESHOLD)[0]
    if idx.size == 0:
        return 0.0, 0.0
    return round(float(idx[0]) / sr, 3), round(float(idx[-1]) / sr, 3)


def trim_edges(path: str, sr: int = 48000) -> float:
    """原地裁首尾静音，返回裁掉的首部长度（秒）。"""
    import numpy as np
    x = decode_pcm(path, sr)
    if x.size == 0:
        return 0.0
    idx = np.where(np.abs(x) > TRIM_THRESHOLD)[0]
    if idx.size == 0:
        return 0.0
    a = max(0, int(idx[0]) - int(TRIM_HEAD_BACKOFF * sr))
    b = min(len(x), int(idx[-1]) + int(TRIM_TAIL_KEEP * sr))
    if b <= a:
        return 0.0
    y = x[a:b]
    tmp = path + ".trim.mp3"
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "f32le", "-ac", "1", "-ar", str(sr), "-i", "-",
           "-c:a", "libmp3lame", "-b:a", "128k", tmp]
    r = subprocess.run(cmd, input=y.astype("<f4").tobytes(), capture_output=True)
    if r.returncode != 0 or not os.path.exists(tmp):
        print(f"  ⚠ trim 失败，保留原文件：{(r.stderr or b'')[-200:]}", file=sys.stderr)
        return 0.0
    os.replace(tmp, path)
    return round(a / sr, 3)


def cache_paths(text, voice, rate, volume, pitch, cache_dir, trim):
    sig = f"{voice}|{rate}|{volume}|{pitch}|{_boundary_kwarg()}|{int(trim)}|{text}"
    h = hashlib.sha1(sig.encode("utf-8")).hexdigest()[:16]
    d = os.path.join(cache_dir, "trim") if trim else cache_dir
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, h + ".mp3"), os.path.join(d, h + ".json")


async def synth(text, out_path, voice, rate, volume=DEFAULT_VOLUME, pitch=DEFAULT_PITCH,
                cache_dir="", timeout=DEFAULT_TIMEOUT, retries=DEFAULT_RETRIES, trim=True) -> dict:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    spoken = sanitize_for_tts(text)

    cache_mp3 = cache_js = ""
    if cache_dir:
        cache_mp3, cache_js = cache_paths(text, voice, rate, volume, pitch, cache_dir, trim)
        if os.path.exists(cache_mp3) and os.path.exists(cache_js):
            bounds = json.load(open(cache_js, encoding="utf-8"))
            with open(cache_mp3, "rb") as f:
                open(out_path, "wb").write(f.read())
            dur = bounds[-1]["offset_sec"] + bounds[-1]["duration_sec"] if bounds else 0.0
            return _result(text, spoken, out_path, voice, rate, bounds, dur, 0.0, trim)

    async def _once():
        kw = {}
        b = _boundary_kwarg()
        if b != "n/a":
            kw["boundary"] = b
        comm = edge_tts.Communicate(spoken, voice, rate=rate, volume=volume, pitch=pitch, **kw)
        audio = bytearray()
        bounds: list[dict] = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                bounds.append({
                    "text": chunk["text"],
                    "offset_sec": round(chunk["offset"] / 10_000_000, 4),
                    "duration_sec": round(chunk["duration"] / 10_000_000, 4),
                })
        if not audio:
            raise RuntimeError("empty audio stream")
        return bytes(audio), bounds

    last: Exception | None = None
    for attempt in range(retries):
        try:
            audio, bounds = await asyncio.wait_for(_once(), timeout=timeout)
            with open(out_path, "wb") as f:
                f.write(audio)
            await asyncio.sleep(RETRY_SLEEP)
            head_cut = trim_edges(out_path) if trim else 0.0
            if cache_dir:
                with open(cache_mp3, "wb") as f:
                    f.write(open(out_path, "rb").read())
                json.dump(bounds, open(cache_js, "w", encoding="utf-8"), ensure_ascii=False)
            dur = bounds[-1]["offset_sec"] + bounds[-1]["duration_sec"] if bounds else 0.0
            return _result(text, spoken, out_path, voice, rate, bounds, dur, head_cut, trim)
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  [retry {attempt + 1}/{retries}] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            await asyncio.sleep(1.5 * (attempt + 1))
    raise SystemExit(
        f"edge-tts 连续 {retries} 次失败：{type(last).__name__}: {last}\n"
        f"已合成段落走缓存不会重复耗时，稍后重跑即可。")


def _result(text, spoken, out_path, voice, rate, bounds, dur, head_cut, trimmed) -> dict:
    cd = container_duration(out_path)
    ds, de = speech_window(out_path) if trimmed else (0.0, cd)
    return {
        "path": os.path.abspath(out_path),
        "bytes": os.path.getsize(out_path) if os.path.exists(out_path) else 0,
        "voice": voice, "rate": rate,
        "spoken_text": spoken, "original_text": text,
        # ★ 词边界是「原始坐标系」；裁剪后请用 lead_cut_sec 平移
        "duration_sec": round(dur, 3),
        "lead_cut_sec": round(head_cut, 3),
        # ★ 帧时长口径：裁后容器时长
        "container_duration_sec": cd,
        # ★ 末块字幕收尾口径：裁后坐标系里的语音真实结束
        #   注意 speech_window(out_path) 量的是**已经裁过**的文件，de 本身就在裁后坐标系里，
        #   绝不能再减 head_cut（那会重复扣一次，症状是「重跑（走缓存）与首跑（现合成）
        #   报出的 speech_end 差一个首裁量」，字幕末块提前消失）。见 lessons.md。
        "speech_start_sec": ds if trimmed else 0.0,
        "speech_end_sec": de if trimmed else round(dur, 3),
        "tail_pad_sec": round(max(0.0, cd - (de if trimmed else dur)), 3),
        "boundary_count": len(bounds),
        "boundaries": bounds,
    }


async def run(args) -> int:
    proj = os.path.abspath(args.project)
    pj = json.load(open(os.path.join(proj, "project.json"), encoding="utf-8"))
    narration = json.load(open(os.path.join(proj, "narration.json"), encoding="utf-8"))
    if isinstance(narration, dict):
        narration = narration.get("items") or []

    voice = args.voice or pj.get("voice") or DEFAULT_VOICE_ZH
    rate = args.rate or pj.get("rate") or DEFAULT_RATE
    out_dir = os.path.join(proj, "audio")
    cache = os.path.join(out_dir, "cache")
    results = []

    for item in narration:
        key, text = item["id"], item["text"]
        r = await synth(text, os.path.join(out_dir, f"{key}.mp3"),
                        voice=item.get("voice", voice), rate=item.get("rate", rate),
                        cache_dir="" if args.no_cache else cache,
                        trim=not args.no_trim)
        r["id"] = key
        results.append(r)
        print(f"  [{key}] {r['bytes']:>8}B  容器 {r['container_duration_sec']:>7.3f}s  "
              f"语音止 {r['speech_end_sec']:>6.3f}s  首裁 {r['lead_cut_sec']:.3f}s  "
              f"bounds={r['boundary_count']}", file=sys.stderr)

    manifest = {
        "voice": voice, "rate": rate,
        "trimmed": not args.no_trim,
        "engine": f"edge-tts {edge_tts.__version__}",
        "boundary_mode": _boundary_kwarg(),
        "items": results,
    }
    mp = os.path.join(proj, "audio-manifest.json")
    json.dump(manifest, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[tts] {len(results)} 段 → audio/ + {mp}")
    total = sum(r["container_duration_sec"] for r in results)
    print(f"[tts] 容器合计 {total:.2f}s（未含段间 gap；timeline_build.py 会加）")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="html-explainer 配音合成（edge-tts）")
    p.add_argument("--project", default=".")
    p.add_argument("--voice", default="")
    p.add_argument("--rate", default="")
    p.add_argument("--no-trim", action="store_true", help="不裁首尾静音（不建议）")
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
