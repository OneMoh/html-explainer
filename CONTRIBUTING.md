# Contributing to html-explainer

Thanks for taking the time to contribute. This document covers the practical things:
how to get a working environment, what the project's hard rules are, and where different
kinds of contributions actually belong.

## Ways to contribute

| Kind of contribution | Where it goes |
|---|---|
| Bug report | [Open an issue](https://github.com/OneMoh/html-explainer/issues/new/choose) using the bug template |
| Rendering / sync bug you diagnosed | Add a numbered entry to `references/lessons.md` **and** fix the code |
| New visual style or a better adaptation recipe | `references/style-catalog.md` notes + a documented example |
| Documentation fix | Direct PR — typo fixes need no prior discussion |
| New feature | Open an issue first so the approach can be agreed before you write it |
| Platform-specific fix (macOS / Linux paths, shell variants) | Very welcome — the project is developed on Windows + Git Bash |

## Development setup

```bash
git clone https://github.com/OneMoh/html-explainer.git
cd html-explainer

# Check the environment, then install anything missing
bash setup_env.sh            # report only
bash setup_env.sh --install  # fetch missing dependencies

# Confirm the toolchain is healthy
node -v && python -V
```

Requirements: Python ≥ 3.9, Node ≥ 18, and either Chrome or Edge (both are almost always
already present). `ffmpeg` is used from `PATH` or falls back to the static binary bundled
with `imageio-ffmpeg`.

### Running an end-to-end check

```bash
python scripts/new_project.py demo --topic "人工智能"
cd demo
# fill narration.json, write frames/*.html, set project.json order
python ../scripts/tts_build.py      --project .
python ../scripts/timeline_build.py --project .
python ../scripts/subs.py           --project .
python ../scripts/lint_frames.py    --project .
node   ../scripts/render_video.mjs  . --preview 30
```

If all of that completes and `out/preview.mp4` plays with synchronised audio, your
environment is good.

## The project's hard rules

These are not style preferences. Breaking them produces silent failures — a video that
renders but is wrong. They are enforced by `scripts/lint_frames.py` where possible.

1. **No external fonts or CDN resources in any frame.** Web fonts are unreachable from
   many networks and time out silently. Use system font stacks only, and reference GSAP
   from the bundled `../assets/gsap.min.js`.
2. **Colours come from `theme.css` CSS variables only.** No hex literals in frame code.
   This is what makes a theme change a one-file operation.
3. **No wall-clock logic.** `setInterval` and `requestAnimationFrame` counters cannot
   work under deterministic seeking. Animate with GSAP or CSS `@keyframes`.
4. **Animate with GSAP timelines, registered on `window.__tl`.** The renderer seeks this
   timeline once per frame; without it, nothing animates.
5. **Position animations with `B('block text')`, never hardcoded times.** The fallback
   form `B('x') || 3.2` is forbidden — a missing block should fail loudly at build time,
   not silently reuse a stale number.
6. **Keep the subtitle safe zone clear.** Nothing may render in the bottom 80–170px, and
   entrance paths must not cross it.
7. **Use ASCII paths for all project directories and output files.** Non-ASCII paths break
   ffmpeg on Windows. Project and output names are ASCII; rename for presentation later.

The full contract, with the reasoning behind each rule and the counter-examples that get
a frame rejected, is in [`references/frame-contract.md`](references/frame-contract.md).

## Adding a new lesson

`references/lessons.md` is the most valuable file in this repository. It exists because
this kind of pipeline fails *silently* — a bug produces a plausible-looking video rather
than an error.

A good entry contains, in this order:

1. **The symptom**, as you first observed it — including how it misled you.
2. **The diagnosis**, and the evidence that proved it (a probe, a diff, a measurement).
3. **The fix**, and what to check afterwards to confirm it.
4. **The general rule** this implies, if it implies one.

Number entries sequentially and append. Do not renumber existing entries — they are
referenced from code comments.

## Adding a new visual style

1. Record the specification in `references/style-catalog.md` (canvas, type scale, timeline
   structure, colour discipline) and `references/style-catalog.json`.
2. Classify it as `rich` (single file, CSS `@keyframes` timeline — drivable by the seek
   renderer with no changes) or `gsap` (multi-composition — must be re-expressed, not
   copied).
3. Add an adaptation recipe to `references/template-guide.md` if the style needs anything
   beyond the standard three steps (swap the font stack, lift bottom elements out of the
   subtitle zone, fill in real content).
4. Verify it renders: `node scripts/peek_frame.mjs <project> <id> --at 25,50,85`.

Style identifiers are `kebab-case` and match the pattern already in use (`frame-*`,
`vfx-*`).

## Pull request checklist

Before opening a PR, please confirm:

- [ ] `python scripts/lint_frames.py --project <project>` reports no FAILs for any frame
      you touched
- [ ] You have actually rendered your change. Frame code that "looks right" frequently
      is not — seek-based rendering has its own failure modes
- [ ] Any new lesson is added to `references/lessons.md` with a number
- [ ] No external fonts, CDN references, or hardcoded colours were introduced
- [ ] If you redistributed or re-derived third-party content, `THIRD_PARTY_NOTICES.md`
      is updated
- [ ] `README.md` and `README.en.md` are updated together if user-facing behaviour
      changed

## Commit messages

Conventional Commits are preferred (`fix:`, `feat:`, `docs:`, `chore:`). A body is
encouraged when the change fixes a silent failure — explain what was misbehaving and how
you verified the fix.

## Scope note

This project intentionally does **not** aim to be a framework. It is a pipeline with a
small, boring surface: HTML frames in, MP4 out, with audio-video sync that holds. Features
that add a build system, a plugin API, or a runtime dependency on a cloud service are
generally out of scope — say hello in an issue if you think there's an important exception.

## License

By contributing, you agree that your contributions are licensed under the MIT License
(see [LICENSE](LICENSE)), and you confirm you have the right to submit them. If you are
porting content from another project, add it to `THIRD_PARTY_NOTICES.md` in the same PR.
