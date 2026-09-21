#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
subs.py —— 字幕三出口 + 节拍器 beats.js。

【血统】字幕方案移植自 anything2explainer（tts_build.py + make_srt.py），
经 html-video-workbuddy-driver 实战修订。核心不变式：

  ① 块用 | 切（中文 ≤16 字 / 英文 ≤48 字符），整句一次送 TTS（词边界最准）
  ② 每块首字对齐到 WordBoundary 给的秒 → 帧号（绝不按字数插值：
     中文同字数时长能差 3 倍，插值一定飘）
  ③ 两级时钟：段长用容器时长（音画同步），末块收尾用语音真实结束
     （speech_end_sec，裁后坐标系）—— 混用会「字幕过了语音还没过」
  ④ 停留重分配：按真实语速比例 + 每块 ≥0.6s（water-filling）
  ⑤ 屏幕文本去句读标点（标点只驱动 TTS 停顿，不上画面）

【本技能新增】beats.js 节拍器 —— 把每块的本地秒写进 frames/<id>.beats.js，
场景 HTML 里用 B('文本') 拿到该词的起播秒，画面节拍直接对齐吐字节拍。
解说词改动后重跑 tts_build → 本脚本，beats.js 全部自动刷新，
帧代码一行不用改（这比 anything2explainer 的「帧号硬编码」省一轮全片重对位）。

用法：
  python subs.py --project . [--fps 30]
产出：
  subs.json + frames/<id>.beats.js + out/<slug>.srt / .vtt
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

FPS_DEFAULT = 30
SUB_SIZE = 44
SUB_MAX_W = 1160
SUB_MIN_SIZE = 34
SUB_BUDGET_ZH = 16
SUB_BUDGET_EN = 48
MIN_HOLD = 0.6

_EM = {'space': 0.227, 'upper': 0.668, 'digit': 0.59, 'lower': 0.566,
       'accent': 0.58, 'punct': 0.325}


def text_em(s: str) -> float:
    t = 0.0
    for ch in s:
        c = ord(ch)
        if c >= 0x2000:
            t += 1.0
        elif ch == ' ':
            t += _EM['space']
        elif 'A' <= ch <= 'Z':
            t += _EM['upper']
        elif '0' <= ch <= '9':
            t += _EM['digit']
        elif 'a' <= ch <= 'z':
            t += _EM['lower']
        elif 0xc0 <= c < 0x250:
            t += _EM['accent']
        else:
            t += _EM['punct']
    return t


def fit_size(text, max_w=SUB_MAX_W, size=SUB_SIZE, floor=SUB_MIN_SIZE):
    w = text_em(text) * size
    if w <= max_w:
        return size
    return max(floor, int(size * max_w / w))


def will_wrap(text):
    return text_em(text) * SUB_MIN_SIZE > SUB_MAX_W


def has_cjk(s: str) -> bool:
    return any('\u4e00' <= c <= '\u9fff' for c in s)


_SENT_END = '。！？；'
_PAUSE = '，、：'


def split_chunks(text: str):
    if '|' in text:
        return [c.strip() for c in text.split('|') if c.strip()]
    return auto_split(text)


def auto_split(text: str, budget=None):
    zh = has_cjk(text)
    budget = budget or (SUB_BUDGET_ZH if zh else SUB_BUDGET_EN)
    sents, cur = [], ''
    for ch in text:
        cur += ch
        if ch in _SENT_END:
            sents.append(cur.strip()); cur = ''
    if cur.strip():
        sents.append(cur.strip())
    out = []
    for s in sents:
        if len(s) <= budget:
            out.append(s); continue
        parts, cur = [], ''
        for ch in s:
            cur += ch
            if ch in _PAUSE:
                parts.append(cur.strip()); cur = ''
        if cur.strip():
            parts.append(cur.strip())
        buf = ''
        for p in parts:
            if not buf:
                buf = p
            elif len(buf) + len(p) <= budget:
                buf += p
            else:
                out.append(buf); buf = p
        if buf:
            while len(buf) > budget:
                out.append(buf[:budget]); buf = buf[budget:]
            if buf:
                out.append(buf)
    return out or [text]


