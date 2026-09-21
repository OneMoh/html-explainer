# Third-Party Notices

`html-explainer` is MIT-licensed (see [LICENSE](LICENSE)). That license covers the
**original code and documentation** authored for this project.

It does **not** cover the third-party components and derived content listed below.
Those remain under their own terms, reproduced here as required.

> **If you redistribute this project (fork, zip, package, mirror, or ship it inside a
> product), you must carry this file along with it.**

---

## 1. Bundled in this repository

### GSAP 3.13.0 — `assets/gsap.min.js`

- **Copyright**: © 2025 GreenSock. All rights reserved. Author: Jack Doyle.
- **License**: GreenSock standard "no charge" license — <https://gsap.com/standard-license>
- **Status**: Bundled verbatim for offline rendering. Not modified.
- **Note**: This is **not** an OSI license. GSAP is free to use, including commercially,
  under its standard license terms. The copyright header inside `assets/gsap.min.js`
  must not be removed. Upstream README is kept alongside it at
  `assets/gsap-README.md`.

---

## 2. Runtime dependencies (installed, not vendored)

These are declared as dependencies and fetched by `bash setup_env.sh --install`.
They are not committed to this repository.

| Component | Version (tested) | License | Upstream |
|---|---|---|---|
| `edge-tts` | 7.2.8 (pinned) | LGPL-3.0 | <https://github.com/rany2/edge-tts> |
| `playwright-core` | 1.63.0 | Apache-2.0 | <https://github.com/microsoft/playwright> |
| `numpy` | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | <https://numpy.org> |
| `pillow` | 12.3.0 | MIT-CMU | <https://python-pillow.org> |
| `imageio-ffmpeg` | 0.6.0 | BSD-2-Clause | <https://github.com/imageio/imageio-ffmpeg> |
| `ffmpeg` (binary) | via `imageio-ffmpeg` | LGPL-2.1+ / GPL-2.0+ (varies by build) | <https://ffmpeg.org/legal.html> |

**A note on `edge-tts` (LGPL-3.0) and `ffmpeg`:** these are invoked as **separate
processes / imported as unmodified libraries**; this project does not statically link
them or ship modified copies. If you plan to redistribute a *bundled* binary build of
ffmpeg, review FFmpeg's own licensing page — build flags determine whether a given
binary is LGPL or GPL.

`edge-tts` is pinned to `7.2.8` intentionally: the 7.x series has had breaking changes
in its speech-boundary API, and this project depends on `WordBoundary` events.

---

## 3. Derived content — the style catalog

`references/style-catalog.md` and `references/style-catalog.json` are a **transcription
of third-party template design specifications** — canvas size, typography, timeline
structure, colour discipline — for 23 named styles. No template source code, markup, or
asset from any upstream is included. Only factual design parameters and style names are
recorded, so that a compatible frame can be authored from scratch.

This catalog was produced by `scripts/import_styles.py`, which reads an installed copy of
html-video and writes the specification out as plain text. **It is a one-time porting
tool.** Running an html-explainer video never reads html-video, and no html-video code is
executed or linked at any point.

### 3.1 `nexu-io/html-video` — 23 templates

- **Copyright**: the html-video authors (Open Design / nexu-io)
- **License**: Apache-2.0
- **Source**: <https://github.com/nexu-io/html-video>
- **What was derived**: design specifications and style identifiers for all 23 templates
  (`frame-bold-poster` … `vfx-text-cursor`), transcribed into `references/style-catalog.*`.
- **Changes made**: specifications reformatted into a flat Markdown/JSON catalog; each
  template classified as `rich` (single-file CSS `@keyframes`) or `gsap` (multi-composition);
  annotated with adaptation cost and subtitle-safe-zone constraints. Original template
  code, compositions, and assets were **not** copied.
- Apache-2.0 requires that recipients of a derivative work receive a copy of the license.
  A verbatim copy is included at [`licenses/Apache-2.0.txt`](licenses/Apache-2.0.txt).
  The upstream repository ships no `NOTICE` file, so no `NOTICE` propagation applies
  (Apache-2.0 §4(d)).

### 3.2 Upstreams of the html-video templates

`references/style-catalog.json` records a `via` field per style, preserving the
provenance that html-video attaches to each of its templates. Seven of the 23 styles
trace back to an earlier MIT-licensed project. Those notices are reproduced here because
this project's catalog describes the same styles.

Exact mapping, as recorded in the catalog:

#### `frontend-slides` — 4 styles

- **Copyright**: Zara Zhang © 2025
- **License**: MIT
- **Source**: <https://github.com/zarazhangrui/frontend-slides>
- **Styles**: `frame-bold-poster`, `frame-bold-signal`, `frame-creative-voltage`,
  `frame-electric-studio`

#### `huashu-design` — 3 styles

- **Copyright**: alchaincyf (花叔 · 花生) © 2026
- **License**: MIT
- **Source**: <https://github.com/alchaincyf/huashu-design>
- **Styles**: `frame-build-minimal`, `frame-pentagram-stat`, `frame-takram-organic`

#### `hyperframes-student-kit` (Nate Herk) — 1 style

- **Copyright**: Nate Herk
- **License**: MIT (as recorded in the catalog's `license` field for this entry)
- **Styles**: `frame-product-promo-30s` — recorded upstream as a fork of
  `linear-promo-30s`, with brand-specific copy and assets replaced by generic
  placeholders.

html-video's own `ATTRIBUTIONS.md` documents the first two upstreams and states its rule
for all such templates: static slide designs were re-expressed as original CSS/SVG
keyframe timelines, with new sample data and no verbatim source copying, and the studio
names attached to some styles (Pentagram, Build, Takram) are recorded as **inspiration
only, never as affiliation or endorsement**. This project inherits that position.

MIT License notice for all three upstreams above:

```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### 3.3 Studio names — inspiration only, no affiliation

Some style names reference real design studios or publications as a record of stylistic
inspiration (Pentagram, Build, Takram, NYT, Vignelli, Swiss Grid). These are **factual
statements of inspiration only**. This project — and html-video before it — is **not
affiliated with, endorsed by, or sponsored by** any of them. No third-party logo,
wordmark, typeface file, or branded asset is included; all frames are authored from
scratch with system fonts.

---

## 4. Design lineage of the workflow

The narration/audio-sync methodology (word-boundary subtitles, two-level clock, speech-rate
calibration, QC criteria) was developed in the author's earlier private projects,
`anything2explainer` and `html-video-workbuddy-driver`. Both are the author's own work.
No code from either is shipped or required at runtime; the names appear only in comments
and historical notes.

---

## Summary for redistributors

| Must ship with your copy | Why |
|---|---|
| `LICENSE` | MIT terms for the original code |
| `THIRD_PARTY_NOTICES.md` (this file) | Apache-2.0 §4 + MIT notice retention |
| `licenses/Apache-2.0.txt` | Apache-2.0 §4(a) requires a copy of the license |
| `assets/gsap-README.md` | GSAP license reference; keep the header in `gsap.min.js` intact |

*Last reviewed: 2026-09-21.*
