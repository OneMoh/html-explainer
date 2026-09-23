#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_integrity.py —— 仓库自洽性检查（CI 与本地都能跑，零第三方依赖）。

检查项都对应真实发生过的漂移风险：
  1. SKILL.md 的 version 与 CHANGELOG.md 最新版本号一致
     —— 发布时最容易漏：改了 SKILL.md 忘写 CHANGELOG（或反之）。
  2. style-catalog.json 与 style-catalog.md 的风格 ID 集合完全一致
     —— 两者由 import_styles.py 同时生成，不一致 = 有人只手改了其中一个。
  3. style-catalog.json 的条目数 == SKILL.md 里声明的风格数
     —— 更新风格库时 SKILL.md 的硬编码数字最容易忘记同步。
  4. JSON 每条都有 id / license 字段，且 id 唯一
     —— 授权信息缺失会让 THIRD_PARTY_NOTICES 失真。
  5. 帧模板 / 封面模板不得出现外链字体或 CDN 资源
     —— 离线渲染硬要求，见 frame-contract.md 契约 2。
  6. 密钥防线：.gitignore 必须忽略 tts.env / *.env / *.key，且仓库内不得出现
     真实的火山引擎密钥（非空赋值 / AKLT 形态 token）
     —— 火山 TTS 是本技能唯一需要密钥的功能，泄露即永久失守。

用法：
  python scripts/check_integrity.py            # 以脚本所在技能的根目录为准
  python scripts/check_integrity.py --root .   # 指定仓库根
退出码：0 = 全过，1 = 有失败项。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

OK = "  \u2713"
BAD = "  \u2717"

# 外链资源（离线渲染禁止）
REMOTE = re.compile(r"""(?:<link[^>]+href|@import\s+url\(|<script[^>]+src)\s*=?\s*["'(]?https?://""", re.I)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check_version(root: str, fails: list[str]) -> None:
    """SKILL.md version 必须与 CHANGELOG.md 最新版本号一致。"""
    skill = os.path.join(root, "SKILL.md")
    changelog = os.path.join(root, "CHANGELOG.md")
    if not os.path.isfile(skill) or not os.path.isfile(changelog):
        fails.append("version: 找不到 SKILL.md 或 CHANGELOG.md")
        return

    m = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", read(skill), re.M)
    if not m:
        fails.append("version: SKILL.md 里没有合法的 version 字段")
        return
    skill_ver = m.group(1)

    # CHANGELOG 的第一个 "## [x.y.z]" 标题即最新发布版本
    m2 = re.search(r"^##\s*\[([0-9]+\.[0-9]+\.[0-9]+)\]", read(changelog), re.M)
    if not m2:
        fails.append("version: CHANGELOG.md 里找不到 '## [x.y.z]' 标题")
        return
    log_ver = m2.group(1)

    if skill_ver == log_ver:
        print(f"{OK} 版本一致：{skill_ver}")
    else:
        fails.append(
            f"version: SKILL.md 是 {skill_ver}，CHANGELOG.md 最新是 {log_ver} —— 发布前必须同步"
        )


def check_catalog(root: str, fails: list[str]) -> int | None:
    """两个风格目录必须描述同一组风格。"""
    md_path = os.path.join(root, "references", "style-catalog.md")
    js_path = os.path.join(root, "references", "style-catalog.json")
    if not os.path.isfile(md_path) or not os.path.isfile(js_path):
        fails.append("catalog: 找不到 references/style-catalog.md 或 .json")
        return None

    try:
        entries = json.loads(read(js_path))
    except Exception as exc:  # noqa: BLE001
        fails.append(f"catalog: style-catalog.json 解析失败 —— {exc}")
        return None
    if not isinstance(entries, list):
        fails.append("catalog: style-catalog.json 顶层应为数组")
        return None

    # ---- 结构完整性 ----
    ids: list[str] = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            fails.append(f"catalog: 第 {i} 条不是对象")
            continue
        eid = e.get("id")
        if not eid:
            fails.append(f"catalog: 第 {i} 条缺少 id")
            continue
        if not e.get("license"):
            fails.append(f"catalog: {eid} 缺少 license 字段（授权信息不完整）")
        ids.append(eid)

    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        fails.append(f"catalog: id 重复 —— {', '.join(dupes)}")

    # ---- .md 与 .json 的 ID 集合比对（md 用反引号包 id）----
    md_ids = set(re.findall(r"`((?:frame|vfx)-[a-z0-9-]+|frame-product-promo-30s)`", read(md_path)))
    json_ids = set(ids)
    only_md = sorted(md_ids - json_ids)
    only_json = sorted(json_ids - md_ids)
    if only_md or only_json:
        if only_md:
            fails.append(f"catalog: 只在 .md 里出现 —— {', '.join(only_md)}")
        if only_json:
            fails.append(f"catalog: 只在 .json 里出现 —— {', '.join(only_json)}")
    else:
        print(f"{OK} 风格目录一致：{len(json_ids)} 个风格，.md 与 .json 同步")

    return len(json_ids)


