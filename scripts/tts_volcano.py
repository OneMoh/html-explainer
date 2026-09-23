#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tts_volcano.py —— 火山引擎（豆包）语音合成 2.0 接口包。

【为什么单独成一个包】密钥只在这一个文件里被读取，调用方（含 AI agent）
只传「文本 + 音色 + 语速」，永远拿不到也不需要密钥值。本包保证：

  ★ 不打印、不记录、不回显密钥；异常信息一律脱敏（见 _redact）。
  ★ 不把密钥写进任何文件；只读 tts.env，从不写 tts.env。
  ★ 上游返回体里也没有密钥，缓存与 manifest 里也不会出现密钥。
  → agent 只需要会调用本包，不需要（也不应该）读 tts.env。

【接口】与 tts_build.py 的 edge 引擎同构，下游 timing 逻辑零改动：
  synthesize(text, voice, rate=0, ...) -> {
      "audio": bytes,                                  # mp3 字节
      "boundaries": [{"text","offset_sec","duration_sec"}],  # 原始坐标系
      "usage": {"text_words": int} | {},
      "requests": int,                                 # 实际请求数（长文本会切分）
  }
  ★ boundaries 的时间单位是**秒**，坐标系 = 返回音频的起点，
    与 edge-tts 的 WordBoundary 语义一致（下游 subs.py 按 offset_sec - lead_cut 平移）。

【接口规格】（2026-09 核对官方文档）
  POST https://openspeech.bytedance.com/api/v3/tts/unidirectional
  Header: X-Api-Key（必选）/ X-Api-Resource-Id（必选，TTS2.0 = seed-tts-2.0）
          / X-Api-Request-Id（必选，uuid）/ Content-Type: application/json
  Body:   {user:{uid}, req_params:{text, speaker, audio_params:{format,sample_rate,bit_rate,speech_rate}}}
  响应:   NDJSON，逐行 JSON；音频块 code=0 + data(base64)；
          **sentence.words[] 直接给字级时间戳**（word / startTime / endTime / confidence，单位秒）；
          结束标记 code=20000000 且 data=null（★ 不是 code=0，误判会丢最后一段音频）。

【本机注意】openspeech.bytedance.com 是境内端点，默认**绕过系统代理**直连
（本机常驻代理会让境内域名绕远甚至失败）。要强制走代理时设 VOLC_PROXY。

用法：
  python tts_volcano.py --check                    # 连通性自检（用一句话试合成）
  python tts_volcano.py --voices                   # 列出内置常用音色
  python tts_volcano.py --synth "测试文本" out.mp3  # 手动合成一段
  python tts_volcano.py --env-file <路径> ...       # 指定 tts.env（默认自动探测）
被 tts_build.py 作为库调用（provider=volcano 时）。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
DEFAULT_RESOURCE_ID = "seed-tts-2.0"          # TTS 2.0 预置音色
CLONE_RESOURCE_ID = "seed-icl-2.0"            # 声音复刻音色
END_CODE = 20000000                           # ★ 结束标记；不是 0
MAX_TEXT_LEN = 200                            # 单请求文本上限（超了按标点切分）
DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRIES = 3
RETRY_SLEEP = 1.0

# 音色 ID 末尾都是 _uranus_bigtts = 豆包语音合成模型 2.0
DEFAULT_VOICE = "zh_male_m191_uranus_bigtts"   # 云舟 2.0
ENV_FILENAME = "tts.env"

