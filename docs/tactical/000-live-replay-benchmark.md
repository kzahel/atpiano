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

### 2026-07-24: environment and offline reference

Commands:

```text
uv lock
uv sync
uv run pytest -q
uv run atpiano fixture results/smoke-input-v2
uv run atpiano offline \
  results/smoke-input-v2/input.json \
  results/offline-basic-pitch-v2
```

The final generated `deterministic-midi-smoke-v2` fixture identities were:

- MIDI SHA-256:
  `84326c3ce5131b4a475a9bd3205fc289a995182e82cbf51b716e5958d540cf12`
- PCM WAV SHA-256:
  `39217861396c1bb84ddd883a9f10c63f1be8b8c34462676d87b626916452b043`

Basic Pitch 0.4.0 loaded its shipped Core ML package and completed locally on
the M4 Pro. The model artifact tree hash was
`4b0c371ebc032c02caa4103c26578c6544ca8e7b2b98c5b2ed09a8b5b85e5f48`.
The first process observed 5.179 seconds inside the stock `predict` call. A
second process observed 0.400 seconds after macOS had compiled or cached the
model. Runs therefore record no warm-up and an uncontrolled backend-cache
state; both cold and warmed distributions are needed before drawing a latency
conclusion.

The 19-note deterministic fixture produced 23 estimates:

| Metric | Precision | Recall | F1 |
|---|---:|---:|---:|
| onset, 50 ms | 0.826 | 1.000 | 0.905 |
| onset, 25 ms | 0.826 | 1.000 | 0.905 |
| note with offset | 0.565 | 0.684 | 0.619 |
| frame, 100 Hz | 0.691 | 0.996 | 0.816 |

The smoke test establishes that the released package runs and recovers every
fixture onset within 25 ms, but it is not a near-lossless MIDI round trip:
four false onsets remain, decoded offsets are substantially weaker, and the
model cannot emit the reference sustain-pedal interval. This fixture is a
synthetic plumbing diagnostic, not evidence of acoustic-piano quality.

Environment fixes discovered during execution:

- Basic Pitch's `resampy` dependency still imports `pkg_resources`; add
  `setuptools<81` explicitly because new isolated environments omit or remove
  it.
- Core ML 9 supports scikit-learn only through 1.5.1; pin that compatible
  version to avoid resolving a known-unsupported conversion dependency.
- The 0.4.0 release source differs from current `main`: decoder defaults are
  literal function defaults rather than exported constants. The adapter
  records those exact released values instead of importing unreleased names.

### 2026-07-24: rolling replay

Commands:

```text
uv run atpiano replay \
  results/smoke-input-final/input.json \
  results/replay-basic-pitch-nowait-v3 \
  --no-wait
uv run atpiano replay \
  results/smoke-input-final/input.json \
  results/replay-basic-pitch-realtime
```

Replay delivered 1,024 samples every 46.44 ms against a monotonic deadline.
It reproduced the release's 43,844-sample inputs, 7,680-sample overlap, and
36,164-sample window hop. It retained every window output separately with its
possibly negative source start sample.

The commit policy reserves 10 overlap frames (2,560 samples) at the left edge
and 20 frames (5,120 samples) at the right edge. Center detections commit
immediately. Right-edge detections are provisional and the next overlapping
window either commits a matched pitch/onset or retracts it. The asymmetric
split deliberately gives the provisional lane more future-edge coverage while
the two guards still sum to the complete overlap. The fixture exercised one
provisional-to-committed revision; no retraction happened in this run.

Wall-clock replay produced:

| Measure | Result |
|---|---:|
| onset F1, 50 ms | 0.900 |
| onset F1, 25 ms | 0.850 |
| note-with-offset F1 | 0.450 |
| frame F1, 100 Hz | 0.852 |
| matched first-visible latency p50 / p95 / max | 0.961 / 1.310 / 1.446 s |
| matched committed latency p50 / p95 / max | 1.085 / 1.516 / 1.916 s |
| per-window inference p50 / p95 / max | 0.029 / 0.048 / 0.056 s |
| replay scheduling lateness p50 / p95 / max | 0.005 / 0.005 / 0.042 s |

The host easily keeps up by throughput, but Basic Pitch's future context and
window commit policy dominate event latency. This is concrete evidence for
reporting algorithmic wait separately from inference time.

### 2026-07-24: local artifact reviewer

The reviewer is a dependency-free HTML, CSS, and Canvas application served by
the Python package:

```text
uv run atpiano review results/replay-review-final
```

It reads only completed run artifacts. It provides synchronized audio,
reference and prediction piano rolls, quality and latency cards, lifecycle
counts, provenance, and the complete normalized revision log. Reference and
prediction notes are exported as versioned JSON alongside MIDI so the browser
does not need a MIDI parser or model dependency.

Validation:

```text
uv run pytest -q
node --check src/atpiano/web/app.js
curl http://127.0.0.1:8765/artifacts/run.json
curl -I -H 'Range: bytes=0-99' \
  http://127.0.0.1:8765/artifacts/fixture.wav
```

The server test covers packaged UI assets, artifact delivery, and path
traversal rejection. Manual HTTP validation confirmed byte-range audio
responses. Browser visual inspection was not part of this tactical's automated
validation; the user-facing command opens the local reviewer for subjective
audition.
