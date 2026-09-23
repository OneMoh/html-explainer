#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tts_setup.py —— 配音方案设置向导（选 TTS 引擎 → 配密钥 → 测连接 → 选音色）。

【它在流程里的位置】SKILL.md 的「确认点 3」要求先问用户用哪个 TTS。
本脚本把那次对话落成可复现的三步，并保证**密钥永不经过对话窗口**：

  ① 选方案   edge-tts（免费、免密钥、开箱可用） / 火山引擎语音合成 2.0（音质更好，需 API Key）
  ② 配密钥   选火山但缺 tts.env → 生成带注释的空模板 → 打印指引 → 退出（NEXT_ACTION=fill_env）
            用户填好回来说一声 → 重跑本脚本（或 --check）→ 测连接
  ③ 选音色   列出内置常用音色（可自定义 ID）→ 写进 project.json

【密钥纪律】本脚本**从不打印、不落盘、不回显**密钥值；状态摘要走 tts_volcano.describe_env()
（内部已脱敏）。也不会因为测连接失败而把密钥打进日志。

用法：
  python tts_setup.py --project . --status                 # 当前配置 + 脱敏密钥状态
  python tts_setup.py --project . --provider volcano       # 选火山（缺 env 则生成模板后退出）
  python tts_setup.py --project . --list-voices            # 列出候选音色
  python tts_setup.py --project . --check                  # 测连接（火山走真合成；edge 查依赖）
  python tts_setup.py --project . --provider volcano --voice "解说小明 2.0"   # 一步到位
  python tts_setup.py --project .                          # 交互式（人在终端时用）

退出码：0 完成；2 = 需要用户手工填 tts.env 后再来；1 = 出错。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tts_volcano  # noqa: E402

ENV_FILENAME = "tts.env"
ENV_TEMPLATE = """\
# ---------------------------------------------------------------
# 火山引擎（豆包）语音合成 2.0 —— 密钥配置
# 本文件由 tts_setup.py 生成，已被 .gitignore 忽略，不会进 git 仓库。
# ★ agent 不需要、也不应该读取本文件；接口包 scripts/tts_volcano.py 会自己读。
# ---------------------------------------------------------------

# 【必填】API Key —— 火山引擎控制台 → 语音技术 → API Key 管理
# https://console.volcengine.com/speech/new/setting/apikeys
VOLC_API_KEY=

# 资源 ID：seed-tts-2.0 = 预置音色；seed-icl-2.0 = 声音复刻音色
VOLC_RESOURCE_ID=seed-tts-2.0

# 【可选】旧版鉴权：若你拿到的是 APP ID + Access Token 而不是 API Key，填这两项
VOLC_APP_ID=
VOLC_ACCESS_KEY=
"""

# edge-tts 常用音色（名称, voice, 说明）。完整列表：edge-tts --list-voices
EDGE_VOICES: list[tuple[str, str, str]] = [
    ("云希（默认）",   "zh-CN-YunxiNeural",       "中文男声 · 年轻，解说常用"),
    ("云健",           "zh-CN-YunjianNeural",     "中文男声 · 浑厚，纪录片感"),
    ("晓晓",           "zh-CN-XiaoxiaoNeural",    "中文女声 · 通用"),
    ("晓伊",           "zh-CN-XiaoyiNeural",      "中文女声 · 甜"),
    ("云扬",           "zh-CN-YunyangNeural",     "中文男声 · 新闻播报"),
    ("云夏",           "zh-CN-YunxiaNeural",      "中文男声 · 少年"),
    ("辽宁小北",       "zh-CN-liaoning-XiaobeiNeural", "中文女声 · 东北方言"),
    ("Guy（英文）",    "en-US-GuyNeural",         "英文男声"),
    ("Aria（英文）",   "en-US-AriaNeural",        "英文女声"),
]

EDGE_DEFAULT_ZH = "zh-CN-YunxiNeural"
EDGE_DEFAULT_EN = "en-US-GuyNeural"


def catalog(provider: str) -> list[tuple[str, str, str]]:
    return tts_volcano.VOICES if provider == "volcano" else EDGE_VOICES


def resolve_voice(provider: str, token: str) -> str:
    """名称 / 序号 / 原始 ID 都能接受。返回 "" 表示「用户没指定」。"""
    token = (token or "").strip()
    if not token:
        return ""
    if provider == "volcano":
        # 交给接口包解析，避免两处规则各写一份、慢慢跑偏
        return tts_volcano.resolve_voice_token(token)
    cat = catalog(provider)
    if token.isdigit() and 1 <= int(token) <= len(cat):
        return cat[int(token) - 1][1]
    for name, vid, _ in cat:
        if token == name or token == vid:
            return vid
    # 允许带括注的名字，如「云希（默认）」
    for name, vid, _ in cat:
        if name.startswith(token) or token.startswith(name):
            return vid
    return token                                   # 自定义 ID 原样返回


