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
- [`desktop-score-runtime-footprint.md`](desktop-score-runtime-footprint.md):
  measured internal desktop score footprint, duplicated dependency evidence,
  inference-only checkpoint opportunity, safe pruning order, and parity
  gates.
- [`family-workspaces-and-attribution.md`](family-workspaces-and-attribution.md):
  implemented managed performer profiles, fast shared-piano selection, and
  explicit creator-versus-performer attribution, with shareable multi-space
  roots retained as the next bounded extension.
- [`generative-musical-response-and-accompaniment.md`](generative-musical-response-and-accompaniment.md):
  proposed deterministic and model-assisted responses to player-created
  melodies, spanning backing-band play, symbolic arrangement, optional audio
  renders, source separation, provenance, rights, and staged experiments.
- [`home-hosted-family-sharing.md`](home-hosted-family-sharing.md):
  accepted near-term Mac-hosted family deployment through the home Pi/Caddy,
  with on-demand availability, local persistence, proportionate access
  boundaries, and explicit triggers for reconsidering cloud infrastructure.
- [`live-acoustic-transcription.md`](live-acoustic-transcription.md):
  browser prototype whose strict-onset decoder, room gate, physical keyboard,
  grand-staff stream, confidence controls, and source-timing guides are
  validated for initial subjective use; target-piano octave overtones remain.
- [`linux-development-portability.md`](linux-development-portability.md):
  reproducible x86_64 Linux development and inference evidence, current
  platform-neutral fixes, and the unresolved CPU-only Transkun packaging and
  same-process live-scheduling gaps.
- [`long-session-storage-retention.md`](long-session-storage-retention.md):
  policy and validation work for predictable long-session disk use, with
  ordinary session data separated from bounded, disposable local debug data
  and an interim MP3-retention path scheduled inside Phase 4 for measured R4
  review.
- [`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md):
  deferred PostgreSQL, object-storage, managed-identity, worker, tenancy, and
  sync architecture retained as a future option rather than the current
  implementation sequence.
- [`natural-language-musical-editing.md`](natural-language-musical-editing.md):
  proposed selection-scoped correction and composition workflow that turns
  typed, spoken, played, or direct-manipulation intent into previewed,
  versioned performance, notation, or arrangement edits.
- [`nvidia-accelerated-low-latency-pipeline.md`](nvidia-accelerated-low-latency-pipeline.md):
  proposed native Windows RTX 4090 ceiling experiment for CUDA Transkun
  correction, opt-in score-model acceleration, scheduler latency sweeps,
  concurrent GPU behavior, and hosted premium-tier cost evidence.
- [`performance-to-notation.md`](performance-to-notation.md):
  evaluated downstream conversion prototype whose artifacts are inspectable
  but whose first target-piano score failed the readability goal.
- [`playful-piano-learning.md`](playful-piano-learning.md):
  proposed separate Play product surface spanning caregiver-and-toddler
  cause-and-effect, ear-led imitation and invention, notation bridges,
  acoustic turn-taking, low-latency MIDI games, studio discovery, and
  cross-device offline delivery.
- [`practice-companion-product-vision.md`](practice-companion-product-vision.md):
  proposed musical-notebook direction joining quiet practice capture,
  moment-centered reflection, readable engraving, cautious tool-backed
  analysis, trusted collaboration, and teacher review.
- [`session-workspace-management.md`](session-workspace-management.md):
  accepted v2 foundation for explicit New, session history, separate
  active/selected identities, recoverable deletion, and future continuation.
- [`windows-native-runtime-portability.md`](windows-native-runtime-portability.md):
  proposed native Windows Python/model and unpackaged local-server baseline,
  aligned with later Tauri sidecar and model-pack work without opening desktop
  packaging yet.

## Update Policy

- Read the relevant topic before changing the behavior it governs.
- Update it when status, contracts, evidence, validation, gaps, or recommended
  direction change.
- Keep the main text as current truth rather than an append-only diary.
- Keep detailed per-slice execution in `docs/tactical/`.
- Link relevant code, reference material, and tacticals so future work starts
  from the right boundaries.
- Create a sibling topic instead of turning an existing topic into a catch-all.