# 内置常用音色（名称, voice_type, 说明）。完整列表见官方音色文档。
VOICES: list[tuple[str, str, str]] = [
    # —— 男声：解说 / 通用 ——
    ("云舟 2.0",        "zh_male_m191_uranus_bigtts",              "男声 · 沉稳通用（默认，最稳）"),
    ("温暖阿虎 2.0",    "zh_male_wennuanahu_uranus_bigtts",        "男声 · 温暖"),
    ("解说小明 2.0",    "zh_male_jieshuoxiaoming_uranus_bigtts",   "男声 · 解说"),
    ("磁性解说男声 2.0", "zh_male_cixingjieshuonan_uranus_bigtts",  "男声 · 磁性解说"),
    ("悬疑解说 2.0",    "zh_male_xuanyijieshuo_uranus_bigtts",     "男声 · 悬疑叙事"),
    ("广告解说 2.0",    "zh_male_guanggaojieshuo_uranus_bigtts",   "男声 · 广告调"),
    ("儒雅青年 2.0",    "zh_male_ruyaqingnian_uranus_bigtts",      "男声 · 青年儒雅"),
    ("少年梓辛 2.0",    "zh_male_shaonianzixin_uranus_bigtts",     "男声 · 少年"),
    # —— 女声 ——
    ("小何 2.0",        "zh_female_xiaohe_uranus_bigtts",          "女声 · 通用（默认女声）"),
    ("Vivi 2.0",        "zh_female_vv_uranus_bigtts",              "女声 · 活泼通用"),
    ("知性灿灿 2.0",    "zh_female_cancan_uranus_bigtts",          "女声 · 知性"),
    ("甜美桃子 2.0",    "zh_female_tianmeitaozi_uranus_bigtts",    "女声 · 甜美"),
    ("邻家女孩 2.0",    "zh_female_linjianvhai_uranus_bigtts",     "女声 · 邻家"),
    ("温柔淑女 2.0",    "zh_female_wenroushunv_uranus_bigtts",     "女声 · 温柔"),
    ("深夜播客 2.0",    "zh_male_shenyeboke_uranus_bigtts",        "男声 · 深夜播客/低语"),
    # —— 英文 ——
    ("Tim",             "en_male_tim_uranus_bigtts",               "美式英语 · 男声"),
    ("Dacey",           "en_female_dacey_uranus_bigtts",           "美式英语 · 女声"),
]

VOICE_BY_NAME = {name: vid for name, vid, _ in VOICES}
VOICE_IDS = {vid for _, vid, _ in VOICES}


def resolve_voice_token(token: str, default: str = "") -> str:
    """把「名称 / 序号 / 原始 ID」统一成音色 ID。空 token → default。

    必需：speaker 字段只认 ID。直接传中文显示名会被服务端拒掉，
    报的还是 `55000000 resource ID is mismatched with speaker related resource`
    这种看不出是「名字没解析」的错误。
    """
    token = (token or "").strip()
    if not token:
        return default or DEFAULT_VOICE
    if token.isdigit() and 1 <= int(token) <= len(VOICES):
        return VOICES[int(token) - 1][1]
    if token in VOICE_BY_NAME:
        return VOICE_BY_NAME[token]
    if token in VOICE_IDS:
        return token
    for name, vid, _ in VOICES:              # 允许带括注的名字，如「云舟 2.0（默认）」
        if name.startswith(token) or token.startswith(name):
            return vid
    return token                             # 自定义 ID（如复刻音色）原样返回


def parse_rate_percent(value) -> int:
    """把各种语速写法统一成整数百分比：'+8%' / '8' / 0.08 / 8 → 8。

    火山 `speech_rate` 与 edge `rate` 语义相同（都表示「快百分之几」），
    只是表示法不同：火山要 int，edge 要 '+N%' 字符串。
    两个下游脚本共用这一个换算，避免各写一份慢慢跑偏。
    """
    if isinstance(value, bool) or value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        v = float(value)
        return int(round(v * 100 if abs(v) <= 1.5 else v))
    m = re.search(r"([-+]?\d+(?:\.\d+)?)", str(value))
    if not m:
        return 0
    v = float(m.group(1))
    if "%" in str(value):
        return int(round(v))
    return int(round(v * 100 if abs(v) <= 1.5 else v))

# 形如 AKLT... 的火山 AccessKey —— 只认这种明确形态，避免把普通 request-id 也抹掉
_SECRET_PAT = re.compile(r"AKLT[A-Za-z0-9_\-]{6,}")


class VolcanoTTSConfigError(RuntimeError):
    """缺 tts.env 或字段不全 —— 由 tts_setup.py 负责引导用户补齐。"""


class VolcanoTTSError(RuntimeError):
    """调用失败（已脱敏，可安全打印）。

    retryable=False 表示**重试没有意义**（密钥错、音色 ID 错、参数错这类 4xx）。
    退避重试只对网络抖动、超时、5xx、429 有意义 —— 对 401 重试三次只是白等两轮。
    """

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


