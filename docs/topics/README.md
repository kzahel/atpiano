# Topics

Focused, living records of continuing concerns live here.

Prefer the smallest coherent topic whose status, decisions, evidence, and next
work benefit from continuity across sessions or commits. Topic docs own
current truth, decisions, evidence, gaps, and recommended direction. Bounded
implementation slices and their execution records belong under
[`../tactical/`](../tactical/README.md).

New topics should normally begin with a crisp scope, a `Topic: <slug>` line,
and an honest status. When a commit series implements the same concern,
normally reuse the document slug in its `Topic:` trailers.

## Current Topics

- [`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md):
  discovery-stage investigation of acoustic models, streaming adaptations,
  the latency/quality measurement contract, and reproducible benchmarks.
- [`live-acoustic-transcription.md`](live-acoustic-transcription.md):
  proposed browser audio transport, rolling feedback, event revision, latency
  measurement, and final full-file backfill.
- [`performance-to-notation.md`](performance-to-notation.md):
  integrated downstream conversion from performance notes or direct MIDI to
  inspectable sheet music, with editable hypotheses and oracle comparison.

## Update Policy

- Read the relevant topic before changing the behavior it governs.
- Update it when status, contracts, evidence, validation, gaps, or recommended
  direction change.
- Keep the main text as current truth rather than an append-only diary.
- Keep detailed per-slice execution in `docs/tactical/`.
- Link relevant code, reference material, and tacticals so future work starts
  from the right boundaries.
- Create a sibling topic instead of turning an existing topic into a catch-all.
