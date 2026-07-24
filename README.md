# atpiano

Atpiano is an experimental acoustic-piano transcription service. It listens to
a nearby piano, turns the captured audio into timestamped note events, and
makes those events available to a piano roll or other consumers with useful
quality at real-ish latency.

The first goal is not to select a permanent model or build the final user
interface. It is to measure the latency/quality frontier of available
transcription models and the effects of windowing, overlap, look-ahead,
batching, post-processing, execution backend, and recording conditions.

## Project Boundary

Atpiano owns:

- timestamped audio capture or ingestion from a local microphone or a remote
  phone;
- acoustic-piano transcription;
- reconciliation of overlapping or revised model output; and
- a normalized, timestamped note-event stream.

A separate visualization and analysis program will consume those events. It
will also accept direct MIDI from an enabled keyboard, so harmonic, chord, and
piano-roll behavior does not depend on acoustic transcription.

The first implementation should be a deterministic live-replay benchmark. It
will replay aligned recordings at wall-clock cadence, exercise models as if
audio were arriving live, and report both transcription quality and
capture-to-event latency. Live Mac microphone and phone streaming are later
input adapters to the same pipeline.

## Project Status

The project is in discovery. Python and Spotify Basic Pitch are the first
prototype stack, not permanent selections. A deterministic MIDI-derived
fixture, untouched offline reference, wall-clock replay benchmark, and local
artifact reviewer are runnable on Apple Silicon.

Current direction and research questions live in
[`docs/topics/acoustic-transcription-latency-quality.md`](docs/topics/acoustic-transcription-latency-quality.md).

## Prototype Quick Start

Use the pinned Python 3.10 environment:

```text
uv sync
```

For microphone recording, include the optional capture dependency:

```text
uv sync --extra capture
uv run atpiano devices
uv run atpiano record \
  ../atpiano-artifacts/my-piano \
  --seconds 30
```

The recording manifest has no aligned MIDI and is therefore explicitly
unscored. It can still be passed to `offline`, `replay`, and `review` for
subjective inspection.

Generate a deterministic MIDI-derived WAV and aligned reference:

```text
uv run atpiano fixture ../atpiano-artifacts/smoke-input
```

Run the untouched Basic Pitch file path:

```text
uv run atpiano offline \
  ../atpiano-artifacts/smoke-input/input.json \
  ../atpiano-artifacts/offline
```

Or replay the same samples at real wall-clock cadence:

```text
uv run atpiano replay \
  ../atpiano-artifacts/smoke-input/input.json \
  ../atpiano-artifacts/replay
```

Review a completed run in the local browser UI:

```text
uv run atpiano review ../atpiano-artifacts/replay
```

Generated inputs, checkpoints, recordings, and run results do not belong in
Git. Each run records hashes, runtime/model versions, parameters, stage timing,
native outputs, normalized event revisions, scores, and a compact report.

## Project Map

- [`docs/topics/`](docs/topics/README.md) — focused, living decisions, evidence,
  gaps, and recommended direction
- [`docs/tactical/`](docs/tactical/README.md) — bounded implementation plans and
  execution records
- [`AGENTS.md`](AGENTS.md) — repository guidance for coding agents
- [`topics.md`](topics.md) — commit-series topic string log

## Working Principles

- Measure end-to-end latency from the audio sample clock to emitted note
  events; model inference time alone is not product latency.
- Preserve raw model output and timing evidence so post-processing can be
  compared without rerunning inference.
- Keep source timestamps separate from arrival and display timestamps.
- Treat recent acoustic events as revisable when a model needs future context.
- Compare against an offline/full-context quality ceiling before optimizing a
  streaming path.
- Keep model checkpoints, datasets, recordings, and generated benchmark
  artifacts outside Git.
