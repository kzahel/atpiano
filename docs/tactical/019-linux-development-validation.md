# 019 — Linux Development Validation

Topic: linux-development-portability

Status: complete on 2026-07-26. Full installation and execution exposed one
score-input ordering blocker owned by active tactical 018 and one local
capture/worker scheduling blocker; neither was hidden by a timer or weakened
guard here.

## Entry Evidence

- The repository had been developed and measured on macOS arm64.
- The migration baseline already defined one unattended regression command,
  while the shared React tactical separately required a production build.
- The ordinary and optional dependency groups were locked but had no recorded
  Linux execution evidence.

## Outcome

A fresh x86_64 Linux clone can install the ordinary locked dependencies, run
the complete unattended regression gate, build the production frontend, and
execute real Basic Pitch offline, rolling, and v2 preview inference through
the packaged TFLite backend. The optional native capture and real Transkun
lanes also execute, and the shared React/local server completes replay,
settlement, explicit API reads, and exports.

Local product copy no longer calls every device a Mac. Current Linux evidence,
limits, and follow-up direction live in
[`../topics/linux-development-portability.md`](../topics/linux-development-portability.md).

## Implementation Scope

- Install the locked ordinary Python and frontend environments without
  changing dependency resolution.
- Run the canonical regression report and the separate frontend production
  build.
- Generate the deterministic aligned smoke fixture and exercise real Basic
  Pitch offline, rolling replay, and corrected-session preview paths.
- Replace hard-coded “this Mac” local-workspace and v1 capture labels with
  platform-neutral “this device” copy.
- Make the optional native capture adapter explain its PortAudio system
  dependency when the `sounddevice` import cannot load it.
- Document the exact fresh-clone gate and distinguish unattended results from
  machine-dependent lanes.
- Install and exercise the real corrected-model dependency resolution.
- Install and inspect the isolated internal score runtime without weakening
  its private-use license restriction.
- Exercise Chrome's fake microphone through the real React, AudioWorklet,
  WebSocket, live-model, Stop, export, recovery, and playback paths.

## Exclusions

- No PyTorch source, Transkun version, model, decoder, or accelerator change.
- No human browser microphone review, real multi-hour soak, Tauri packaging,
  or Linux desktop support claim. Chrome's fake-device permission path is
  covered; a human piano audition is not.
- No score-alignment contract fix after the real runtime exposed an ordering
  mismatch; that continuing slice remains in tactical 018.
- No inference-quality or capture-to-event-latency parity claim against Apple
  Silicon.

## Validation

The locked install and automated gates passed:

```text
uv sync --extra corrected --extra capture --frozen
npm ci --prefix app
uv run atpiano migration-regression
npm run build --prefix app
```

The report at
`results/migration-regression/20260726T141206Z/report.json` recorded 86
passing Python tests, 28 passing application tests, both retained JavaScript
suites, contract drift, TypeScript, dependency audit, Ruff, syntax, and
whitespace as passing. The production Vite build completed with only its
existing OpenSheetMusicDisplay chunk-size warning.

The deterministic fixtures then completed:

```text
uv run atpiano offline ...                  onset F1 @ 50 ms: 0.905
uv run atpiano replay ... --no-wait         onset F1 @ 50 ms: 0.900
uv run atpiano replay-v2 ... --no-wait \
  --preview                                 271,436 source frames
uv run atpiano replay-v2 MUSICAL ... \
  --no-wait --preview --commit              2,016,000 source frames
```

The real Transkun CPU run completed five decodes, flushed `H_commit` to all
2,016,000 frames, closed every pending tail, and recorded 55.72 seconds of
inference. Decode time exceeded the four-second source hop, so the bounded
scheduler entered its expected degraded eight-second-hop mode.

The same musical fixture completed through `workbench-v3`. Its API reported a
complete session and ready exports containing 936 revision rows, 151 committed
notes, and 11 pedal intervals. Aligned onset precision was 1.0, recall 0.763,
and F1 0.865 at both 25 and 50 ms.

