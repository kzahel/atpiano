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

The project is in discovery. No model, implementation language, transport, or
deployment runtime has been selected.

Current direction and research questions live in
[`docs/topics/acoustic-transcription-latency-quality.md`](docs/topics/acoustic-transcription-latency-quality.md).

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