_PUNCT_RE = re.compile(r'[\s，。、！？：；“”（）,.!?:;()\-—…·|]')


def chunk_starts(tts_text, chunks, words, lead_cut):
    """每块首字对齐到词边界秒（词边界为原始坐标系 → 减 lead_cut 平移）。"""
    def _t_of(w):
        if 't' in w:
            return float(w['t'])
        return float(w.get('offset_sec', 0.0))

    char_t = [None] * len(tts_text)
    cur = 0
    for w in words:
        wt = _PUNCT_RE.sub('', w.get('text', ''))
        if not wt:
            continue
        p = tts_text.find(wt, cur)
        if p < 0:
            p = tts_text.find(wt[0], cur)
            if p < 0:
                continue
        t = _t_of(w) - lead_cut
        for i in range(p, min(len(tts_text), p + len(wt))):
            char_t[i] = t
        cur = p + len(wt)

    starts, pos = [], 0
    for c in chunks:
        st = None
        for i in range(pos, min(len(tts_text), pos + len(c))):
            if char_t[i] is not None:
                st = char_t[i]; break
        starts.append(st)
        pos += len(c)

    fixed = []
    for st in starts:
        if st is None:
            st = fixed[-1] if fixed else 0.0
        if fixed and st < fixed[-1]:
            st = fixed[-1]
        fixed.append(max(0.0, st))
    if fixed:
        fixed[0] = 0.0
    return fixed


_KEEP_CHARS = set('“”"\'‘’…、～·%（）《》〈〉【】[]()/*&+=-_#@$')
_TO_SPACE = set('  \u3000\t')
_DROP_PUNCT = set('，。！？；：,.!?;:、·|｜')


def clean_sub_text(s: str, lang: str = 'zh') -> str:
    out = []
    for ch in s:
        if ch in _KEEP_CHARS:
            out.append(ch); continue
        if ch in _TO_SPACE:
            if lang != 'zh':
                out.append(' ')
            continue
        if ch in _DROP_PUNCT:
            continue
        out.append(ch)
    t = re.sub(r'\s{2,}', ' ', ''.join(out)).strip()
    return t


def durations_proportional(secs, min_hold):
    n = len(secs)
    if n == 0:
        return []
    if n * min_hold >= sum(secs):
        return [min_hold] * n
    d = list(secs)
    fixed = [False] * n
    for _ in range(n + 2):
        free = [i for i in range(n) if not fixed[i]]
        if not free:
            break
        free_total = sum(secs[i] for i in free)
        budget = sum(secs) - min_hold * (n - len(free))
        changed = False
        for i in free:
            share = budget * (secs[i] / free_total) if free_total > 0 else budget / len(free)
            if share < min_hold:
                d[i] = min_hold; fixed[i] = True; changed = True
            else:
                d[i] = share
        if not changed:
            break
    return d


def frame_of(sec: float, fps: float) -> int:
    return int(round(sec * fps)) + 1


def tc(frame: int, fps: float, sep: str) -> str:
    ms = int(round((frame - 1) * 1000.0 / fps))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}'


# ---- beats.js：给场景作者的对齐节拍器 ----
BEATS_TMPL = """/* 自动生成（subs.py）——解说词/配音改动后重跑即全量刷新，别手改。
 * B(text)  → 该字幕块起播秒（本地坐标系，0 = 本场景第 0 帧）
 * Be(text) → 该块收尾秒
 * 规则：text 匹配「块的原文片段」即可（块内前几个字也行），找不到抛错。
 * __SEG_INFO__：{id, duration, speech_end, tail} —— duration 对帧长、
 * speech_end 是语音真实结束（按它排主体动画，尾部留静止呼吸）。
 * 用法：window.__SEG__.speech_end / window.__SEG__.duration */
window.__BEATS__ = __BEATS_DATA__;
window.__SEG__ = __SEG_DATA__;
(function () {
  var B = window.__BEATS__;
  function find(text) {
    var t = String(text || '').replace(/[\\s，。、！？；：,.!?;:|]/g, '');
    for (var i = 0; i < B.length; i++) {
      var bt = B[i].text.replace(/[\\s，。、！？；：,.!?;:|]/g, '');
      if (bt === t || bt.indexOf(t) === 0 || t.indexOf(bt) === 0) return B[i];
    }
    throw new Error('B() 找不到节拍: ' + text);
  }
  window.B = function (text) { return find(text).start; };
  window.Be = function (text) { return find(text).end; };
})();
"""


