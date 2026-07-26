# Linux Development Portability

Topic: linux-development-portability

Status: **the ordinary locked environment, full unattended regression gate,
production frontend build, native PortAudio capture, Basic Pitch TFLite
inference, real Transkun CPU correction, and a complete shared-workbench
replay pass on x86_64 Linux as of 2026-07-26. The isolated internal score
runtime installs, but real score generation is blocked by a source-note/MIDI
ordering mismatch owned by the active score-alignment tactical. A real Chrome
fake-microphone run also exposes correction backlog and a client Stop timeout
when CPU inference shares the local server process. The host-independent
worker, Stop, and measured-degradation changes now pass on macOS, but their
mandatory Linux rerun has not happened.**

## Scope

This topic owns evidence and small fixes needed to develop and exercise the
current local applications on Linux. It does not claim Linux desktop
packaging, accelerator parity, microphone-device coverage, or model-quality
equivalence with the measured Apple Silicon environment.

The hybrid product shape, cross-platform sidecar and model-pack contracts,
and eventual desktop release order remain owned by
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md).
Model quality and backend comparison remain owned by
[`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md).

## Reproducible Result

The validation host reported Linux 7.0.0, x86_64, glibc 2.39, Python 3.10.19,
uv 0.9.18, Node 25.2.0, and npm 11.6.2. It has an AMD Ryzen AI 9 365 with
10 physical cores and 20 threads, 22 GiB RAM, and integrated Radeon graphics.
The final environment adds Transkun 2.0.1 and PyTorch 2.13.0. Locked installs
succeeded:

```text
uv sync --extra corrected --extra capture --frozen
npm ci --prefix app
```

The canonical unattended gate passed:

```text
uv run atpiano migration-regression
```

Its report recorded:

```text
Python:              86 passed, one upstream deprecation warning
Retained JavaScript: 2 suites passed
Application:         5 Node tests and 23 Vitest tests passed
Contracts:           generated files have no drift
TypeScript:          passed
npm audit:           zero vulnerabilities at high severity
Ruff:                passed
JavaScript syntax:   passed
Git whitespace:      passed
```

The separate Phase 3 production gate also passed:

```text
npm run build --prefix app
```

The build emits a non-fatal large-chunk warning for the pinned
OpenSheetMusicDisplay dependency. That is a frontend delivery optimization,
not a Linux failure.

## Model Execution Evidence

On Linux, Basic Pitch 0.4.0 resolves its packaged TFLite artifact and
`tflite-runtime` rather than the macOS Core ML path. The deterministic
12.31-second fixture completed all of these real-model paths:

```text
uv run atpiano offline INPUT_JSON OFFLINE_OUTPUT
uv run atpiano replay INPUT_JSON REPLAY_OUTPUT --no-wait
uv run atpiano replay-v2 INPUT_JSON V2_OUTPUT --no-wait --preview
```

The offline result scored 0.905 onset F1 at 50 ms against the aligned
fixture, the rolling replay scored 0.900, and the v2 preview session consumed
all 271,436 source frames. These results establish functional execution, not
backend quality or latency parity with Apple Silicon.

The real two-lane path then completed the frozen 42-second musical fixture:

```text
uv run atpiano replay-v2 INPUT_JSON OUTPUT \
  --no-wait --preview --commit --commit-device cpu
```

It consumed all 2,016,000 source frames, flushed the commit horizon to the
audio head, closed every pending tail, and completed five Transkun decodes.
CPU inference totaled 55.72 seconds. Individual decodes took up to 11.82
seconds, so the bounded scheduler correctly entered degraded mode and raised
its source hop from four to eight seconds.

The same fixture completed through `workbench-v3`, its explicit workspace and
session APIs, Stop settlement, and export surface. The product result retained
936 revision rows, 151 committed MIDI notes, and 11 pedal intervals. Against
the aligned MIDI it had 1.0 onset precision, 0.763 recall, and 0.865 F1 at
25 and 50 ms. The earlier macOS record contained 152 notes and 12 pedal
intervals; the project already accepts neural rolling output by declared
tolerances rather than a frozen output hash.

## CPU Runtime Characterization

The Linux result is slower than the earlier Apple M4 Pro result, but the
measurements also show substantial run-to-run variation on this development
host:

| Path | Source | Decodes | Inference total / mean / max |
|---|---:|---:|---:|
| Apple M4 Pro replay baseline | 42.0 s | 8 | 22.455 / 2.807 / 3.105 s |
| Linux direct replay | 42.0 s | 5 | 55.716 / 11.143 / 11.821 s |
| Linux shared-workbench replay | 42.0 s | 5 | 54.353 / 10.871 / 11.647 s |
| Linux direct replay repeat | 42.0 s | 5 | 84.480 / 16.896 / 23.162 s |
| Linux Chrome fake-microphone capture | 63.21 s | 7 | 148.846 / 21.264 / 23.654 s |

The Apple run remains below the four-second base hop and therefore performs
eight decodes. Linux crosses that hop on its first decode, enters the declared
eight-second degraded hop, and performs fewer differently shaped windows.
This is a scheduler-level comparison rather than a controlled processor
benchmark, but it is enough to reject Linux latency parity. The two earlier
Linux paths agree near 11 seconds per decode. The later repeat overlaps the
browser range for its first three decodes and then falls to about 12.5
seconds, so browser activity alone does not explain all of the variance.

`/usr/bin/time -v` measured that repeat at 109.89 seconds wall time, 688.74
seconds user CPU, 107.33 seconds system CPU, 724% aggregate CPU, and
1,791,936 KiB maximum RSS. At the post-run observation the host used the
`amd-pstate-epp` driver, `powersave` governor with
`balance_performance` preference, enabled boost, 54–57 C thermal readings,
17 GiB available memory, and load averages 9.53 / 13.53 / 10.76. This was not
an isolated benchmark, so those figures are context and evidence of
variability, not a causal attribution. A follow-up performance investigation
should control competing load, power, thread count, warm-up, and window shape
and record per-decode CPU, wall, and queue timing.

## Real Browser Capture Evidence

Headless Chrome used the frozen musical WAV through
`--use-fake-device-for-media-stream` and
`--use-file-for-fake-audio-capture`. This was the real React application,
`getUserMedia`, AudioWorklet PCM conversion, binary WebSocket protocol, local
Basic Pitch and Transkun models, live HTTP reads, Stop path, exports, and
recorded-audio player.

At a displayed 24 seconds, the page showed 98 recognized notes, 44 already
corrected, an exact 12-second commit horizon, detected sounding keys, no
alert, and no page-level horizontal overflow. Stop immediately disabled its
button and displayed commit-to-audio-head progress.

The path did not remain operationally real-time. Browser/worklet audio
continued to queue ahead of the server while Transkun CPU inference ran in
the same process. The stopped artifact contains 3,034,112 frames, or 63.21
seconds, and seven commit decodes totaling 148.85 seconds with a 23.65-second
maximum. Stop exceeded the local runtime's hard 90-second wait. The server
eventually completed at a full commit horizon with 1,469 history rows, 228
committed notes, 20 pedal intervals, segmented WAV, MIDI, and a 1,012,269-byte
MP3, but the live page had already entered “Capture needs attention.”

The retained horizon log makes the scheduling mechanism explicit. The server
took 168.63 seconds to accept 63.21 seconds of source audio, or 0.375 times
real-time ingest, and another 23.71 seconds to finish the final decode. At
each commit boundary, the accepted audio head stayed exactly fixed for 16.30,
17.89, 23.54, 23.26, 22.68, 21.75, and 23.71 seconds while `H_commit`
advanced. Those plateaus match the seven recorded decode wall times to within
about 40 ms. Outside a decode plateau, the largest horizon-record gap that
also advanced the audio head was 0.423 seconds.

This is explained by the captured pre-fix call graph, not inferred from CPU
speed:
the WebSocket loop reads one PCM frame, calls
`CorrectedSession.accept_block`, and only acknowledges and reads the next
frame after that call returns. `CorrectedSession.accept_block` invokes every
lane inline, and Lane B invokes `_decode` inline when a boundary is reached.
Therefore any commit decode, on any operating system, temporarily prevents
the server from accepting the next browser PCM frame. A faster machine can
hide the coupling but cannot remove it.

Reload recovery worked: the same session reopened as complete with six
checksummed artifacts and a seekable 63.21-second MP3. Playback advanced from
18.81 to 20.13 seconds and subsequently updated the exact detected-key view at
30 seconds. This proves durable recovery and playback, not acceptable live
Stop behavior.

Do not “fix” this evidence by only increasing the 90-second timer. Model
execution must not starve capture ingest, the accepted-frame count and queued
transport high-water need explicit presentation, and Stop should become a
durable asynchronous operation that a reload can reattach to. The accepted
architecture already places model execution in separate worker processes;
this result is direct evidence for enforcing that boundary in the local
runtime too.

Tactical
[`022-durable-capture-worker-isolation.md`](../tactical/022-durable-capture-worker-isolation.md)
now owns the local implementation and a mandatory rerun on this host.
Tactical
[`023-backend-capability-degradation.md`](../tactical/023-backend-capability-degradation.md)
owns the measured product mode. Until isolated worker execution demonstrates
otherwise, this host should run Basic Pitch provisionally during capture and
defer Transkun until after Stop.

## Host-Independent Remediation Awaiting Linux

The local implementation now keeps model calls out of the microphone ingest
path. PCM is validated and durably appended before acknowledgement; bounded
preview and commit scheduler threads call separately spawned, warmed model
processes. A commit worker is limited to an explicit Torch thread count.
Commit work that falls behind reads source ranges from segmented audio rather
than relying on the memory ring.

Stop now persists capture-complete `stopping` state and responds before
correction or exports finish. Browser reload observes that same settlement
through ordinary session and horizon APIs. The session retains pipeline lag
and timing summaries, while browser Stop records sent and acknowledged
frames and WebSocket buffered-byte high-water separately. A full server exit
during settlement produces an explicit failed-but-recording-preserved session
on restart; automatic continuation across process exit is not yet claimed.

Automatic correction selection is conservative. With no exact matching
versioned profile, the runtime starts Transkun only after Stop. The new
profiling command records fixture, host, model/checkpoint, scheduler, thread
limit, and raw decode timing samples. A real Apple Silicon run exercised the
command and selected delayed correction, but a profile is host-specific and
does not alter the Linux direction.

These changes remove the known synchronous call path by inspection and pass
blocked-lane, durable-catch-up, worker-exit, prompt-Stop, transport-evidence,
and frontend tests. Only the real Linux Chrome rerun can establish that
native dependencies start, OS scheduling preserves preview responsiveness,
and the browser source head no longer develops decode-shaped plateaus.

## Small Portability Fix

Local workspace and v1 capture copy now say “this device” instead of claiming
that every local runtime is a Mac. The wire shape and local workspace ID are
unchanged. The optional `sounddevice` extra installs on Linux, but the native
adapter also requires the host PortAudio shared library. A missing library now
reports an actionable error. Installing Ubuntu 24.04's `libportaudio2`
exposed the onboard ALC294 input plus PipeWire and Pulse devices. A one-second
physical-input smoke at the device-native 44.1 kHz wrote exactly 44,100 mono
PCM16 frames in 44 sample-clocked blocks with no PortAudio status errors.

## Dependency Footprint

`uv sync --extra corrected --frozen` selected and installed 55 additional
Linux packages, including PyTorch 2.13 and the CUDA 13, cuDNN, NCCL, Triton,
and related NVIDIA stack, even though Transkun ran with `--commit-device cpu`.
PyTorch reports a CUDA 13.0 build but `torch.cuda.is_available()` is false on
this AMD-integrated-GPU host.

Apparent directory sizes on this checkout were about 491 MiB for a fresh
ordinary environment, 4.7 GiB for the corrected environment, and 2.7 GiB for
the separate score runtime. Within the corrected environment, `nvidia`,
`torch`, `triton`, and `transkun` account for about 2.7 GiB, 1.1 GiB,
688 MiB, and 55 MiB respectively. Thus the immediate observed concern is
mostly several gigabytes of download and disk use for accelerator libraries
that this host cannot use.

It is not only a capacity concern for eventual packaging. Shipping those
artifacts also expands dependency resolution, update and vulnerability
tracking, license review, accelerator compatibility, and the model-pack
surface. None of those prevented Linux CPU execution in this validation.

Do not solve this by changing the shared lock or model dependency source
without a bounded decision. A follow-up should choose and validate a
CPU-specific PyTorch source or a separate Linux CPU dependency/model pack,
then run the real corrected fixture and compare its normalized output with
the existing finite Transkun control. The eventual model-pack boundary must
continue to distinguish CPU and accelerator requirements explicitly.

## Score Alignment Blocker

`setup-midi2score` installed the isolated Python 3.11 runtime, pinned upstream
commit, and the checksummed 389,829,880-byte checkpoint. The runtime passed
its manifest inspection, but scoring the completed Linux session failed
before model inference:

```text
ValueError: score input-note order differs from MIDI
```

The selected source list contains two attacks ten source samples apart,
pitch 64 followed by pitch 60. MIDI tick rounding places both at the same
tick, after which the pinned transformer's `midi_to_list` sorts pitch 60
before pitch 64. The new score-input artifact currently sorts by exact source
sample and therefore disagrees at source index 1.

This mismatch is deterministic and is not evidence of Linux/macOS
nondeterminism. The same exact-sample/MIDI-tick collision can occur on either
platform for the same notes; the Linux session merely supplied the first
retained example that exercised it. This is a real gap in the active
[`018-score-playback-alignment.md`](../tactical/018-score-playback-alignment.md)
contract, not a reason to disable its verification guard. The fix must define
the source identity order in the transformer's quantized MIDI order while
preserving exact source samples, then validate chords, near-simultaneous
attacks, and repeated pitches. No published snapshot or corrupt alignment was
produced.

## Remaining Validation

- Run the fixed Chrome fake-microphone acceptance first, then a consentful
  human browser-microphone audition against an actual piano.
- Measure capture-to-event latency by stage on Linux; the accelerated checks
  above intentionally publish no latency claim.
- Generate a Linux backend profile with a controlled thread count and
  competing load recorded; confirm that it selects after-Stop unless new
  evidence supports a less conservative mode.
- Compare browser sent/acknowledged and WebSocket high-water with ingest
  append timing, worker utilization, and correction lag.
- Decide whether interrupted settlement must resume automatically across a
  full server-process restart; it is currently preserved as an explicit
  recoverable stage failure.
- Correct and revalidate the score-input ordering contract before claiming
  real score generation passes.
- Resolve the CPU-only corrected and score-runtime dependency distribution.
- Run a multi-hour real-model soak; the automated longevity lanes continue to
  validate bounded state with fake constant-cost adapters.
- Add a Linux CI lane once its Python, Node, and system-library versions are
  chosen deliberately.
