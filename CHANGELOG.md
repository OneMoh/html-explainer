# Changelog

All notable changes to `html-explainer` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions before `1.2.2` were private, internal releases. `1.2.2` is the first public
release on GitHub.

---

## [1.2.2] — 2026-09-21 — first public release

### Added

- **`scripts/lint_frames.py`** — static pre-render audit of every scene frame. Checks the
  eight frame-contract rules plus known pitfalls before spending time on a full render:
  external fonts / CDN links, hardcoded colour literals, missing `window.__tl`
  registration, CDN GSAP, wall-clock logic (`setInterval`, `requestAnimationFrame`
  counters), CSS `transition` entrances, `B('…') || number` fallbacks, content intruding
  into the subtitle safe zone, and missing CJK font families.
- **`scripts/peek_frame.mjs`** — single-frame viewer. Seeks one scene to a few time points
  and screenshots them in seconds, so frame design can be judged without rendering the
  whole video. `--at` takes percentages, not frame numbers.
- **Bilingual project README** (`README.md` in Chinese, `README.en.md` in English).
- **Open-source governance files**: `LICENSE` (MIT), `THIRD_PARTY_NOTICES.md`,
  `CHANGELOG.md`, `CONTRIBUTING.md`, `licenses/Apache-2.0.txt`, `.gitignore`,
  `.gitattributes`, GitHub issue/PR templates, and a CI workflow.

### Fixed

- **`speech_end_sec` disagreed between a cold run and a cached re-run** (lessons #31).
  `_result()` measured the already-trimmed output file, so the head-trim amount was
  subtracted twice: a cold run reported `7.541s`, a cached re-run reported `7.696s` —
  a 0.155s discrepancy that broke the "two runs are frame-identical" guarantee and made
  the final subtitle block disappear early. Now stored in post-trim coordinates.

### Changed

- Documentation: `scripts/lint_frames.py` and `scripts/peek_frame.mjs` added to the
  command sequence and the file reference table (both previously undocumented).
- Documentation: the lint stage is now an explicit step in the workflow, between subtitle
  generation and rendering.
- Documentation: removed references to private client projects so the skill can ship
  publicly.
- Documented licensing: the style catalog is derived from Apache-2.0 content and now
  carries full upstream attribution.

### Notes

- Backfilled from field work: preview-render frame deletion (`--keep-frames`), the
  temporary-project technique for re-rendering a single scene, and the cold-open rule
  that a video's first 0.5s must already show its subject (lessons #32–#34).

---

## [1.2.1] — 2026-09-20

Four rendering / QC correctness fixes, all found by instrumenting the renderer rather
than by inspection. See `references/lessons.md` #27–#30.

### Fixed

- **`tl.pause(t)` silently suppressed seek callbacks.** GSAP's signature is
  `pause(atTime, suppressEvents)` and the second parameter defaults to `true`, so any
  `onUpdate` / `onStart` / `onComplete` fired by a seek was dropped. A counter animated
  via `onUpdate` therefore sat frozen at its initial value in the output — no error, no
  warning, correct thumbnail size, and undetectable by static checks. The renderer and
  cover builder now call `tl.pause(t, false)`. The docs additionally steer number
  animations toward a pure-transform "digit strip" that depends on no callback at all.
- **`deviceScaleFactor` passed to `chromium.launch()` was silently ignored.** Both
  `viewport` and `deviceScaleFactor` are context-level options and only take effect on
  `newPage()`. Covers were being written at 1× while the log claimed 2×. The build now
  verifies output dimensions with PIL instead of trusting the log.
- **QC sampling only covered the first quarter of the video.** `qc_check.py` sampled
  subtitle-block start times but sliced `pts[:samples]`, taking the first N blocks rather
  than a spread. A 39-block video sampled 12 blocks covering only 0.25–23.86s, leaving six
  late scenes completely unchecked while reporting "all passed". Sampling now steps evenly
  across the full range.
- **Cover layout was being measured mid-animation.** Verification ran straight after page
  load, so it read `fromTo` start values instead of the settled layout and reported
  phantom offsets. Measurement now sets `__MG_RENDER__` and seeks to `tl.duration()`
  first, matching the cover builder exactly.

---

## [1.2.0] — 2026-09-20

### Added

- **Dual-cover system.** Every finished video now produces two independently laid-out
  covers instead of one: `cover_169.png` (1920×1080, 3840×2160 output) for the feed and
  player, and `cover_34.png` (1440×1080, 2880×2160 output) for profile grids.
  - `scripts/cover_build.mjs` — cover renderer reusing the scene renderer's deterministic
    seek core, with three deliberate differences: no subtitle layer, a single seek to one
    "cover moment" (`--at last` by default) rather than per-frame stepping, and 2× output
    by default.
  - `assets/cover-template.html` — cover template with the three required elements
    documented in its header.
  - `references/cover-guide.md` — re-layout comparison table, sizing rules, upload
    strategy, and a self-check list.
- `scripts/new_project.py` now scaffolds both cover HTML files into a new project.

### Notes

- The two covers are **sibling layouts sharing one visual DNA, never a crop pair**.
  Cropping 3:4 out of 16:9 discards 57.8% of the frame width (1920 → 810px), which
  guarantees a headline hook gets cut. The re-layout changes the composition itself:
  the paradox visual moves from side-by-side on the right to a vertical stack on top,
  and the hook goes from two lines to three.

---

## [1.1.0] — 2026-09-20 — first packaged release

### Added

- Core pipeline: `new_project.py` → `tts_build.py` → `timeline_build.py` → `subs.py` →
  `render_video.mjs` → `qc_check.py`.
- **Deterministic seek renderer** (`render_video.mjs`). Instead of screen-recording a
  live page, every frame is produced by seeking the GSAP timeline (`tl.pause(t, false)`)
  and synchronising CSS animations (`document.getAnimations().currentTime = t*1000`)
  before screenshotting. This eliminates the entire class of live-recording failures:
  no playback-start race, no font-load timeout, no unstable lead-in.
- **`B('block text')` beat sync.** Frame animations are positioned by matching subtitle
  block text rather than hardcoded frame numbers, so editing narration re-times the whole
  video without touching a single frame file.
- `scripts/subs.py` — three subtitle outputs (runtime JSON, SRT/VTT sidecars, and the
  in-frame layer injected by the renderer) plus generated `beats.js` per scene.
- `scripts/make_theme.py` — four presets plus topic-word colour derivation, writing a
  single `theme.css` source of truth for all colours.
- `scripts/qc_check.py` — stream, duration, loudness, and sampled-frame auditing with a
  contact sheet.
- `scripts/import_styles.py` — one-time porting tool that transcribes template design
  specifications into `references/style-catalog.md` / `.json`.
- 23-style visual catalog across 8 categories, classified by adaptation cost.
- `setup_env.sh` for first-time environment checks and `--install` for fetching missing
  dependencies; `package_skill.py` for portable zips.

[1.2.2]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.2
[1.2.1]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.1
[1.2.0]: https://github.com/OneMoh/html-explainer/releases/tag/v1.2.0
[1.1.0]: https://github.com/OneMoh/html-explainer/releases/tag/v1.1.0
