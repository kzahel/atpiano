# Browser Capture Workbench

Topic: acoustic-transcription-latency-quality

Status: active.

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

Pending.

