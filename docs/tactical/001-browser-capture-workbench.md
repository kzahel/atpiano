# Browser Capture Workbench

Topic: acoustic-transcription-latency-quality

Status: complete.

## Objective

Add a local browser-first path for the first real acoustic-piano experiments:

1. start one local atpiano server;
2. grant microphone access in the browser;
3. record mono PCM against the browser audio sample clock;
4. stop and audition the captured waveform;
5. submit it to the existing untouched Basic Pitch offline adapter; and
6. open the completed transcription in the existing artifact reviewer.

The user should not need separate record, transcribe, or review commands.

## Bounds

Included:

- one local-only workbench command that opens the browser;
- browser microphone capture through `getUserMedia` and an `AudioWorklet`;
- lossless mono PCM WAV construction without MediaRecorder codec ambiguity;
- explicit browser sample rate and frame-count metadata;
- bounded upload and WAV validation on the Python server;
- one-at-a-time background transcription jobs with visible status;
- persistence of the input manifest and complete run artifacts outside Git;
- recording playback and a compact waveform before submission; and
- automatic handoff to the existing piano-roll run reviewer.

Excluded:

- streaming inference while the musician is playing;
- phone or other LAN capture;
- authentication, HTTPS, or public deployment;
- compressed browser audio;
- cancellation of a model invocation already in progress;
- selecting or converting another model; and
- moving visualization or harmonic analysis into the transcription service.

## Decisions

### Capture boundary

Use a browser `AudioWorklet` as the source adapter. It batches mono
`Float32Array` samples for the page while retaining the `AudioContext` sample
rate and a monotonically increasing source-frame count. The worklet does no
transcription or WAV encoding.

After Stop, the page converts the captured samples to mono 16-bit PCM WAV. It
shows a waveform and browser audio player before the user decides to submit.
This preserves an inspectable recording and avoids the browser-dependent
WebM/Opus formats produced by `MediaRecorder`.

This tactical intentionally runs full-file inference after capture. It does
not claim capture-to-event latency. A future live source can send the same
sample-indexed worklet blocks to the replay scheduler, with an explicit
browser-to-host clock mapping.

### Local server and storage

Add a workbench server bound to `127.0.0.1`. It serves the static capture and
review application, accepts bounded same-origin WAV uploads, creates a
versioned unaligned input manifest, and queues the existing `run_offline`
adapter on one worker.

The default workspace is `results/workbench`, which is ignored by Git. Each
job owns an input directory and run directory. The server exposes only known
static assets, job status, and files beneath the selected completed run.

Do not expose this unauthenticated upload surface on the LAN. Phone capture
will require an authenticated HTTPS transport and explicit clock handling.

### Job behavior

Upload returns a job identifier immediately. The page polls a small JSON
status resource while the server validates, queues, and transcribes the
recording. A completed job supplies a run URL; a failed job supplies a concise
error without a server traceback.

Only one model job runs at a time. This keeps Core ML initialization and model
resource use deterministic enough for the first subjective recordings.

## Planned Validation

- unit-test the browser-WAV input manifest and its mono PCM validation;
- integration-test upload, status polling, completed run access, size limits,
  malformed metadata, and path traversal rejection;
- retain the existing read-only reviewer tests;
- syntax-check both browser JavaScript files;
- run lint and the full Python test suite;
- build the wheel and confirm all workbench assets are packaged;
- exercise a synthetic browser-style WAV through the real Basic Pitch job; and
- record exact commands, evidence, gaps, and recommended next work here before
  completing the tactical.

## Execution Record

### 2026-07-24: browser source and local workbench

The shipped workbench starts with one command:

```text
uv run atpiano workbench
```

It binds only to `127.0.0.1`, opens the system browser, and uses
`results/workbench` by default. The page requests a mono microphone with echo
cancellation, noise suppression, and automatic gain control disabled. It
records the browser's effective settings because a browser or device can
decline those constraints.

An `AudioWorklet` batches 2,048 mono float samples per message. The page
verifies that every message begins at the expected source sample, requires an
acknowledged final flush, and refuses to build a take from a discontinuous
sequence. Stop produces a 16-bit PCM WAV, waveform preview, duration, sample
rate, and local audio player. Nothing reaches the model until the user presses
**Transcribe recording**.

The server requires a same-origin-style local Host header, a bounded
`Content-Length`, `audio/wav`, versioned capture metadata, and a mono 16-bit
PCM file whose sample rate and frame count match the metadata. The 64 MiB
server bound exceeds the page's two-minute maximum at normal browser sample
rates. Every valid submission receives a unique job and run ID. A single
background worker calls the existing unmodified Basic Pitch offline adapter;
completed job links continue to work after a server restart.

This is a file-producing source adapter, not a latency experiment. It retains
the AudioWorklet sample clock but has no browser-to-host monotonic clock
mapping and reports no capture-to-event latency.

### Real adapter-path validation

The deterministic 12.310-second fixture was submitted as a browser-style WAV
to the actual HTTP endpoint and processed by the actual Basic Pitch 0.4.0
worker:

```text
job: 20260724T103400-1bbf61dd9177
run: run-20260724T103400-1bbf61dd9177
audio SHA-256:
39217861396c1bb84ddd883a9f10c63f1be8b8c34462676d87b626916452b043
model inference: 0.395 s
estimated notes: 23
quality available: false
```

The uploaded audio hash exactly matched the deterministic fixture. The run was
correctly unscored because browser input deliberately has no reference MIDI.
The API served its manifest, scores, audio, and reviewer artifacts through the
job-scoped run URL.

### Validation

Commands:

```text
uv run ruff check .
uv run pytest -q
node --check src/atpiano/web/app.js
node --check src/atpiano/web/capture-processor.js
uv build
git diff --check
```

Results:

- 13 unit and HTTP integration tests passed;
- existing read-only reviewer behavior remains covered;
- browser PCM preservation and manifest validation passed;
- malformed metadata, foreign hosts, and artifact traversal were rejected;
- completed artifacts remained discoverable after a server restart;
- both browser JavaScript files passed syntax checks;
- the source distribution and wheel built with all four web assets; and
- the real upload, model, artifact, and status path completed locally.

Browser visual inspection and a real ambient microphone recording were not
performed automatically. Microphone permission, input selection, and
subjective capture quality need to be exercised by the user on the target
piano.

## Gaps And Recommended Next Work

- Record a 20–40 second target-piano take in the workbench, including silence,
  isolated dynamics, repeated notes, chords, bass, treble, legato, and pedal.
- Check whether the browser honors the disabled speech-processing constraints
  and compare its audio with the native `sounddevice` adapter.
- Decide from that recording whether raw-probability heatmaps or threshold
  controls would improve subjective review before adding another model.
- Keep live browser-to-Python streaming as a separate tactical. It requires a
  sample-indexed transport, backpressure, disconnect recovery, and an explicit
  browser-to-host clock mapping before it can report latency.
- Add authenticated HTTPS transport before attempting phone or LAN capture.
