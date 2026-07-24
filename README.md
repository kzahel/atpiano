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
browser capture/transcription workbench are runnable on Apple Silicon.

Current direction and research questions live in [`docs/topics/`](docs/topics/README.md).
Acoustic-model benchmarking, live browser transcription, and downstream
performance-to-notation conversion have separate owners there.

## Browser Workbench

Use the pinned Python 3.10 environment:

```text
uv sync
```

Then start the one local server:

```text
uv run atpiano workbench
```

The command opens a browser page. Grant microphone access, press **Start
recording**, press **Stop**, listen to the captured waveform, and press
**Transcribe recording**. The completed audio, MIDI, normalized events, raw
model output, run report, piano roll, and first readable score appear in the
same page.

The score view shows its tempo, beat, meter, key, quantization, and hand-split
assumptions. Change them and press **Regenerate local score** to retain and
review another interpretation. Score rendering uses a pinned
OpenSheetMusicDisplay bundle from a CDN, so it needs internet access; the
MusicXML artifact remains downloadable if that bundle is unavailable.

The same page supports a consentful two-phase comparison with Ivory:

1. download and submit the original WAV to test Ivory's complete
   audio-to-score pipeline;
2. download and submit the atpiano prediction MIDI in a separate Ivory job to
   test its notation conversion with note detection held constant; and
3. import each unedited MusicXML result into its labeled workbench lane.

The workbench does not upload audio automatically or handle Ivory accounts,
payments, or credentials. Imported oracle scores remain under the ignored
local run directory.

The workbench binds only to `127.0.0.1` and stores generated artifacts under
the ignored `results/workbench` directory by default. Browser takes are
limited to two minutes and the server accepts at most 64 MiB per upload. A
recording has no aligned MIDI, so its quality metrics are explicitly unscored;
the piano roll is for listening and subjective inspection.

This path performs full-file inference and score generation after Stop. It
does not yet transcribe while the piano is being played and makes no
capture-to-event latency claim. Notation is a separate artifact consumer and
does not change the acoustic model output.

## Benchmark Commands

The lower-level commands remain available for reproducible experiments.

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

The native fixed-duration capture adapter is also retained for instrumentation
experiments:

```text
uv sync --extra capture
uv run atpiano record ../atpiano-artifacts/my-piano --seconds 30
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
