## What this changes

<!-- One or two sentences. What was wrong, and what does this do about it? -->

## Why

<!--
If this fixes a silent failure, explain what was misbehaving and how you proved the
cause. "I tried X, it still broke; I changed Y, it worked" is genuinely useful here —
this pipeline produces plausible-looking output while being wrong.
-->

## How it was verified

<!--
Not "it should work". What did you actually run?
e.g. `node scripts/peek_frame.mjs . hook --at 25,50,85` and inspected the 50% frame
-->

## Checklist

- [ ] `python scripts/lint_frames.py --project <project>` reports no FAILs for frames I touched
- [ ] I actually rendered the change and looked at the output
- [ ] No external fonts, CDN links, or hardcoded colour literals introduced
- [ ] New lesson (if any) appended to `references/lessons.md` with the next number
- [ ] `python scripts/check_integrity.py` passes
- [ ] `README.md` and `README.en.md` updated together if user-facing behaviour changed
- [ ] `THIRD_PARTY_NOTICES.md` updated if third-party content was added or re-derived

## Related issues

<!-- Closes #... -->
