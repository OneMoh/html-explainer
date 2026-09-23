#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
new_project.py —— 建项目脚手架（复制模板、生成配置与主题、写占位解说词）。

用法：
  python new_project.py <工作目录> <slug> [--topic "医疗"] [--preset amber]
      [--fps 30] [--width 1920] [--height 1080]

产出结构：
  <dir>/
    project.json      全片配置（order = 场景顺序，写完解说词后填）
    narration.json    解说词（[{id, text}]，text 用 | 切字幕块）
    theme.css         主题配色（--topic/--preset 决定，后续可换）
    assets/gsap.min.js
    frames/_template.html   场景模板（复制改内容，契约见文件头注释）
    frames/_template.beats.js（占位节拍，subs.py 跑完会被真数据覆盖格式参考）
    research/ script/ audio/ render/ out/
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("slug")
    ap.add_argument("--topic", default="")
    ap.add_argument("--preset", default="")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--lang", default="zh")
    args = ap.parse_args()

    proj = os.path.abspath(args.dir)
    if os.path.exists(proj) and os.listdir(proj):
        print(f"✗ 目录非空：{proj}", file=sys.stderr)
        return 1

    for d in ("frames", "audio", "render", "out", "research", "script", "assets"):
        os.makedirs(os.path.join(proj, d), exist_ok=True)

    # project.json
    pj = {
        "slug": args.slug,
        "lang": args.lang,
        "fps": args.fps,
        "width": args.width,
        "height": args.height,
        "gap": 0.35,
        "order": [],               # 写完 narration.json 后把 id 按顺序填进来
        "theme": "violet",
        "progress": True,
        # 配音引擎：edge = 免费免密钥；volcano = 火山引擎语音合成 2.0（需 tts.env）。
        # ★ 建项目后先问用户用哪个 —— python <skill>/scripts/tts_setup.py --project .
        "provider": "edge",
        "voice": "zh-CN-YunxiNeural" if args.lang == "zh" else "en-US-GuyNeural",
        "rate": "+8%",
    }
    json.dump(pj, open(os.path.join(proj, "project.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # narration.json 占位（示例含 | 切块写法）
    narration = [
        {"id": "intro", "text": "开场钩子，一到两句。|用竖线切字幕块，每块不超过16个字。"},
        {"id": "point1", "text": "第一个论点。|画面节拍用B函数对齐这句。"},
    ]
    json.dump(narration, open(os.path.join(proj, "narration.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 模板与资源
    shutil.copy(os.path.join(SKILL_ROOT, "assets", "gsap.min.js"),
                os.path.join(proj, "assets", "gsap.min.js"))
    tpl = open(os.path.join(SKILL_ROOT, "assets", "frame-template.html"), encoding="utf-8").read()
    open(os.path.join(proj, "frames", "_template.html"), "w", encoding="utf-8", newline="\n").write(
        tpl.replace("TEMPLATE_ID.beats.js", "_template.beats.js"))

    # 封面模板两份：直接建进 frames/，用户改内容即可（默认写在 cover_169/cover_34 下）
    # —— 起始尺寸已按目标画幅设好，只改文案与构型
    cover_src = open(os.path.join(SKILL_ROOT, "assets", "cover-template.html"), encoding="utf-8").read()
    open(os.path.join(proj, "frames", "cover_169.html"), "w", encoding="utf-8", newline="\n").write(
        cover_src.replace("1920px; height: 1080px", "1920px; height: 1080px"))
    open(os.path.join(proj, "frames", "cover_34.html"), "w", encoding="utf-8", newline="\n").write(
        cover_src.replace("1920px; height: 1080px", "1440px; height: 1080px"))

    # 占位 beats（预览模板用；正式场景的 beats 由 subs.py 生成）
    stub = """/* 占位节拍（new_project.py 生成，仅供 _template.html 预览）。
 * 正式节拍由 subs.py 生成：解说词定稿 + tts_build 跑完后自动刷新。 */
window.__BEATS__ = [
  { text: "开场钩子，一到两句。", start: 0.30, end: 2.40 },
  { text: "用竖线切字幕块，每块不超过16个字。", start: 2.40, end: 4.80 },
  { text: "左边卡片", start: 0.40, end: 2.00 },
  { text: "右边卡片", start: 1.80, end: 3.60 },
  { text: "结论句", start: 3.60, end: 5.60 },
  { text: "证据", start: 6.00, end: 8.00 }
];
window.__SEG__ = { id: "_template", duration: 9.0, speech_end: 8.2, tail: 0.8 };
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
    open(os.path.join(proj, "frames", "_template.beats.js"), "w", encoding="utf-8", newline="\n").write(stub)

    # 主题
    import subprocess
    py = sys.executable
    theme_args = [py, os.path.join(SKILL_ROOT, "scripts", "make_theme.py"), "--project", proj, "--use"]
    if args.topic:
        theme_args += ["--topic", args.topic]
    elif args.preset:
        theme_args += ["--preset", args.preset]
    else:
        theme_args += ["--preset", "violet"]
    r = subprocess.run(theme_args, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip() or r.stderr.strip())

    readme = f"""# {args.slug}（html-explainer 项目）

## ★ 先挑画面风格（别从零设计）
`<skill>/references/style-catalog.md` —— **23 个模板风格 / 8 个类别**
（大胆信号卡、奢华极简、NYT 数据图表、瑞士网格、故障艺术、胶片漏光、流体 Hero、
Logo 收尾、东方柔和有机、VFX 文字光标…），每种含画布/字体/时间轴/配色规范。

两类模板改编成本不同：
- **★ rich（12 个）**：单文件 + 纯 CSS @keyframes → 换系统字体栈 + 让出字幕带 + 填内容，即可用
- **gsap（11 个）**：多 composition + CDN GSAP → **不要搬代码**，只取视觉 DNA 用 CSS 重写

改编细则见 `<skill>/references/template-guide.md`。
建议全片轮换 2–4 种风格，避免每场景一个样。

## 流程速查（详情见技能 SKILL.md）
1. research/调研.md —— 按 reference/workflow-guide.md 派研究员，事实带 URL
2. narration.json —— 解说词定稿（`|` 切字幕块，中文每块 ≤16 字）
3. project.json 的 order 填场景顺序（= narration.json 的 id 顺序）
4. 分镜 script/storyboard.md —— **每场景先指定用哪个模板风格**
5. 配音与时间轴：
   python <skill>/scripts/tts_build.py --project .
   python <skill>/scripts/timeline_build.py --project .
   python <skill>/scripts/subs.py --project .
6. 每个场景一个 frames/<id>.html（改编挑中的模板，或从 _template.html 复制；节拍用 B()）
7. 渲染：node <skill>/scripts/render_video.mjs . [--preview 30]
8. QC：python <skill>/scripts/qc_check.py --project .

## ★ 封面双方案（成片后必做）
复制 `assets/cover-template.html` 做**两份独立排版**的封面：
  frames/cover_169.html  1920x1080  -> 抖音主封面（信息流/播放页）
  frames/cover_34.html   1440x1080  -> 兼容主页 3:4 栅格（防切字）
**不是裁切关系**：16:9 裁 3:4 会丢掉 57.8% 的画面宽度，大字钩子必被切。
两份共享配色/主视觉/钩子文案，但各自重排（悖论视觉从右侧并置改成上方竖排、
钩子从两行改成三行）。详规见 `<skill>/references/cover-guide.md`。
渲染：node <skill>/scripts/cover_build.mjs .

主题：{args.topic or args.preset or 'violet'}（make_theme.py --topic ... --use 可换）
"""
    open(os.path.join(proj, "README.md"), "w", encoding="utf-8", newline="\n").write(readme)

    print(f"✓ 项目建好：{proj}")
    print("  下一步：调研 → 解说词定稿 → 分镜（挑模板风格）→ 填 project.json.order")
    print("  风格库：references/style-catalog.md（23 个模板 / 8 类别）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