def check_catalog_count(root: str, count: int | None, fails: list[str]) -> None:
    """SKILL.md 里声明的风格数必须等于实际条数。"""
    if count is None:
        return
    skill = os.path.join(root, "SKILL.md")
    if not os.path.isfile(skill):
        return
    body = read(skill)
    # 匹配「共 23 种风格」/「23 个模板」；用后顾断言排除「2–4 种风格轮换」这类区间
    nums = {int(n) for n in re.findall(r"(?<![\d\u2013\u2014-])(\d+)\s*(?:个|种)\s*(?:模板|风格)", body)}
    if not nums:
        print(f"  · 计数：SKILL.md 未声明风格数量，跳过（实际 {count}）")
        return
    if count in nums:
        print(f"{OK} 计数一致：SKILL.md 声明 {sorted(nums)}，实际 {count}")
    else:
        fails.append(
            f"count: SKILL.md 声明 {sorted(nums)} 个风格，实际 {count} 个 —— 更新风格库后忘记同步文案"
        )


def check_no_remote_assets(root: str, fails: list[str]) -> None:
    """模板里不得有外链资源（离线渲染硬要求）。"""
    targets = []
    assets = os.path.join(root, "assets")
    if os.path.isdir(assets):
        targets += [os.path.join(assets, f) for f in sorted(os.listdir(assets))
                    if f.endswith((".html", ".htm"))]
    bad = []
    for p in targets:
        for m in REMOTE.finditer(read(p)):
            bad.append(f"{os.path.basename(p)}: {m.group(0)[:70]}")
    if bad:
        for b in bad:
            fails.append(f"remote: 模板含外链资源（离线渲染会失败/退化）—— {b}")
    elif targets:
        print(f"{OK} 模板无外链资源：{len(targets)} 个模板检查通过")


def check_no_secrets(root: str, fails: list[str]) -> None:
    """密钥防线：tts.env 必须被忽略，且仓库里不得出现真实密钥。

    对应 2026-09-23 加入的火山引擎 TTS 支持 —— 那是本技能唯一需要密钥的功能。
    密钥纪律是「agent 不读、仓库不记」，所以这里做两道自动化检查：
      a) .gitignore 覆盖 tts.env / *.env / *.key，且 tts.env.example 模板仍被跟踪；
      b) 草签文件里不得出现非空的密钥赋值或 AKLT 形态的 token。
    """
    gi = os.path.join(root, ".gitignore")
    if os.path.isfile(gi):
        text = read(gi)
        need = ["tts.env", "*.env", "*.key"]
        missing = [n for n in need if n not in text]
        if missing:
            fails.append(f"secret: .gitignore 未忽略 {', '.join(missing)}"
                         f" —— 密钥可能被提交进公开仓库")
        else:
            print(f"{OK} 密钥防线：.gitignore 已忽略 tts.env / *.env / *.key")
    else:
        fails.append("secret: 没有 .gitignore —— 密钥无保护")

    example = os.path.join(root, "tts.env.example")
    if not os.path.isfile(example):
        if os.path.isfile(os.path.join(root, "tts.env")):
            # 实证过这种踩法：用户把仓库里的 tts.env.example **改名**成 tts.env 去填 key，
            # 于是模板没了、仓库里多了一份（被忽略的）密钥文件。给个能指向原因的说法。
            fails.append("secret: 缺 tts.env.example 模板，但同目录有 tts.env —— "
                         "疑似把模板文件改名成了 tts.env。请恢复 tts.env.example"
                         "（模板要留在仓库），tts.env 另行复制")
        else:
            fails.append("secret: 缺 tts.env.example 模板（用户没有可照抄的密钥模板）")

    # 真实密钥形态：非空赋值 / AKLT 前缀
    SECRET_ASSIGN = re.compile(
        r"^\s*(VOLC_API_KEY|VOLC_ACCESS_KEY|X_Api_Key|X-Api-Key)\s*[=:]\s*[\"']?([^\s\"'#]+)",
        re.M)
    AKLT = re.compile(r"AKLT[A-Za-z0-9_\-]{8,}")
    SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist", ".venv", "venv"}
    SKIP_EXT = {".mp4", ".mp3", ".wav", ".png", ".jpg", ".jpeg", ".ttf", ".otf",
                ".woff", ".woff2", ".zip", ".ico"}
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            # tts.env 本体跳过：它是用户本地文件，本检查只保证它不入库
            if fn in ("tts.env",) or rel in ("tts.env",):
                continue
            try:
                body = read(p)
            except (UnicodeDecodeError, OSError):
                continue
            for m in AKLT.finditer(body):
                hits.append(f"{rel}: AKLT 形态 token")
            if fn.endswith(".example"):
                continue
            for m in SECRET_ASSIGN.finditer(body):
                if m.group(2).strip():          # 有值才算泄露，空模板是合规的
                    hits.append(f"{rel}: {m.group(1)} 有非空值")
    if hits:
        for h in sorted(set(hits)):
            fails.append(f"secret: 疑似真实密钥 —— {h}")
    else:
        print(f"{OK} 密钥防线：仓库内未发现真实密钥（模板里的空赋值不算）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="仓库根目录（默认 = 本脚本所在技能的根）")
    args = ap.parse_args()

    root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.abspath(root)
    print(f"== html-explainer 自洽性检查 ==\n根目录：{root}\n")

    fails: list[str] = []
    check_version(root, fails)
    count = check_catalog(root, fails)
    check_catalog_count(root, count, fails)
    check_no_remote_assets(root, fails)
    check_no_secrets(root, fails)

    print("-" * 40)
    if fails:
        print(f"✗ {len(fails)} 项失败：\n")
        for f in fails:
            print(f"  · {f}")
        return 1
    print("全部检查通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