# ---------------------------------------------------------------- 密钥读取
def _skill_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env_candidates(project_dir: str = "") -> list[str]:
    """tts.env 探测顺序：显式指定 → 项目目录 → 技能目录 → 用户目录。"""
    out: list[str] = []
    explicit = os.environ.get("TTS_ENV_FILE", "").strip()
    if explicit:
        out.append(explicit)
    if project_dir:
        out.append(os.path.join(os.path.abspath(project_dir), ENV_FILENAME))
    out.append(os.path.join(_skill_root(), ENV_FILENAME))
    out.append(os.path.join(os.path.expanduser("~"), ".workbuddy", ENV_FILENAME))
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def find_env_file(project_dir: str = "") -> str:
    for p in env_candidates(project_dir):
        if os.path.isfile(p):
            return p
    return ""


def parse_env(path: str) -> dict[str, str]:
    """极简 KEY=VALUE 解析（与 python-dotenv 兼容的最小子集），不执行任何代码。"""
    vals: dict[str, str] = {}
    with open(path, encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            vals[k] = v
    return vals


def load_credentials(project_dir: str = "") -> dict[str, str]:
    """读取密钥。返回的 dict 里含密钥，**调用方不得打印或落盘**。"""
    path = find_env_file(project_dir)
    if not path:
        raise VolcanoTTSConfigError(
            "没有找到 tts.env。跑到项目根目录执行：python <skill>/scripts/tts_setup.py\n"
            "（它会生成一份带注释的空模板，你手工填入 API Key 即可。）")
    vals = parse_env(path)
    api_key = vals.get("VOLC_API_KEY", "").strip()
    app_id = vals.get("VOLC_APP_ID", "").strip()
    access_key = vals.get("VOLC_ACCESS_KEY", "").strip()
    if not api_key and not (app_id and access_key):
        raise VolcanoTTSConfigError(
            f"{path} 里还没有填密钥。请打开该文件填入 VOLC_API_KEY 后告诉我，我来测连接。\n"
            "  API Key 获取：火山引擎控制台 → 语音技术 → API Key 管理\n"
            "  https://console.volcengine.com/speech/new/setting/apikeys")
    return {
        "path": path,
        "api_key": api_key,
        "app_id": app_id,
        "access_key": access_key,
        "resource_id": vals.get("VOLC_RESOURCE_ID", "").strip() or DEFAULT_RESOURCE_ID,
    }


def describe_env(project_dir: str = "") -> dict[str, str]:
    """给 agent/用户看的**脱敏**状态摘要 —— 这个函数的输出可以安全打印。"""
    try:
        c = load_credentials(project_dir)
    except VolcanoTTSConfigError as e:
        return {"status": "missing", "detail": str(e).splitlines()[0]}
    mode = "X-Api-Key" if c["api_key"] else "X-Api-App-Id + X-Api-Access-Key"
    return {
        "status": "ok",
        "env_file": c["path"],
        "auth": mode,
        "key_masked": _mask(c["api_key"] or c["access_key"]),
        "resource_id": c["resource_id"],
    }


def _mask(secret: str) -> str:
    if not secret:
        return "(未设置)"
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}{'*' * 6}{secret[-4:]}（长度 {len(secret)}）"


def _redact(text: str) -> str:
    """把可能混进错误信息的密钥抹掉。异常与日志一律过这一层。

    只做两件事：抹掉**本次实际加载的**密钥值，以及 AKLT 形态的 token。
    刻意不用「长字符串就当密钥」这种宽规则 —— 那会把 reqid、logid 一起抹掉，
    排查问题时就看不到定位线索了（而密钥只可能从下面这两个来源进入输出）。
    """
    try:
        c = load_credentials("")
        for k in ("api_key", "access_key"):
            v = c.get(k) or ""
            if len(v) >= 8 and v in text:
                text = text.replace(v, _mask(v))
    except Exception:
        pass
    return _SECRET_PAT.sub(lambda m: _mask(m.group(0)), text)


# ---------------------------------------------------------------- 请求构造
def _headers(cred: dict[str, str]) -> dict[str, str]:
    h = {
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",       # 不要 gzip，NDJSON 逐行读
        "X-Api-Resource-Id": cred["resource_id"],
        "X-Api-Request-Id": str(uuid.uuid4()),
        # 不加这个头，响应里就没有 usage.text_words（计费字数恒为 0）
        "X-Control-Require-Usage-Tokens-Return": "*",
    }
    if cred["api_key"]:
        h["X-Api-Key"] = cred["api_key"]
    else:                                     # 旧版鉴权兜底
        h["X-Api-App-Id"] = cred["app_id"]
        h["X-Api-Access-Key"] = cred["access_key"]
    return h


