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
- [`browser-only-wasm-deployment.md`](browser-only-wasm-deployment.md):
  candidate static, offline-capable deployment that moves capture,
  transcription, persistence, and export into the browser; the exact ONNX
  artifact executes under a web WASM runtime, while real-browser parity and
  end-to-end behavior remain unvalidated.
- [`live-acoustic-transcription.md`](live-acoustic-transcription.md):
  browser prototype whose strict-onset decoder, room gate, physical keyboard,
  grand-staff stream, confidence controls, and source-timing guides are
  validated for initial subjective use; target-piano octave overtones remain.
- [`performance-to-notation.md`](performance-to-notation.md):
  evaluated downstream conversion prototype whose artifacts are inspectable
  but whose first target-piano score failed the readability goal.

## Update Policy

- Read the relevant topic before changing the behavior it governs.
- Update it when status, contracts, evidence, validation, gaps, or recommended
  direction change.
- Keep the main text as current truth rather than an append-only diary.
- Keep detailed per-slice execution in `docs/tactical/`.
- Link relevant code, reference material, and tacticals so future work starts
  from the right boundaries.
- Create a sibling topic instead of turning an existing topic into a catch-all.
