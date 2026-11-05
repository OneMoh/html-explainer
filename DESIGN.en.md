# Design and implementation

> The deep end of [`README.en.md`](README.en.md): **why** things are done this way, and the
> constraints that get violated over and over if they are not written down.
>
> - How to use it → [README.en.md](README.en.md)
> - Commands and confirmation points → [SKILL.md](SKILL.md)
> - Bugs already paid for (133 entries) → [references/lessons.md](references/lessons.md)

**Contents**

1. [Why not screen recording](#why-not-screen-recording)
2. [The `B()` beat system](#the-b-beat-system)
3. [Visual style library](#visual-style-library)
4. [Motion library](#motion-library)
5. [Style orchestration](#style-orchestration)
6. [Multi-format covers](#multi-format-covers)
7. [Measured rendering](#measured-rendering)
8. [Voice details](#voice-details)
9. [Where the ideas came from](#where-the-ideas-came-from)

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
`lint_frames.py`. It is exactly why the motion library is built as "`t` → a set of numbers": a pure
function is seekable by construction.

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

Rotate 2–4 styles per project. Eight scenes sharing one look reads as monotonous — and the
orchestrator does that rotation for you (below).

---

## Motion library

`assets/motion.js` (exposed as `window.HXM` in the browser) abstracts the actions that recur across
the 23 templates into **40+ action words**, in five groups:

| Group | Actions (excerpt) |
|---|---|
| `enter` | `riseWord` `dropLetters` `springIn` `blurAway` `riseFromMask` `typeChars` `checkOff` `flyPlane` |
| `carry` | `morphBox` `irisOpen` `diveInto` `arcHop` `gatherTo` `railShift` `sealDisc` `burstWord` |
| `contact` | `landHit` `splitOnHit` `tapPress` `pointer` `stretch2` `sim.*` (magnet / follow / soft-body / rope) |
| `camera` | `camTrack` `layerMatrix` `depthBlur` `whipPan` `camShake` `slowPush` `gridDots` + coordinate conversion |
| `ambience` | `swiftSpring` `glowField` `floodRings` `noiseField` (5 colour ramps) `beltLoop` |

Every action is **`t` (absolute seconds) → a set of numbers**: stateless, touching neither the DOM
nor a canvas, so it can be **seeked frame by frame** — the same `t` always yields the same numbers.
All randomness goes through `seededRng`, and `Math.random()` **never appears on the render path**,
so frame-by-frame rendering matches live preview. `tests/test_motion.mjs` holds 148 assertions.

Authoring a scene is no longer a matter of hand-tuning easing curves from scratch: you pick from
this vocabulary, combine and parameterise — a scene is usually a few layers of "entrance + carry +
a touch of camera + ambience" stacked together. Full vocabulary in
[`references/motion-library.md`](references/motion-library.md) (Chinese).

---

## Style orchestration

`scripts/style_director.py` **reads the narration itself**, infers what role each scene plays
(opener / statement / data / mechanism / evidence / contrast / close / outro), scores a **primary
style** by role × sub-category × duration × content words × audience × pace, attaches **accent
styles** to selected scenes for local element replacement, and decides opener **variants** (rotated
by a topic hash) and **transitions** (driven by the energy delta between neighbouring scenes):

```bash
# dry-run first to inspect the result, then drop --dry-run to write it
python scripts/style_director.py --project . --dry-run
python scripts/style_director.py --project . --mood calm --pace slow --audience general --pin hook=bold-signal
```

The emitted `style-plan.json` carries `role / primary / motion_intensity / transition_out / why` per
scene — "why this scene got this style" is inspectable. Diversity constraints (a cap on the number
of styles, a cap on consecutive repeats, opener ≠ second scene) plus `--pin` hard constraints stop
it from degenerating back into one-style-per-video. `--seed` gives the same topic a fresh set of
scenes each time, while `--band 0` is fully deterministic (for regression). Full rules in
[`references/style-director.md`](references/style-director.md) (Chinese).

**The test:** if the output can be recognised as "that's the bold-signal template", absorption went
too far; if all you can say is "the colours feel like X, the pace like Y", the depth is right. The
point is to let the template serve the topic, not the other way round.

---

## Multi-format covers

Every video ships **covers that are siblings, not crops**. Cropping 16:9 to 3:4 leaves 810px of
1920px — **57.8% of the width is gone**, and any full-width headline gets sliced in half. So all
formats share one visual DNA, but each is **laid out again from scratch**:

| Element | 16:9 (`1920×1080`) | 3:4 (`1440×1080`) | 9:16 (`1080×1920`) |
|---|---|---|---|
| Use | Feed / watch page | Profile grid | Full-screen vertical / RedNote / WeChat Channels |
| Layout | Side by side | Top, stacked vertically | Three bands, weight high |
| Hook | Bottom-left, two lines, ≥96px | Bottom, three lines, ≥120px | Lower-middle, three lines, ≥130px |
| Max characters per line | 8 | 8 | 6 |
| Margins | 96px all round | 110px all round | top ≥180px · bottom ≥160px · sides ≥90px |

**16:9 + 3:4 ship by default; add 9:16 for vertical placements** — just add
`frames/cover_916.html`; the builder **skips any format whose frame is missing**. On 9:16 the top
and bottom margins are **reserved zones, not safety margins**: the top carries the account/duration
layer, the bottom the title bar and action buttons.

Templates are generated by `new_project.py`; output is 2× by default. After rendering, run the
**final-state geometry check** — the eye only catches blatant problems, while a 20px bleed or a
one-character orphan line does not:

```bash
node scripts/cover_build.mjs .          # → out/cover_{169,34,916}.png
node scripts/check_cover.mjs .          # margins / hook size / line width / orphans / no two columns on 9:16
```

Full rules and the pre-upload checklist: [`references/cover-guide.md`](references/cover-guide.md)
(Chinese).

---

## Measured rendering

A real **3 min 20 s · 1080p30 · 5982-frame** video (this machine: Windows 10 · 16 logical cores ·
Chrome · 6 browser processes · shutter 180°/8 samples, enabled on 3 scenes only = 35.3% of frames):

| Stage | `--png-fast` (default) | `--jpeg --jpeg-quality 95` |
|---|---|---|
| Capture (5982 frames · 11995 samples) | 365.4 s | 365.8 s |
| Shutter integration | 67.1 s | 63.0 s |
| Encode + tail | 36.8 s | 31.9 s |
| **End to end** | **469.2 s ≈ 7 min 49 s** | 460.7 s ≈ 7 min 41 s |
| Output size | **10.81 MB** | 11.02 MB |

Derived: **16.4 frames/s** average capture throughput across the film, **30.5 ms** average per
capture (including scene switches and preload); **26.65 frames/s** peak throughput once a scene is
warm. **Shutter eats only 13.7% of the time** — because it lands on just 35.3% of the frames.

### Where the speed comes from (largest lever first)

1. **`--workers N`, true multi-process** — capture is pure CPU work and scales with cores.
   `--concurrency` does nothing (intermediate-frame encoding is serial inside the browser process;
   measured throughput at concurrency 1/3/6 is 1.80 / 1.86 / 1.87 frames/s).
2. **Switching the intermediate-frame channel** — an encode-side lever on par with parallelism;
   on graphics frames `png-fast` means "same speed + smaller + lossless".
3. **`--shutter-only` whitelisting** — shutter is the only item you pay for by a multiple. Enable it
   only on scenes that need the streak; every other scene costs zero: here 35.3% of frames had
   shutter on, yet they account for only 13.7% of the time.
4. **`--profile draft` + `--preview`** — while iterating, render just a section with shutter off and
   get a preview in seconds.

> The numbers above are an **end-to-end measurement of one real film**, which is more trustworthy
> than a synthetic micro-benchmark — micro-benchmarks lack the signal-to-noise to predict
> whole-film tail costs. Absolute values vary a lot with machine and frame content; after changing
> machines, render your own film twice on one channel to calibrate a baseline.

### The full intermediate-frame picture

| Channel | Relative speed (graphics frames / full-frame photos) | Quality | Size (1080p graphics frames) | Position |
|---|---|---|---|---|
| **`--png-fast`** ★**default** | **×1.02 / ×4.4** | **pixel-lossless** | **0.10 MB/frame** | Same speed as JPEG q95 on pure CSS/MG frames, smaller → the default |
| `--jpeg --jpeg-quality 95` | ×1.00 / **×13** | PSNR 41.65 dB (below the final encode's own distortion) | 0.12 MB/frame | First choice when frames contain **full-frame photos / heavy compositing, or for 4K finals** |
| `--png` | ×1.16 / ×1.0 | pixel-lossless | 0.08 MB/frame | Only for `legacy` reproduction / the `master` profile |
| `--jpeg --jpeg-quality 82` | fastest | slightly lower | ~0.08 MB/frame | Previews only |

> **Calibration trap: the "×13 / ×4.4" figures are full-frame *photo* ratios — do not apply them to
> graphics frames.** The vast majority of videos made with this skill are **pure CSS/MG graphics
> frames** (large flat colour areas plus crisp text), and PNG's deflate is extremely efficient on
> those — measured, **JPEG q95 and PNG-fast run at the same speed** (27.14 vs 26.65 frames/s, ×1.02),
> and PNG-fast is **smaller and lossless**. That is why the default is `--png-fast`;
> `--jpeg q95` only wins when frames contain **photos / a 4K final** (fine PNG on photo frames is a
> 582 ms/frame black hole).
>
> End-to-end cost: on the same 5982-frame video, JPEG q95 measured 460.7 s and PNG-fast **measured
> 469.2 s (+1.85%)** — pixel-lossless costs almost nothing, and the output is 0.21 MB smaller.

Full profile table, how to read the benchmarks, and the shutter disk guard:
[`references/render-profiles.md`](references/render-profiles.md) (Chinese).

---

## Voice details

Before the pipeline starts the agent **asks which TTS you want**, then lists candidate voices for
you to pick from (or you can just hand it a voice ID). Both engines emit an **identical**
`audio-manifest.json`, so the timeline, the subtitles and the renderer **all stay untouched** —
switching engines is a one-field change.

### Volcano Engine voices

Built-in voices (full list in the [official voice docs](https://docs.volcengine.com/docs/6561/1257544)):

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

## Where the ideas came from

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

**This project's own parts:** the deterministic seek renderer, `B()` beat anchoring, the **motion
library** (`assets/motion.js`), the **style orchestrator** (`style_director.py`), the **render
profile and channel system** (quality/frame rate/shutter/parallelism,
`references/render-profiles.md`), the multi-format cover system (and its geometry checker), and the
criteria in `lint_frames.py` / `qc_check.py`. Full attribution and the per-style
mapping are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) (Chinese).

If you want React component animation or Studio-style visual collaboration, go straight to the two
projects above. If you want to edit one sentence without re-aligning the whole video by hand, and
you want frame-level reproducibility, use this one.
