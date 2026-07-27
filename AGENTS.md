See [`README.md`](README.md) for project context.

## Notes for agents

Focused, living topic docs live under `docs/topics/`. Before working on a
continuing concern, read the relevant topic and update it when the work changes
its status, contract, evidence, validation, gaps, or recommended direction.
Create a sibling topic instead of broadening an existing one into a catch-all.

Implementation tactical docs live under `docs/tactical/` and use zero-padded
numeric filenames such as `000-topic.md`, `001-next-topic.md`. A tactical owns
one bounded implementation slice and becomes its execution record when the
slice lands. Completed tacticals are historical evidence; current topic docs
own continuing guidance.

The temporary public application is an on-demand macOS service. After
completing and validating a code change that affects the shared live
application, run `scripts/share-atpiano-service status`. If the service is
active, restart it with `scripts/share-atpiano-service restart` and verify the
public homepage and capability API. Do not start an inactive service merely
because code changed. The service commands are intentionally unsupported on
Linux; report that the live restart was skipped when validation occurs there.

Documentation roles:

- Architecture and reference docs own durable system shape and external facts.
- Topic docs own current truth for a focused continuing concern.
- Tactical docs own bounded implementation slices and execution records.

When a commit series implements a documented topic, normally reuse the topic
filename's slug in its `Topic:` trailers. This is a convention, not a
one-to-one requirement.

## Transcription research guardrails

- Establish a reproducible offline result before adapting a model for rolling
  or streaming inference.
- Report capture-to-event latency separately from preprocessing, scheduling,
  inference, post-processing, transport, and delivery time.
- Use the audio sample clock as the source timeline. Do not infer event time
  from packet arrival or model completion time.
- Preserve model-native probabilities or frame outputs when practical. Do not
  make decoder thresholds impossible to re-evaluate.
- Treat window edges as suspect. Overlap, reconcile, and report the commit
  policy used for every result.
- Evaluate silence, room noise, repeated notes, dense chords, sustain pedal,
  low bass, and high treble in addition to aggregate dataset metrics.
- Keep model checkpoints, datasets, captured audio, and benchmark output out of
  Git. Record acquisition URLs, versions, licenses, and checksums in tracked
  manifests or documentation.
- Do not claim a model is real-time from throughput or inference time alone.
  Measure its full algorithmic look-ahead and the end-to-end event delay.
- Keep accelerator-specific code behind an execution boundary. Apple, CUDA,
  AMD, and CPU experiments must consume and produce the same model-adapter
  contracts.

## Commit Message Guidance

Aim for a <=65 char subject, and strictly enforce a 72-column line wrap for
the body. Prefer bullet lists in the commit body when items are numerous or
complex; use prose when the content is short and simple.

For non-trivial commits, include a concise synthesis of the originating
instruction or motivating observation. Summarize the motivating request and
key implementation direction so a maintainer could re-derive something close
to the intended result. Prune secrets, digressions, and low-signal chat detail.
Mechanical or small self-evident changes are exempt.

When a commit is part of a related series, append one or more
`Topic: <string>` trailers at the bottom of the body. Reuse the exact topic
string across the series so `git log --grep "Topic: ..."` finds the chain.
Use multiple trailers when a commit spans multiple established topics.
Standalone commits with no expected follow-up need no trailer.

Keep the repository-level [`topics.md`](topics.md) log of topic strings. Scan
it before opening a series and append each new topic when the series begins.