def write_beats(path, seg):
    data = [{'text': b['spoken'], 'start': b['local_start_sec'],
             'end': round(b['local_start_sec'] + (b['global_end_sec'] - b['global_start_sec']), 3)}
            for b in seg['blocks']]
    seginfo = {'id': seg['id'], 'duration': seg['duration_sec'],
               'speech_end': seg['speech_end_sec'], 'tail': seg['tail_silence_sec']}
    js = BEATS_TMPL.replace('__BEATS_DATA__', json.dumps(data, ensure_ascii=False, indent=2)) \
                   .replace('__SEG_DATA__', json.dumps(seginfo, ensure_ascii=False))
    open(path, 'w', encoding='utf-8', newline='\n').write(js)


def main() -> int:
    ap = argparse.ArgumentParser(description="html-explainer 字幕 + 节拍器")
    ap.add_argument("--project", default=".")
    ap.add_argument("--fps", type=float, default=0)
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    pj = json.load(open(os.path.join(proj, "project.json"), encoding="utf-8"))
    fps = args.fps or float(pj.get("fps") or FPS_DEFAULT)
    narration = json.load(open(os.path.join(proj, "narration.json"), encoding="utf-8"))
    if isinstance(narration, dict):
        narration = narration.get("items") or []

    man = json.load(open(os.path.join(proj, "audio-manifest.json"), encoding="utf-8"))
    by_id = {it.get("id") or os.path.splitext(os.path.basename(it["path"]))[0]: it
             for it in man.get("items", [])}
    layout = json.load(open(os.path.join(proj, "layout.json"), encoding="utf-8"))

    out = {'fps': fps, 'size': SUB_SIZE, 'safe_width': SUB_MAX_W,
           'budget': {'zh': SUB_BUDGET_ZH, 'en': SUB_BUDGET_EN}, 'segments': []}
    warn_over = []

    for item in narration:
        sid, text = item['id'], item['text']
        chunks = split_chunks(text)
        m = by_id.get(sid) or {}
        words = m.get('boundaries') or []
        lead_cut = float(m.get('lead_cut_sec', 0.0))
        trimmed = bool(man.get('trimmed'))

        tts_text = ''.join(chunks)
        if words:
            starts_sec = chunk_starts(tts_text, chunks, words, lead_cut)
        else:
            total = float(m.get('container_duration_sec') or m.get('duration_sec') or 1.0)
            tot = max(1, sum(len(c) for c in chunks))
            acc, starts_sec = 0, []
            for c in chunks:
                starts_sec.append(total * acc / tot); acc += len(c)
            print(f'  ⚠ {sid}: 无词边界 → 按字数插值（字幕会飘）', file=sys.stderr)

        # 两级时钟：段长 = 容器；末块收尾 = 语音真实结束（均为裁后坐标系）
        seg_container = float(m.get('container_duration_sec') or m.get('duration_sec') or 0.0)
        if trimmed and 'speech_end_sec' in m:
            speech_end = float(m['speech_end_sec'])
        else:
            speech_end = float(m.get('duration_sec') or seg_container) - lead_cut
        span_end = min(speech_end, seg_container) if seg_container else speech_end

        n = len(chunks)
        natural = list(starts_sec) + [span_end]
        if len(natural) < n + 1:
            natural += [span_end] * (n + 1 - len(natural))

        raw_spans = [max(1.0 / fps, natural[i + 1] - natural[i]) for i in range(n)]
        spans = durations_proportional(raw_spans, MIN_HOLD) if n else []
        edges = [starts_sec[0] if starts_sec else 0.0]
        for d in spans:
            edges.append(edges[-1] + d)
        if edges[-1] > span_end and len(edges) > 1:
            k = span_end / edges[-1]
            edges = [starts_sec[0] + (e - starts_sec[0]) * k for e in edges]
        starts_sec = edges[:-1]
        bounds = edges

        base = float(layout.get(sid, {}).get('start_sec', 0.0))

        blocks = []
        for i, c in enumerate(chunks):
            a, b = bounds[i], bounds[i + 1]
            if b <= a:
                b = a + 1.0 / fps
            f0, f1 = frame_of(a, fps), max(frame_of(a, fps), frame_of(b, fps) - 1)
            screen = clean_sub_text(c, 'zh' if has_cjk(c) else 'en') or c
            size = fit_size(screen)
            blocks.append({
                'text': screen, 'spoken': c, 'from': f0, 'to': f1,
                'local_start_sec': round(a, 3),
                'global_start_sec': round(base + a, 3),
                'global_end_sec': round(base + b, 3),
                'size': size,
            })
            if will_wrap(screen) or len(screen) > (SUB_BUDGET_ZH if has_cjk(screen) else SUB_BUDGET_EN):
                warn_over.append((sid, screen))

        out['segments'].append({
            'id': sid, 'text': text, 'chunks': chunks, 'tts_text': tts_text,
            'start_sec': round(base, 3), 'duration_sec': round(seg_container, 3),
            'speech_end_sec': round(speech_end, 3),
            'tail_silence_sec': round(max(0.0, seg_container - speech_end), 3),
            'blocks': blocks,
        })

    sp = os.path.join(proj, 'subs.json')
    json.dump(out, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    # beats.js per scene
    frames_dir = os.path.join(proj, 'frames')
    os.makedirs(frames_dir, exist_ok=True)
    for s in out['segments']:
        write_beats(os.path.join(frames_dir, f"{s['id']}.beats.js"), s)

    # SRT / VTT
    items = []
    for s in out['segments']:
        for b in s['blocks']:
            gf0 = frame_of(b['global_start_sec'], fps)
            gf1 = max(gf0, frame_of(b['global_end_sec'], fps) - 1)
            items.append((gf0, gf1, b['text']))
    items.sort(key=lambda x: x[0])
    for i in range(len(items) - 1):
        if items[i][1] >= items[i + 1][0]:
            items[i] = (items[i][0], items[i + 1][0] - 1, items[i][2])

    srt, vtt = [], ['WEBVTT', f'NOTE {len(items)} 条 · fps {fps}', '']
    for i, (f0, f1, text) in enumerate(items, 1):
        srt.append(f'{i}\n{tc(f0, fps, ",")} --> {tc(f1 + 1, fps, ",")}\n{text}\n')
        vtt.append(f'{tc(f0, fps, ".")} --> {tc(f1 + 1, fps, ".")}\n{text}\n')

    slug = pj.get('slug') or 'video'
    out_dir = os.path.join(proj, 'out')
    os.makedirs(out_dir, exist_ok=True)
    srt_p = os.path.join(out_dir, f'{slug}.srt')
    open(srt_p, 'w', encoding='utf-8', newline='\n').write('\n'.join(srt))
    open(os.path.splitext(srt_p)[0] + '.vtt', 'w', encoding='utf-8', newline='\n').write('\n'.join(vtt))

    n_blocks = sum(len(s['blocks']) for s in out['segments'])
    print(f'[subs] {len(out["segments"])} 段 → {n_blocks} 块 · fps {fps}')
    print(f'[subs] → {sp} + frames/<id>.beats.js + {srt_p}(.vtt)')
    for s in out['segments']:
        print(f'  {s["id"]:<12} {len(s["blocks"])} 块  语音止 {s["speech_end_sec"]:>6.2f}s '
              f'/ 容器 {s["duration_sec"]:>6.2f}s（尾静音 {s["tail_silence_sec"]:.2f}s 不挂字幕）')
    if warn_over:
        print(f'⚠ {len(warn_over)} 块超预算（自动缩字号，>1.3× 折两行压内容区，按缺陷处理）：')
        for sid, c in warn_over[:8]:
            print(f'    {sid}: "{c}"')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