def _opener() -> urllib.request.OpenerDirector:
    """默认不走代理：境内端点直连更快更稳；需要时用 VOLC_PROXY 显式指定。"""
    proxy = os.environ.get("VOLC_PROXY", "").strip()
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def split_long_text(text: str, limit: int = MAX_TEXT_LEN) -> list[str]:
    """按标点切分到 <=limit 字，保证不把一个词从中间劈开。"""
    if len(text) <= limit:
        return [text]
    parts = re.split(r"(?<=[。！？；，、,.!?;：:\n])", text)
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        if len(p) <= limit and (not out or len(out[-1]) + len(p) > limit):
            out.append(p)
        elif len(p) <= limit:
            out[-1] += p
        else:                                  # 单句仍超长 → 硬切
            for i in range(0, len(p), limit):
                out.append(p[i:i + limit])
    return [s for s in out if s.strip()] or [text]


def _one_request(text: str, voice: str, cred: dict[str, str], rate: int,
                 fmt: str, sample_rate: int, bit_rate: int,
                 timeout: float, enable_subtitle: bool = True,
                 context_texts: list[str] | None = None,
                 uid: str = "") -> tuple[bytes, list[dict], dict]:
    """单次请求 → (mp3 字节, boundaries, usage)。"""
    audio_params: dict = {"format": fmt, "sample_rate": sample_rate}
    if fmt == "mp3" and bit_rate:
        audio_params["bit_rate"] = bit_rate
    # ★ 不传这个开关，响应里的 sentence.words 恒为空数组 —— 字级时间戳拿不到。
    #   实测（2026-09-23）：同文本 false→words=0，true→words=10。
    #   官方文档示例里默认带词时间戳，容易让人以为「不用开」，实际必须显式打开。
    #   仅豆包语音合成大模型 2.0 音色、仅中英文语种支持。
    if enable_subtitle:
        audio_params["enable_subtitle"] = True
    if rate:
        audio_params["speech_rate"] = int(rate)     # [-50,100] → 0.5x~2.0x

    req_params: dict = {"text": text, "speaker": voice, "audio_params": audio_params}
    if context_texts:
        req_params["context_texts"] = list(context_texts)
    body = {"user": {"uid": uid or f"html-explainer-{uuid.uuid4().hex[:12]}"},
            "req_params": req_params}

    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=_headers(cred), method="POST")

    chunks: list[bytes] = []
    boundaries: list[dict] = []
    usage: dict = {}
    try:
        with _opener().open(req, timeout=timeout) as resp:
            for raw in resp:                       # NDJSON：逐行
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                code = obj.get("code")
                data = obj.get("data")
                # ★ usage 挂在**结束行**上（code=20000000、data=null 那一行）。
                #   先判结束标记再读 usage，会把计费字数永远读成 0（踩过）。
                if obj.get("usage"):
                    usage = obj["usage"]
                if code == END_CODE:               # ★ 结束标记，且不含音频
                    continue
                if code not in (0, None):
                    raise VolcanoTTSError(
                        f"接口返回 code={code} message={obj.get('message')!r}")
                if data:
                    try:
                        chunks.append(base64.b64decode(data))
                    except Exception:
                        raise VolcanoTTSError("音频块 base64 解码失败（流可能被截断）")
                sent = obj.get("sentence") or {}
                for w in (sent.get("words") or []):
                    txt = (w.get("word") or "").strip()
                    if not txt:
                        continue
                    st = float(w.get("startTime") or 0.0)
                    et = float(w.get("endTime") or st)
                    boundaries.append({
                        "text": txt,
                        "offset_sec": round(st, 4),
                        "duration_sec": round(max(0.0, et - st), 4),
                    })
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        hint = ""
        # 4xx 基本都是永久性错误（密钥/音色/参数），重试无益；429 与 5xx 才值得重试
        retryable = e.code == 429 or e.code >= 500
        if e.code in (401, 403):
            hint = "\n  → 鉴权失败：核对 tts.env 里的 VOLC_API_KEY 是否正确、是否已开通该服务。"
        elif e.code == 404:
            hint = "\n  → 音色或资源 ID 不对：预置音色要配 seed-tts-2.0。"
        raise VolcanoTTSError(
            f"HTTP {e.code} {e.reason}{hint}\n  {_redact(detail)}", retryable=retryable)
    except urllib.error.URLError as e:
        raise VolcanoTTSError(
            f"网络不可达：{_redact(str(e.reason))}\n"
            "  → 本包默认绕过系统代理直连。若你的网络确实需要代理，设 VOLC_PROXY=http://127.0.0.1:<port>。")
    except TimeoutError:
        raise VolcanoTTSError(f"请求超时（{timeout}s）")

    if not chunks:
        raise VolcanoTTSError("没有收到任何音频块（检查音色 ID 与文本是否为空）")
    return b"".join(chunks), boundaries, usage