def _normalize_rate(provider: str, value) -> object:
    """把语速写成该引擎的表示法：火山 = int 百分比，edge = '+N%'。

    new_project.py 默认写 '+8%'（那是 edge 的格式）。用户后来切到火山时若不清洗，
    火山项目的 project.json 里就一直留着 edge 字符串 —— 下游换算虽然能兜住，
    但 --status 打出来会让人以为配错了引擎。
    """
    if value is None or value == "":
        return 0 if provider == "volcano" else "+8%"
    pct = tts_volcano.parse_rate_percent(value)
    if provider == "volcano":
        return max(-50, min(100, pct))
    return f"{pct:+d}%"


def print_voices(provider: str) -> None:
    label = "火山引擎语音合成 2.0" if provider == "volcano" else "edge-tts"
    print(f"{label} 候选音色：")
    for i, (name, vid, note) in enumerate(catalog(provider), 1):
        print(f"  {i:>2}. {name:<22} {note}")
        print(f"      {vid}")
    print("  （也可以直接给音色 ID 自定义）")


def load_project(project: str) -> tuple[str, dict]:
    proj = os.path.abspath(project or ".")
    pj_path = os.path.join(proj, "project.json")
    if not os.path.isfile(pj_path):
        print(f"✗ 找不到 {pj_path}（--project 要指向视频项目目录）", file=sys.stderr)
        raise SystemExit(1)
    return proj, json.load(open(pj_path, encoding="utf-8"))


def save_project(proj: str, pj: dict) -> None:
    with open(os.path.join(proj, "project.json"), "w", encoding="utf-8") as f:
        json.dump(pj, f, ensure_ascii=False, indent=2)


def ensure_env_file(proj: str) -> tuple[str, bool]:
    """返回 (路径, 是否本次新建)。已存在则原样返回，**不读内容**。

    优先级与 tts_volcano.env_candidates() 保持一致：项目目录 → 技能目录 → 新建于项目目录。
    不按同序查找会出现「向导认技能目录的、接口包认项目目录的」这种静默错位。
    """
    project_env = os.path.join(proj, ENV_FILENAME)
    if os.path.isfile(project_env):
        return project_env, False
    skill_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ENV_FILENAME)
    if os.path.isfile(skill_env):
        return skill_env, False
    with open(project_env, "w", encoding="utf-8") as f:
        f.write(ENV_TEMPLATE)
    return project_env, True


def cmd_status(proj: str, pj: dict) -> int:
    provider = pj.get("provider") or os.environ.get("TTS_PROVIDER") or "edge"
    rate = pj.get("rate")
    if rate is None or rate == "":
        rate_shown = "(未设置，将用默认)"
    elif provider == "volcano":
        rate_shown = f"{rate}%（快慢百分比，0 = 原速）"
    else:
        rate_shown = str(rate)
    print(f"当前方案：{provider}")
    print(f"当前音色：{pj.get('voice') or '(未设置，将用默认)'}")
    print(f"当前语速：{rate_shown}")
    if provider == "volcano":
        st = tts_volcano.describe_env(proj)
        if st["status"] == "ok":
            print(f"tts.env ：已就绪 {st['env_file']}")
            print(f"密钥    ：{st['key_masked']}（脱敏显示）· 鉴权 {st['auth']} · 资源 {st['resource_id']}")
        else:
            print(f"tts.env ：未就绪 —— {st['detail']}")
    else:
        try:
            import edge_tts  # noqa: F401
            print("edge-tts：已安装（免费，无需密钥）")
        except ImportError:
            print("edge-tts：未安装 → pip install edge-tts")
    return 0


def cmd_check(proj: str, provider: str, voice: str) -> int:
    print(f"测试方案：{provider}", flush=True)   # flush：否则与 stderr 的错误信息交错乱序
    if provider == "volcano":
        st = tts_volcano.check(proj, voice)
        if st["ok"]:
            print(f"✓ 火山接口连通 · 音色 {st['voice']} · 音频 {st['audio_bytes']}B · "
                  f"时间戳 {st['boundaries']} 个 · 计费 {st['chars_billed']} 字")
            print(f"  tts.env {st['env_file']} · 密钥 {st['key_masked']}")
            return 0
        print(f"✗ 火山接口未通过（{st['stage']}）\n{st['detail']}", file=sys.stderr)
        return 1
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        print("✗ edge-tts 未安装：pip install edge-tts", file=sys.stderr)
        return 1
    if shutil.which("ffmpeg") is None:
        try:
            import imageio_ffmpeg  # noqa: F401
        except ImportError:
            print("✗ 缺 ffmpeg（edge 引擎裁静音/量时长要用）：pip install imageio-ffmpeg",
                  file=sys.stderr)
            return 1
    print("✓ edge-tts 与 ffmpeg 就绪（edge 不需要密钥）")
    return 0


def interactive_ask(prompt: str, options: list[tuple[str, str]], default_idx: int = 0) -> str:
    print(prompt)
    for i, (label, note) in enumerate(options, 1):
        mark = "（默认）" if i - 1 == default_idx else ""
        print(f"  {i}. {label}{mark}    {note}")
    while True:
        raw = input(f"选择 [1-{len(options)}]，直接回车用默认：").strip()
        if not raw:
            return options[default_idx][0]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        print("  输入不在范围内，再试一次。")


