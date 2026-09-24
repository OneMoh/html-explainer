<div align="center">

# html-explainer

**An Agent Skill: give it a topic, get back a narrated explainer video with subtitles and covers.**

Write scenes in HTML → deterministic frame-by-frame rendering → a real MP4. Everything runs
locally; the core pipeline needs no API key and charges no per-render fee.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.3.1-blue.svg)](CHANGELOG.md)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-SKILL.md-8A2BE2.svg)](SKILL.md)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-%E2%9C%93-D97757.svg)](#install)
[![Codex](https://img.shields.io/badge/Codex-%E2%9C%93-000000.svg)](#install)
[![WorkBuddy](https://img.shields.io/badge/WorkBuddy-%E2%9C%93-1f6feb.svg)](#install)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg?logo=python&logoColor=white)](#requirements)
[![Node](https://img.shields.io/badge/Node-18%2B-339933.svg?logo=node.js&logoColor=white)](#requirements)

[简体中文](README.md) · [English](README.en.md)

<br/>

Three finished videos made with this skill — visuals, voiceover, subtitles and covers all
produced by the pipeline, no manual post-production. Covers and other assets live in a separate
[demos repository](https://github.com/OneMoh/html-explainer-demos); this repo stays text-only.

https://github.com/user-attachments/assets/912e6c2d-831f-43dd-a39f-57b749bb417d

| HK innovative drugs · early session | A quant firm built an LLM |
|---|---|
| https://github.com/user-attachments/assets/8007843c-088d-457c-8550-81ec912e0add | https://github.com/user-attachments/assets/28949988-449b-4c4e-8d0f-6706af6f64ee |

**Follow the test accounts — watch the video stats in real time**

| Douyin · OnlyOneMoh | Profile · Moen | Douyin · Moen_xin |
|---|---|---|
| <img src="https://raw.githubusercontent.com/OneMoh/html-explainer-demos/main/images/douyin-qr-moh-onlyonemoh.jpg" width="240"> | <img src="https://raw.githubusercontent.com/OneMoh/html-explainer-demos/main/images/douyin-profile-moen.jpg" width="240"> | <img src="https://raw.githubusercontent.com/OneMoh/html-explainer-demos/main/images/douyin-qr-moenxin.jpg" width="240"> |

</div>

---

## What it is

`html-explainer` turns a topic into a **narrated explainer video with burned-in subtitles and a
progress bar**, with the visuals written in HTML/CSS/GSAP.

**It is an Agent Skill** (`SKILL.md` + `scripts/` + `references/`), following the
[Agent Skills](https://code.claude.com/docs/en/skills) convention, so Claude Code, OpenAI Codex,
WorkBuddy, Cursor, Gemini CLI and others can load it directly. Underneath it is plain Python and
Node scripts, so you can also run it by hand.

You say one sentence:

> Make a 1-minute explainer video about why the sky is blue.

The skill then walks the agent through: research → script → voiceover → subtitles and beats →
scene authoring in one of 23 styles → render → QC → covers.

---

## Install

### One-line install (recommended)

Send this to your agent:

```text
Install this Skill into my local environment: https://github.com/OneMoh/html-explainer.git
Put it in your skills directory and check/install the required runtime
(Python 3.9+ / Node 18+ / Chrome or Edge / ffmpeg)
```

It clones into the right directory, runs the environment check and installs whatever is missing.
Then **start a new session** so the agent rescans its skills directory.

### Manual install

The repository root **is** the skill directory (`SKILL.md` sits at the root), so clone it straight
into your skills directory — there is no subdirectory to copy:

```bash
git clone https://github.com/OneMoh/html-explainer.git ~/.workbuddy/skills/html-explainer
bash ~/.workbuddy/skills/html-explainer/setup_env.sh --install
```

On Windows `~` is `C:\Users\<you>`.

### Skills directory by agent

| Agent | Personal (global) | Project (in-repo) |
|---|---|---|
| **WorkBuddy** | `~/.workbuddy/skills/` | `<workspace>/.workbuddy/skills/` |
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` |
| **OpenAI Codex** | `~/.codex/skills/` | `.codex/skills/` or `.agents/skills/` |
| **Gemini CLI** | `~/.gemini/skills/` | `.gemini/skills/` or `.agents/skills/` |
| **Cursor** | `~/.cursor/skills/` | `.cursor/skills/` |
| **GitHub Copilot / VS Code** | `~/.copilot/skills/` | `.github/skills/` |
| **OpenCode** | `~/.config/opencode/skills/` | `.opencode/skills/` |
| **Windsurf** | `~/.windsurf/skills/` | `.windsurf/skills/` |
| Others (common convention) | `~/.agents/skills/` | `.agents/skills/` |

If unsure where to put it, prefer `.agents/skills/` — most tools read it. (Claude Code is the
exception and only reads `.claude/skills/`.)

### Requirements

| Item | Minimum | Notes |
|---|---|---|
| Python | 3.9+ | `edge-tts==7.2.8` (pinned deliberately — v7 changed the boundary API), `numpy`, `pillow`, `imageio-ffmpeg`. **The Volcano engine needs nothing extra** (stdlib `urllib` only, no SDK) |
| Node.js | 18+ | Used by the renderer and the cover builder |
| Browser | Chrome or Edge | Auto-detected; playwright chromium (~115MB, one time) only if neither exists |
| ffmpeg | any version | Looked up on `PATH`; falls back to the static binary bundled with `imageio-ffmpeg` |
| Disk | ~2GB per video | Frame PNGs are large; safe to delete after muxing |

`bash setup_env.sh` only reports what is missing; `--install` installs it. No admin rights needed.

---

## Voice-over: two engines

Before the pipeline starts the agent **asks which TTS you want**, then lists candidate voices for
you to pick from (or you can just hand it a voice ID):

| | `edge-tts` | Volcano Engine TTS 2.0 |
|---|---|---|
| What you do | nothing | paste an API Key once |
| Cost | free | billed per character |
| Voices | a set of built-in zh/en voices | Doubao 2.0 voice library, incl. voice cloning |
| Word timestamps | `WordBoundary` | `sentence.words[]` |
| Extra deps | `edge-tts==7.2.8`, `imageio-ffmpeg` | **none** — stdlib `urllib` only |
| When to pick it | default; works out of the box | when you want more natural prosody / better quality |

Both engines emit an **identical** `audio-manifest.json`, so the timeline, the subtitles and the
renderer **all stay untouched** — switching engines is a one-field change.

### With Volcano, the only thing you touch

The first time it runs Volcano, the skill **creates a `tts.env` and stops**, then tells you to paste
your API Key into it (console → Speech → API Key management). Say "done" and the agent tests the
connection, confirms the voice, and carries on.

**That step deliberately bypasses the chat window** — the key is never sent to the agent, and the
agent never needs to know it.

Built-in voices (full list in the
[official voice docs](https://docs.volcengine.com/docs/6561/1257544)):

| Male | Female |
|---|---|
| Yunzhou 2.0 (default) · Wennuan Ahu 2.0 · Jieshuo Xiaoming 2.0 · Cixing Jieshuo Nan 2.0<br>Xuanyi Jieshuo 2.0 · Guanggao Jieshuo 2.0 · Ruya Qingnian 2.0 · Shaonian Zixin 2.0 · Shenye Boke 2.0 | Xiaohe 2.0 · Vivi 2.0 · Zhixing Cancan 2.0<br>Tianmei Taozi 2.0 · Linjia Nvhai 2.0 · Wenrou Shunv 2.0 |

If the built-in list is not enough, a voice ID from voice cloning works too.

### Key discipline

The API Key lives only in `tts.env`, and **only one interface package inside the skill reads it**.
The agent calls that package, so it neither gets nor needs the key value:

```
you (fill it in once) → tts.env (already gitignored)
                            ↓  only the interface package reads it
                     synthesis call  ← the agent calls this; never sees the key
                            ↓
                     Volcano Engine
```

- **Never in the chat**: ask the agent for key status; what comes back is a masked summary
  (`ef90******86c8`).
- **Never in the repo**: `.gitignore` covers `tts.env` / `*.env` / `*.key` / `*.pem` / `secrets/`;
  the repo self-check has a dedicated **key-defence** rule, itself proven by a negative test —
  a deliberately planted fake key gets caught.
- **Never in logs**: error messages are redacted — only the key value actually used and `AKLT…`
  tokens are scrubbed. Deliberately **not** a broad "any long string is a secret" rule, which would
  also erase the request IDs you need for support.
- **Never in a distribution**: packaging the skill excludes key files.
- **Backstop** (the real security boundary): if it leaks anyway, keep the blast radius small — use
  a **sub-account with speech-synthesis-only permission**, set **usage alerts and quotas**, and
  **rotate** the key.

> Bluntly: the synthesis code runs on your machine, so the key is visible to that process at
> runtime — **"the agent can never read it" is not achievable**. What is guaranteed is *not in the
> chat, not in the repo, not in the logs, not in the distribution*, which shrinks a leak into one
> revocable incident.
>
> Also **don't store the key in an environment variable** — many hosts dump the process environment
> straight into the session transcript.

**Don't rename `tts.env.example` to `tts.env` and fill that in.** It is the template meant to stay
in the repo; renaming it leaves everyone else without one (the repo self-check reports it).
Copy it, then fill the copy.

---

## Video project layout

Say one sentence and the agent walks the whole pipeline inside a **video project directory**;
output lands in `out/`: `slug.mp4`, `cover_169.png`, `cover_34.png`, `slug.srt`, `slug.vtt`, plus
`qc_report.md` and `qc_sheet.jpg`.

A **video project** looks like this:

```
my-video/
├── project.json      # slug, fps, size, voice, rate, scene order, chapters
├── narration.json    # [{ id, text }] — pipes "|" split subtitle blocks
├── theme.css         # every colour, as CSS variables
├── frames/           # one HTML per scene; <id>.beats.js is generated, never hand-edited
├── audio/  render/  research/  script/
└── out/              # MP4, covers, SRT/VTT, QC report
```

---

## Why not screen recording

Most "HTML to video" tools launch a browser, play the animation and record the screen. That breeds
a whole class of **intermittent** bugs — the animation played before recording started, a web font
loaded late so half the video used the wrong typeface, the first frames captured the pre-animation
state.

`html-explainer` does not record. It **seeks**: position the GSAP timeline at that instant
(`tl.pause(t, false)`), sync every CSS animation (`document.getAnimations().currentTime`), wait
two animation frames, screenshot. Frame 1204 of one render is pixel-identical to frame 1204 of the
next — so QC can point-sample, a single scene can be re-rendered alone, and a whole class of timing
bugs becomes impossible.

The trade-off: **every animation must be seekable.** Wall-clock animation (`setInterval`,
`requestAnimationFrame` counters, CSS `transition` entrances) cannot work and is rejected by
`lint_frames.py`.

---

## Features

| | |
|---|---|
| **Beats anchored to narration** | Scenes position animation by **matching subtitle text** (`B('block text')`), never by hardcoded frame numbers. Edit the script and the whole video re-times with zero scene-code changes. |
| **Word-boundary subtitles** | Timing comes from the TTS engine's **character-level timestamps**, never interpolated by character count — in Chinese two phrases of equal length can differ 3× in duration. `WordBoundary` for edge-tts, `sentence.words[]` for Volcano Engine. |
| **Two voiceover engines** | `edge-tts` (free, no key, default) or **Volcano Engine TTS 2.0** (better quality, needs an API key). Both emit an identical manifest, so nothing downstream changes — switch with `--provider`. |
| **The API key never reaches the agent or the repo** | The Volcano key lives only in `tts.env` (gitignored) and **only the interface package reads it** — the agent calls `tts_volcano.py` and never needs the key. Errors are redacted, `check_integrity.py` enforces a secret guard, and packaging excludes key files. |
| **Two-level clock** | Frame length uses MP3 **container duration** (keeps A/V in sync); the final subtitle block ends on **actual speech end**. |
| **23 visual styles** | 8 categories, each with its canvas, type scale, timeline and colour discipline recorded. No designing from a blank page. |
| **Dual covers** | Every video ships a 16:9 cover plus an **independently re-laid-out** 3:4 cover — not a crop. Cropping loses 57.8% of the width. |
| **Pre-render audit + QC** | `lint_frames.py` reports contract violations before you spend render time; `qc_check.py` checks loudness, drift and samples frames. |
| **Structurally offline** | GSAP vendored; browser auto-detected; ffmpeg falls back to the `imageio-ffmpeg` static binary; web fonts are banned by contract. |

---

## Pipeline

```mermaid
flowchart LR
    A["Topic"] --> B["Research<br/><i>every figure sourced</i>"]
    B --> C["narration.json<br/><i>pipes split subtitle blocks</i>"]
    C --> S["tts_setup.py<br/><i>ask engine · key · voice</i>"]
    S --> D["tts_build.py<br/><i>edge-tts / Volcano to MP3 + word boundaries</i>"]
    D --> E["timeline_build.py<br/><i>global axis + stitched track</i>"]
    E --> F["subs.py<br/><i>subs.json, srt/vtt, beats.js</i>"]
    F --> G["frames/*.html<br/><i>one scene per line, styled from the library</i>"]
    G --> H{"lint_frames.py<br/>eight contract rules"}
    H -->|fail| G
    H -->|pass| I["render_video.mjs<br/><i>seek per frame to PNG</i>"]
    I --> J["ffmpeg<br/><i>H.264 + AAC mux</i>"]
    J --> K[("out/slug.mp4")]
    I --> L["qc_check.py<br/><i>loudness, drift, contact sheet</i>"]
    K --> M["cover_build.mjs<br/><i>cover_169.png, cover_34.png</i>"]

    style K fill:#1f6feb,color:#fff
    style H fill:#8957e5,color:#fff
    style M fill:#238636,color:#fff
```

---

## The `B()` beat system

`subs.py` emits one `beats.js` per scene, exposing each subtitle block by its **source text**, so
scene animation can be anchored directly to the moment words are spoken:

```js
tl.fromTo('.card',    { y: 60, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.7 }, B('right-hand card'));
tl.fromTo('.verdict', { scale: 0.8 },          { scale: 1, duration: 0.6 },        B('the verdict') + 0.2);
```

`B('block text')` is the moment those words start being spoken; `Be('block text')` is the moment
they finish.

This is this project's own design, and it is the part that changes how the work feels: edit the
narration once, re-run three commands, and every scene re-times itself. Compare with hardcoded
frame numbers — one edited sentence means re-aligning the entire video by hand.

**Fallbacks are forbidden.** `B('x') || 3.2` hides "beat not found" behind a stale number. A miss
should fail the build — a mis-timed video is far worse than a failed build.

---

## Visual style library

**Do not design scenes from a blank page.** 23 styles across 8 categories, each recording its
canvas, type scale, timeline structure and colour discipline — full catalogue in
[`references/style-catalog.md`](references/style-catalog.md) (Chinese).

It covers bold signal cards, luxurious minimal whitespace, NYT-grade data charts, Swiss grid,
glitch art, film light leaks, fluid hero backgrounds, brand logo outros, VFX text cursors, 9:16
social formats, product promos and more.

Two classes, with very different adaptation costs:

- **`rich` (12)** — single file, pure CSS `@keyframes`. The seek renderer drives them **with no
  changes**; adaptation is three steps: swap web fonts for a system stack, lift bottom elements out
  of the subtitle band, drop in real content.
- **`gsap` (11)** — multiple compositions loaded from a CDN. **Do not port the code.** Take only
  the visual DNA and re-express it in CSS keyframes.

Rotate 2–4 styles per project. Eight scenes sharing one look reads as monotonous.

---

## Dual covers

Every video ships **two covers that are siblings, not crops**. Cropping 16:9 to 3:4 leaves 810px of
1920px — **57.8% of the width is gone**, and any full-width headline gets sliced in half. So both
share one visual DNA, but each is **laid out again from scratch**:

| Element | 16:9 (`1920×1080`) | 3:4 (`1440×1080`) |
|---|---|---|
| Paradox visual | Right side, side by side | Top, stacked vertically |
| Hook | Bottom-left, two lines, ≥96px | Bottom, three lines, ≥120px |
| Max characters per line | 7 | 5 |

`new_project.py` generates the templates for both sizes directly; output is 2× by default. Full
rules and the pre-upload checklist: [`references/cover-guide.md`](references/cover-guide.md)
(Chinese).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Every frame is a frozen first frame, no error | Timeline not registered on `window.__tl`; or `page.evaluate` received a **string** instead of a function literal (Playwright evaluates it once, so the body never runs) | Pass a real function literal |
| Video comes out 1280×720 | `viewport` was passed to `browser.launch()` — it is a *context*-level option | Pass it to `newPage()` |
| Cover renders at 1× | Same trap, `deviceScaleFactor` twin | Pass to `newPage()` + `screenshot({ scale: 'device' })` |
| Numbers render but never move | The seek suppressed `onUpdate` callbacks | Renderer fixed (`pause(t, false)`); use a transform-based number reel in scenes |
| `No such file or directory` on Windows | Non-ASCII path — Windows ffmpeg reads UTF-8 as ANSI | Keep paths ASCII |
| Subtitles drift / land in the wrong place | TTS returned no word timestamps, so `subs.py` fell back to **character-count interpolation** (a single stderr warning) | Check whether `tts_build` printed `⚠ no word timestamps`; switch to a supported voice (zh/en Doubao 2.0) |
| Volcano error `resource ID is mismatched with speaker related resource` | `speaker` got a display name instead of a voice ID; or a cloned voice paired with the preset resource ID | Use a built-in voice name/ID (the package resolves it); for cloned voices set `VOLC_RESOURCE_ID=seed-icl-2.0` |
| Volcano `HTTP 401/403` | Wrong key in `tts.env`, or the service is not enabled | Verify `VOLC_API_KEY`; check the masked status via `tts_setup.py --status` |
| Volcano `network unreachable` | The package **bypasses the system proxy by default** (China-mainland endpoint) | If you really need a proxy, set `VOLC_PROXY=http://127.0.0.1:<port>` |
| Subtitles sit one frame late after a re-run | A cache hit dropped the head-trim amount (historical bug, fixed) | Upgrade to v1.3.0+; the cache format now carries `lead_cut_sec` |

**`references/lessons.md` is the most valuable file in this repository.** 56 numbered entries, each
one a bug where "the video looked fine but was wrong" — including how it was misdiagnosed at first.
Read it before debugging from scratch.

---

## Who this is for

**Good fit:** turning articles, docs or a topic into narrated video at scale; already using an AI
coding agent and preferring to describe visuals in HTML rather than learn motion software; needing
reproducible output; needing to run offline or refusing per-render fees.

**Poor fit:** live-action editing, talking-head footage, re-creating an existing video; wanting a
drag-and-drop editor (scenes are code, deliberately); wanting React component animation as the
authoring model — that is the domain of the reference project
[`anything2explainer`](https://github.com/Vincentwei1021/anything2explainer).

---

## Reference project ideas

`html-explainer` did not invent its methodology. It has two clear sources of ideas. Both are
**independent projects by different authors — not the same author as this one**, and this
repository neither bundles nor depends on any of their code at runtime. What was carried over is
design specification and engineering experience.

- [**Vincentwei1021/anything2explainer**](https://github.com/Vincentwei1021/anything2explainer)
  (TypeScript / Remotion) — topic in, narrated explainer video out. What this project inherited
  from that line is the **narration and A/V-sync methodology**: word-boundary subtitles, the
  two-level clock, speech-rate calibration, and the QC criteria.
  *Difference:* it is Remotion plus React component animation; this project is HTML/CSS/GSAP plus
  deterministic seeking.

- [**nexu-io/html-video**](https://github.com/nexu-io/html-video) (Apache-2.0, by the Open Design
  team) — HTML to real MP4 on your own machine. What this project inherited from that line is the
  **23-style visual catalogue**, transcribed from its template design specifications. Seven of
  those styles trace further back to MIT-licensed design work.
  *Difference:* it relies on real-time recording; this project seeks frame by frame, so output is
  reproducible.

**This project's own parts:** the deterministic seek renderer, `B()` beat anchoring, the dual-cover
system, and the criteria in `lint_frames.py` / `qc_check.py`. Full attribution and the per-style
mapping are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) (Chinese).

If you want React component animation or Studio-style visual collaboration, go straight to the two
projects above. If you want to edit one sentence without re-aligning the whole video by hand, and
you want frame-level reproducibility, use this one.

---

## Contributing

Issues and PRs are welcome. The most valuable contribution is a **diagnosed silent failure** added
to `references/lessons.md` — write down how it first misled you, the evidence that proved the cause,
the fix, and the general rule that follows. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first
(Chinese).

---

## Licence and acknowledgements

[MIT](LICENSE) © 2026 Moh

MIT covers the original code and documentation. Bundled third-party components and the derived
style specifications remain under their own terms; GSAP is bundled under GreenSock's
[standard "no charge" licence](https://gsap.com/standard-license). Full notices are in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) (Chinese).

---

<div align="center">

If this project helps you, feel free to buy the author a coffee ☕

<img src="https://raw.githubusercontent.com/OneMoh/html-explainer-demos/main/images/wechat-reward-qr.jpg" width="220" alt="Moh's reward QR code">

</div>