The two paths averaged 11.14 and 10.87 seconds per decode, compared with the
recorded M4 Pro's 2.81-second mean. A later instrumented direct repeat recorded
84.48 seconds of inference, a 16.90-second mean, 23.16-second maximum, 109.89
seconds wall time, 724% aggregate CPU, and 1,791,936 KiB maximum RSS. That run
was not isolated from other host activity and is intentionally retained as
variability evidence rather than a clean processor benchmark.

Chrome then exercised the actual browser microphone stack with the frozen WAV
as its fake input. At 24 displayed seconds it showed 98 notes, 44 corrected,
the 12-second commit horizon, sounding keys, no alerts, and no page overflow.
Stop entered visible settlement progress.

That run also exposed the current local execution limit. Transkun shared the
server process, seven CPU decodes totaled 148.85 seconds, and WebSocket input
queued ahead to a final 63.21-second source artifact. The client exceeded its
hard 90-second Stop wait and showed a failure even though the server later
completed all samples and exports. Reload recovered the exact complete
session, six artifacts, a seekable MP3, and synchronized playback/key
inspection. This is successful durability evidence and failed live scheduling
evidence.

The browser session's 1,491-row horizon log proves the coupling. Seven
fixed-audio-head plateaus lasted 16.30, 17.89, 23.54, 23.26, 22.68, 21.75,
and 23.71 seconds. Each matches its inline commit decode wall time to within
about 40 ms. Accepting 63.21 seconds of source took 168.63 wall seconds; final
settlement took 192.35 seconds from the initial horizon row. The WebSocket
handler cannot read the next PCM frame while its synchronous
`session.accept_block` call is running Lane B `_decode`.

The ignored local execution evidence is retained at:

```text
results/linux-smoke/real-corrected/
results/linux-smoke/real-corrected-repeat/
results/linux-smoke/workbench-v3-real/20260726T133716-fc984f3b3450/
results/linux-smoke/browser-mic/20260726T134800-32bbfe25dfff/
```

`uv sync --extra capture --frozen` also installed the optional Python adapter.
Installing Ubuntu 24.04's `libportaudio2` exposed the onboard ALC294 input,
PipeWire, Pulse, and default devices. A one-second native capture at the
device's 44.1 kHz rate produced 44,100 mono PCM16 frames across 44 blocks with
no status errors.

## Dependency Boundary

The corrected install adds 55 Linux packages, including PyTorch 2.13 and the
CUDA 13, cuDNN, NCCL, Triton, and related NVIDIA stack, despite the CPU
execution target. It functions, but the CPU-only source and its parity
evidence remain a separate dependency/model-pack decision. On this checkout,
an ordinary environment is about 491 MiB apparent size, the corrected
environment is 4.7 GiB, and the separate score runtime is another 2.7 GiB.
The immediate pain is download and disk capacity; dependency, security,
license, accelerator-selection, and distribution surface are the additional
packaging reasons not to make the CUDA-heavy environment universal.

## Score Runtime Result

`uv run atpiano setup-midi2score` installed the pinned internal runtime and
verified its 389,829,880-byte checkpoint. Real generation then stopped before
inference because near-simultaneous source notes retain exact sample order
while MIDI tick quantization collapses them to one attack and the transformer
reorders that chord by pitch. The alignment guard correctly rejected the
mismatch and published no snapshot.

This is deterministic conversion behavior, not observed Linux/macOS
nondeterminism. It can occur on either platform whenever distinct exact
attacks collapse to the same MIDI tick.

This is evidence for
[`018-score-playback-alignment.md`](018-score-playback-alignment.md), whose
contract must reconcile quantized MIDI order with exact source identities. It
is not fixed in this portability slice.

## Local Execution Blocker

The real browser result confirms that bounded-memory model scheduling is not
enough when CPU inference competes with ingest and Stop inside one Python
process. A local application worker boundary must keep capture acceptance
responsive, expose queued transport separately from the source audio head,
and make settlement a durable job that a browser reload can resume. Merely
raising the frontend's 90-second timeout would preserve the starvation and
hide the wrong failure.
