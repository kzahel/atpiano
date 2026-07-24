# Live Replay Benchmark

Topic: acoustic-transcription-latency-quality

Status: in progress.

## Objective

Build the smallest reproducible Python harness that can:

1. establish an untouched Spotify Basic Pitch offline result;
2. generate and recover a deterministic MIDI-derived audio fixture;
3. replay timestamped audio at wall-clock cadence;
4. retain native model output, normalized revisable events, and stage timing;
5. score offline and replay results against aligned MIDI; and
6. present machine-readable artifacts in a compact report and local review UI.

This tactical is an evidence-producing prototype. It does not select the
permanent model, runtime, capture transport, application server, or downstream
analysis program.

## Bounds

Included:

- a pinned `uv` Python 3.10 environment;
- versioned input and run manifests;
- a deterministic reference MIDI and repository-owned audio renderer;
- one unmodified Basic Pitch 0.4.0 offline adapter;
- a Basic Pitch rolling-window replay adapter using the same released model;
- source-sample and per-stage monotonic timing;
- raw model activations and normalized event history;
- onset, offset, frame, and latency summaries;
- a compact local browser artifact reviewer; and
- a microphone recording command whose output feeds the same file pipeline.

Excluded:

- phone or network audio transport;
- a polished or product-owned piano roll;
- chord, harmonic, or score analysis;
- model conversion or training;
- a second runnable model adapter; and
- claims of real-time fitness based only on inference throughput.

## Decisions

### Environment

Use Python 3.10 managed by `uv`. Basic Pitch 0.4.0 officially supports Python
through 3.11 and recommends Python 3.10 on Apple Silicon. Pin the dependency
and preserve the generated lockfile rather than resolving a moving environment
for each run.

The first host is an Apple M4 Pro with 48 GiB RAM. Basic Pitch's official Core
ML wrapper requests CPU-only execution, so initial measurements describe that
reference implementation rather than Apple GPU or Neural Engine potential.

### Deterministic fixture

Generate a Standard MIDI File with deliberately separated diagnostics:

- isolated notes across low, middle, and high registers;
- a repeated note;
- intervals and a dense chord;
- overlapping legato notes;
- varied velocities; and
- a sustain-pedal interval.

Render it with a repository-owned seeded harmonic synthesizer. The renderer is
not intended to sound like a production piano. Its job is to make fixture
generation free from an untracked soundfont and exactly repeatable. Preserve a
hash of both the MIDI and rendered WAV in the input manifest.

### Basic Pitch reference behavior

The offline adapter calls the released `basic_pitch.inference.predict` API
without changing the model, windowing, decoder thresholds, or post-processing.
It retains the returned `note`, `onset`, and `contour` matrices before
normalization.

Basic Pitch 0.4.0 uses 43,844-sample inputs at 22,050 Hz, corresponding to just
under two seconds, and removes overlap around window edges. The stock file API
is offline: it processes every window before decoding one transcript.

An open upstream issue documents cumulative drift when concatenated raw frames
are treated as a uniform sample-indexed array. Store raw frames with explicit
source-window coordinates; do not infer their source sample solely from the
concatenated row number.

### Review UI

Keep the local browser reviewer independent from transcription. It reads a run
directory containing audio and JSON artifacts and has no model dependency.
The initial reviewer supports audio playback, a reference/prediction piano
roll, an event table, and timing/quality summaries. It is a debug tool, not the
future visualization and harmony consumer.

### Capture

Microphone capture is an input adapter only. It writes sample-clocked mono WAV
plus an input manifest and does not run inference in the audio callback. No
ambient recording is made during automated validation.

## Artifact Contract

Every generated run directory will contain:

- `run.json` — schema version, source identity and hashes, Git revision,
  runtime/model/backend versions, parameters, device, commands, and status;
- `timing.jsonl` — source sample boundaries and monotonic stage spans;
- `raw/` — model-native arrays and their sample-coordinate metadata;
- `events.jsonl` — normalized event revisions and lifecycles;
- `prediction.mid` — final decoded transcript;
- `scores.json` — machine-readable quality and latency measurements;
- `report.md` — compact human-readable result; and
- referenced audio and reference MIDI paths or copies selected by the command.

Large inputs and generated run directories remain ignored by Git.

## Planned Validation

- unit tests for MIDI fixture identity, rendering determinism, matching,
  lifecycle reconciliation, latency calculations, and manifest validation;
- two identical fixture generations must have identical SHA-256 values;
- an offline Basic Pitch run on the fixture must produce a readable MIDI,
  nonempty raw arrays, normalized events, scores, and report;
- replay must wait for required source samples and record nonnegative
  note-onset-to-emission timing for emitted notes;
- the local reviewer must load a completed run without a Python model process;
- lint and full test suite; and
- record exact commands, observed runtime, gaps, and recommended next work here
  before completing the tactical.

## Execution Record

Not yet executed.