def run(args) -> int:
    proj, pj = load_project(args.project)
    provider = (args.provider or os.environ.get("TTS_PROVIDER")
                or pj.get("provider") or "").lower()

    if args.status:
        return cmd_status(proj, pj)

    # ---- ① 选方案 ----
    if provider not in ("edge", "volcano"):
        if not sys.stdin.isatty():
            print("当前未设置配音方案。可选：", file=sys.stderr)
            print("  --provider edge     免费、免密钥、开箱可用（默认）", file=sys.stderr)
            print("  --provider volcano  火山引擎语音合成 2.0，音质更好，需 API Key", file=sys.stderr)
            print("NEXT_ACTION=ask_user_provider")
            return 1
        choice = interactive_ask(
            "配音用哪个 TTS？",
            [("edge-tts", "免费、免密钥、开箱可用"),
             ("火山引擎语音合成 2.0", "音质更好、需 API Key（约 1 分钟配置）")])
        provider = "edge" if choice.startswith("edge") else "volcano"

    # ★ 方案一旦确定立刻落盘。用户填 key 会中断流程，若不落盘，
    #   回来跑 --check 时 project.json 还写着 edge，会静默去测 edge（踩过这个坑）。
    if pj.get("provider") != provider:
        pj["provider"] = provider
        save_project(proj, pj)

    # ---- ② 密钥（仅火山） ----
    if provider == "volcano":
        env_path, created = ensure_env_file(proj)
        if created:
            print(f"✓ 已生成密钥模板：{env_path}")
            print("  （该文件已被 .gitignore 忽略，不会进仓库；我也不会读它的内容）")
            print()
            print("请手动完成两步：")
            print("  1. 打开上面这个文件，把 VOLC_API_KEY= 后面填上你的 API Key")
            print("     API Key 获取：https://console.volcengine.com/speech/new/setting/apikeys")
            print("  2. 存盘后回来告诉我「填好了」，我再测连接并继续")
            print()
            print("NEXT_ACTION=fill_env")
            return 2
        voice_for_check = resolve_voice("volcano", args.voice or pj.get("voice", ""))
        st = tts_volcano.check(proj, voice_for_check)
        if not st["ok"]:
            print(f"✗ 密钥已存在但连接未通过（{st['stage']}）：\n{st['detail']}", file=sys.stderr)
            print(f"  tts.env：{env_path}", file=sys.stderr)
            return 1
        print(f"✓ 连接正常 · 音色 {st['voice']} · 密钥 {st['key_masked']}")

    # ---- ③ 选音色 ----
    name_or_id = args.voice or ""
    if not name_or_id:
        if not sys.stdin.isatty():
            default = tts_volcano.DEFAULT_VOICE if provider == "volcano" else EDGE_DEFAULT_ZH
            print(f"未指定音色，使用默认 {default}")
            print("NEXT_ACTION=ask_user_voice")
            name_or_id = default
        else:
            print_voices(provider)
            name_or_id = input("音色（填序号 / 名称 / 直接给 ID，回车用默认）：").strip() or ""

    default_voice = tts_volcano.DEFAULT_VOICE if provider == "volcano" else EDGE_DEFAULT_ZH
    voice = resolve_voice(provider, name_or_id) or default_voice

    # ---- 写回 project.json ----
    pj["provider"] = provider
    pj["voice"] = voice
    pj["rate"] = _normalize_rate(provider, args.rate or pj.get("rate"))
    save_project(proj, pj)

    print()
    print(f"✓ 已写入 {os.path.join(proj, 'project.json')}")
    rate_shown = f"{pj['rate']}%（快慢百分比）" if provider == "volcano" else pj["rate"]
    print(f"  方案 {provider} · 音色 {voice} · 语速 {rate_shown}")
    if provider == "volcano":
        print("  下一步：python <skill>/scripts/tts_build.py --project .")
    else:
        print("  下一步：python <skill>/scripts/tts_build.py --project .")
    print("NEXT_ACTION=done")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="html-explainer 配音方案设置向导")
    p.add_argument("--project", default=".")
    p.add_argument("--provider", default="", choices=["", "edge", "volcano"])
    p.add_argument("--voice", default="")
    p.add_argument("--rate", default="")
    p.add_argument("--status", action="store_true", help="显示当前配置与脱敏密钥状态")
    p.add_argument("--check", action="store_true", help="只测连接")
    p.add_argument("--list-voices", action="store_true", help="列出候选音色")
    p.add_argument("--env-file", default="", help="显式指定 tts.env（仅本次）")
    args = p.parse_args()

    if args.env_file:
        os.environ["TTS_ENV_FILE"] = args.env_file

    proj, pj = load_project(args.project)
    provider = (args.provider or os.environ.get("TTS_PROVIDER")
                or pj.get("provider") or "edge").lower()

    if args.list_voices:
        print_voices(provider)
        return 0
    if args.check:
        return cmd_check(proj, provider, resolve_voice(provider, args.voice))
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