def _looks_like_mp3(b: bytes) -> bool:
    if len(b) < 4:
        return False
    head = b[:4].hex()
    return head.startswith("494433") or head.startswith("fff3") or head.startswith("fffb") \
        or head.startswith("fffa") or head.startswith("fff2")


def synthesize(text: str, voice: str = DEFAULT_VOICE, rate: int = 0,
               fmt: str = "mp3", sample_rate: int = 24000, bit_rate: int = 160000,
               timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES,
               context_texts: list[str] | None = None,
               project_dir: str = "",
               enable_subtitle: bool = True) -> dict:
    """合成一段文本 → {audio, boundaries, usage, requests}。失败抛 VolcanoTTSError。

    enable_subtitle=True（默认）会要求服务端返回字级时间戳。关掉只在
    「音色不支持字幕（非中英文）」时有意义 —— 那种情况下 words 必为空。
    """
    text = (text or "").strip()
    if not text:
        raise VolcanoTTSError("文本为空")
    # ★ 音色解析必须在这里再兜一次：`speaker` 字段只认 ID，
    #   而 project.json 里存的是显示名（如「解说小明 2.0」）。
    #   CLI 路径调过 resolve_voice_token，但 tts_build.py 是直接把 project.json 的
    #   voice 传进来的 —— 少这一步就会拿到服务端的
    #   `55000000 resource ID is mismatched with speaker related resource`，
    #   报错信息完全看不出是「名字没解析」（2026-09-23 实测踩到）。
    voice = resolve_voice_token(voice, DEFAULT_VOICE)
    cred = load_credentials(project_dir)

    last: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            pieces = split_long_text(text)
            audio_all: list[bytes] = []
            bounds_all: list[dict] = []
            usage: dict = {}
            # 长文本切分时，后续片段的词边界要按前面片段的实际时长平移
            for i, piece in enumerate(pieces):
                audio, bounds, u = _one_request(
                    piece, voice, cred, rate, fmt, sample_rate, bit_rate,
                    timeout, enable_subtitle, context_texts)
                if i:
                    offset = _bytes_duration(b"".join(audio_all), fmt)
                    bounds = [{**b, "offset_sec": round(b["offset_sec"] + offset, 4)}
                              for b in bounds]
                audio_all.append(audio)
                bounds_all.extend(bounds)
                if u:
                    usage = u
            audio = b"".join(audio_all)
            if not _looks_like_mp3(audio) and fmt == "mp3":
                raise VolcanoTTSError("返回的音频不是有效 MP3 头（可能被截断）")
            result = {"audio": audio, "boundaries": bounds_all,
                      "usage": usage, "requests": len(pieces)}
            # ★ 要了字幕却一个时间戳都没回来 —— 大概率踩到「音色不支持字幕」。
            #   静默放行会让下游字幕整段塌掉，所以这里显式记一条可打印的警告。
            if enable_subtitle and not bounds_all:
                result["warning"] = (
                    "未返回字级时间戳（sentence.words 为空）。"
                    "该能力仅豆包语音合成大模型 2.0 的中英文音色支持；"
                    "当前音色若不支持，字幕将退化为按整段均分——建议换成 zh_*_uranus_bigtts。")
            return result
        except VolcanoTTSConfigError:
            raise
        except VolcanoTTSError as e:
            if not e.retryable:
                raise                              # 密钥/参数错，重试是白等
            last = e
            if attempt + 1 < max(1, retries):
                time.sleep(RETRY_SLEEP * (attempt + 1))
        except Exception as e:                     # noqa: BLE001
            last = e
            if attempt + 1 < max(1, retries):
                time.sleep(RETRY_SLEEP * (attempt + 1))
    raise VolcanoTTSError(_redact(f"连续 {retries} 次失败：{type(last).__name__}: {last}"))


def _bytes_duration(data: bytes, fmt: str) -> float:
    """用 ffmpeg 量已合成字节的时长（长文本切片拼接时算偏移用）。"""
    import subprocess
    import tempfile
    from shutil import which
    ff = which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return 0.0
    fd, tmp = tempfile.mkstemp(suffix=f".{fmt}")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        r = subprocess.run([ff, "-hide_banner", "-i", tmp],
                           capture_output=True, text=True, errors="replace")
        for line in r.stderr.splitlines():
            if "Duration:" in line:
                t = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = t.split(":")
                return round(int(h) * 3600 + int(m) * 60 + float(s), 3)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return 0.0


def check(project_dir: str = "", voice: str = "", timeout: float = 30.0) -> dict:
    """连通性自检：用一句短文本试合成。返回可安全打印的状态 dict。"""
    try:
        cred = load_credentials(project_dir)
    except VolcanoTTSConfigError as e:
        return {"ok": False, "stage": "env", "detail": str(e)}
    v = resolve_voice_token(voice)
    try:
        r = synthesize("连接测试，这句话只用来验证接口是否可用。",
                       voice=v, timeout=timeout, retries=1, project_dir=project_dir)
        return {
            "ok": True, "stage": "api", "voice": v,
            "env_file": cred["path"],
            "key_masked": _mask(cred["api_key"] or cred["access_key"]),
            "resource_id": cred["resource_id"],
            "audio_bytes": len(r["audio"]),
            "boundaries": len(r["boundaries"]),
            "chars_billed": (r.get("usage") or {}).get("text_words", 0),
        }
    except VolcanoTTSError as e:
        return {"ok": False, "stage": "api", "voice": v, "env_file": cred["path"],
                "detail": str(e)}


# ---------------------------------------------------------------- CLI
def _print_voices() -> None:
    print("内置常用音色（完整列表见官方音色文档）：")
    for i, (name, vid, note) in enumerate(VOICES, 1):
        print(f"  {i:>2}. {name:<18} {note}\n      {vid}")


def main() -> int:
    p = argparse.ArgumentParser(description="火山引擎语音合成 2.0 接口包")
    p.add_argument("--project", default="", help="项目目录（用于探测 tts.env）")
    p.add_argument("--env-file", default="", help="显式指定 tts.env 路径")
    p.add_argument("--check", action="store_true", help="连通性自检")
    p.add_argument("--voices", action="store_true", help="列出内置音色")
    p.add_argument("--synth", default="", help="合成一段文本")
    p.add_argument("--out", default="volcano_tts_test.mp3")
    p.add_argument("--voice", default="")
    p.add_argument("--rate", type=int, default=0)
    args = p.parse_args()

    if args.env_file:
        os.environ["TTS_ENV_FILE"] = args.env_file

    if args.voices:
        _print_voices()
        return 0

    if args.check:
        st = check(args.project, args.voice)
        if st["ok"]:
            print(f"✓ 连接正常 · 音色 {st['voice']} · 音频 {st['audio_bytes']}B · "
                  f"时间戳 {st['boundaries']} 个 · 计费 {st['chars_billed']} 字")
            print(f"  tts.env: {st['env_file']}")
            print(f"  密钥: {st['key_masked']} · 资源 {st['resource_id']}")
            return 0
        print(f"✗ 未通过（{st['stage']}）\n{st['detail']}", file=sys.stderr)
        return 1

    if args.synth:
        try:
            r = synthesize(args.synth, voice=resolve_voice_token(args.voice),
                           rate=args.rate, project_dir=args.project)
        except (VolcanoTTSError, VolcanoTTSConfigError) as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1
        with open(args.out, "wb") as f:
            f.write(r["audio"])
        print(f"✓ {args.out} · {len(r['audio'])}B · 时间戳 {len(r['boundaries'])} 个 "
              f"· 请求 {r['requests']} 次")
        if r.get("warning"):
            print(f"⚠ {r['warning']}", file=sys.stderr)
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
