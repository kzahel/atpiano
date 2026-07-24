# Live Acoustic Transcription

Topic: live-acoustic-transcription

Status: research proposal. Browser recording plus full-file transcription is
runnable, but browser audio is not yet sent to the model while the pianist is
playing. No live implementation is authorized or selected.

## Scope And Relationship

This topic owns the live user path:

- sample-indexed browser-to-host audio transport;
- session clocks, buffering, backpressure, gaps, and reconnect behavior;
- scheduling rolling inference while capture continues;
- provisional, revised, committed, and retracted UI behavior;
- a final full-file reconciliation pass after Stop; and
- measured capture-to-browser-display latency.

[`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md)
continues to own model adapters, raw model evidence, transcription quality,
and the general latency/quality benchmark. This topic applies those contracts
to a user-operated browser session. The downstream piano-roll or notation
consumer remains separable and must also accept direct MIDI.

## Desired Experience

The near-term target is not instrument-control latency. It is a useful piano
roll that begins filling while the pianist plays:

- show credible provisional onsets in roughly the existing one-second
  live-feedback band;
- revise offsets, velocities, false positives, and window-edge estimates as
  more context arrives;
- stabilize older notes according to an explicit commit horizon; and
- after Stop, run the exact full-file path that already sounded useful to the
  user and backfill the final result.

This deliberately separates **time to first useful feedback** from **time to
best available transcript**. A genuinely causal model may later improve the
first lane without changing the browser or event contracts.

## Current Evidence

### Deterministic replay

The existing rolling Basic Pitch adapter processed two-second model windows on
the Apple M4 Pro with 0.029-second median inference, while matched first-visible
latency was 0.961 seconds p50 and 1.310 seconds p95. Compute throughput is not
the immediate limit; future context, scheduling, edge handling, and commit
policy dominate.

Basic Pitch's official
[`inference.py`](https://github.com/spotify/basic-pitch/blob/main/basic_pitch/inference.py)
uses fixed 43,844-sample model inputs, overlapping windows, and an offline
decoder. It is not a causal streaming model. Reapplying it to a growing or
rolling buffer is still a valuable prototype, provided the resulting latency,
edge errors, and revisions are reported honestly.

### First target-piano take

The user's `kyle test recording.wav` is byte-identical to workbench job
`20260724T104057-1c108a0915e3`:

```text
SHA-256:
3d747d653d8f7a30c2e3261c85b8b9207959a7e00e8b009aac5fd969247f6f47
format: mono PCM16 WAV, 48,000 Hz
duration: 34.688 s
peak: -4.25 dBFS
RMS: -21.94 dBFS
clipped samples: 0
```

Basic Pitch 0.4.0 produced 133 notes from pitch 45 through 76 with velocity 39
through 109. Model inference took 0.497 seconds and complete artifact creation
took 0.973 seconds. The user judged the result as pretty good.

This is valuable target-room evidence, but it has no aligned MIDI. It cannot
establish precision, recall, pedal accuracy, or whether a rolling result is
close enough to the full-file output.

## Proposed Live Architecture

```text
AudioWorklet
  source frame + PCM block
          |
          v
binary WebSocket transport ----> gap / backpressure evidence
          |
          v
host ring buffer + source/host clock mapping
          |
          +----> rolling preview scheduler
          |             |
          |             v
          |       provisional/revised notes
          |             |
          v             v
lossless session WAV -> normalized event stream -> browser consumer
          |
          v
exact full-file pass after Stop
          |
          v
final reconciliation / backfill
```

The browser should continue using an
[`AudioWorklet`](https://www.w3.org/TR/webaudio-1.1/) so each block has a
source sample position. It should send binary PCM blocks through the standard
[`WebSocket`](https://websockets.spec.whatwg.org/) API with a small versioned
header containing session, sequence number, first source sample, frame count,
sample rate, and client clock observations.

The AudioWorklet must never wait on the network. The page observes the
WebSocket queue, applies a bounded backpressure policy outside the render
thread, and makes any dropped range an explicit gap. The host stores the
lossless session waveform independently of rolling inference so every live
run can be replayed.

Musical time remains the audio sample clock. Periodic clock exchanges should
fit offset and drift between the browser and host monotonic clocks. Browser
paint acknowledgement is required to measure capture-to-visible latency; a
server send timestamp alone measures only part of the experience.

## Revision And Backfill Contract

The live UI should consume the normalized event lifecycle already established
by the benchmark:

- `provisional`: useful recent estimate that may move or disappear;
- a higher revision of the same stable identity: corrected onset, offset,
  velocity, confidence, or other supported attributes;
- `committed`: past the declared rolling commit horizon; and
- `retracted`: a provisional identity removed by later evidence.

The final full-file result may differ even from rolling committed notes. That
is not an ordinary live revision; it is a named **final-pass reconciliation**.
The UI and artifact should preserve both what was visible live and what became
the best final transcript. Stable matching should minimize distracting note
replacement while never hiding disagreements in evaluation.

## Model Lanes

Research reviewed on 2026-07-24:

| Lane | Evidence | Constraint | Proposed use |
|---|---|---|---|
| Existing rolling Basic Pitch | Already runs locally; deterministic replay is near the one-second band | Offline network and backward-looking decoder, no pedal | First preview/backfill feasibility lane |
| [NeuralNote](https://github.com/DamRsn/NeuralNote) | Apache-2.0 native Basic Pitch implementation documents why CQT context, inference, and backward note construction prevent true real time | Records then transcribes rather than streaming | Implementation evidence, not a new model |
| [Streaming onset/offset/pedal model](https://arxiv.org/abs/2503.01362) | ISMIR 2024 method explicitly separates onset and active-note offset decoding and validates sustain pedal each frame | No clean public checkpoint and runnable repository were confirmed | Most directly aligned research candidate if artifacts appear |
| [Minimum-latency causal audit](https://arxiv.org/abs/2509.07586) | Audits hidden non-causality, reports the quality cost of strict causality, and describes a released research baseline | Public code/checkpoint acquisition still needs confirmation | Important causal comparator, not yet an adapter |
| [Mobile-AMT](https://eurasip.org/Proceedings/Eusipco/Eusipco2024/pdfs/0000036.pdf) | Small in-the-wild piano model reported at 174 ms | The later audit identifies global pooling over a ten-second block and future-dependent post-processing | Do not accept its headline latency without reproducing the causal path |
| [Onsets & Velocities](https://github.com/andres-fr/iamusica_demo) | Released onset/velocity model and live demo | Common published configuration uses about 5.5 seconds of context and omits offsets/pedal | Optional onset-only deadline comparator |
| [online_amt](https://github.com/jdasam/online_amt) | Older MIT online piano system with a web visualizer | PyTorch 1.6-era environment and no current portability evidence | Legacy reference only |

An efficient 2025
[sparse-attention sequence-to-sequence implementation](https://github.com/WX-Wei/efficient-seq2seq-piano-trans)
has released checkpoints, but its documented inference is CUDA/FlashAttention
and full audio-to-MIDI rather than the separate streaming onset/offset/pedal
model. It is an offline/final-pass research candidate, not evidence that the
streaming paper is runnable.

No current evidence justifies starting with Linux/NVIDIA. The existing Core ML
path has enough local throughput for the first transport/window/reconciliation
experiment. Accelerator-specific models can later run behind the same adapter
boundary, locally or on a network host, after they beat a measured baseline.

## Alternatives Considered

### Wait for a genuinely streaming model

This avoids adapting an offline model, but blocks feedback on checkpoint
availability and integration work. It also leaves browser transport, clocks,
event revision, and final backfill untested. Those contracts are needed for
any model.

### Re-run the whole growing recording

This is the simplest conceptual prototype but repeats increasing work and
changes the context of every prior note. It is acceptable only as a tiny
diagnostic. The first measured implementation should use bounded windows and
preserve native output per window.

### Send `MediaRecorder` chunks

Encoded WebM/Opus chunks simplify bandwidth but introduce codec framing,
delay, browser variability, and sample-coordinate ambiguity. Lossless
sample-indexed mono PCM is a better first LAN/loopback experiment. Codec
transport can be tested later against the PCM control.

### Run inference inside the browser

This could eventually remove host transport latency, but it combines model
conversion, browser runtime, device variability, and streaming policy in one
experiment. Python on the current Mac is the smaller first boundary.

## Observed Workbench Disconnect

The reported `ConnectionResetError: [Errno 54] Connection reset by peer`
occurred in `_send_file` while the server was writing an artifact body to a
browser socket. The associated job and all transcription artifacts completed.
This is consistent with a browser cancelling an audio range request during
seek, source replacement, or navigation; it is not a model or recording
failure.

A later maintenance patch should treat `BrokenPipeError` and
`ConnectionResetError` during response-body writes as an ordinary client
disconnect and stop sending that response without a traceback. It should have
a focused HTTP test. This proposal records the issue but deliberately does not
change the running server.

## Recommended Direction

Use the current browser and Basic Pitch path to answer the architecture
question before adopting another model:

1. prove sample-exact browser-to-host transport with deterministic replay and
   no model;
2. connect the existing rolling adapter and sweep a small hop/guard/commit
   matrix;
3. compare what was visible at 250 ms, 1 second, and 3 seconds against the
   exact full-file output;
4. run the exact offline adapter after Stop and test stable final backfill; and
5. only then bake off a truly causal or pedal-aware streaming model whose code,
   checkpoint, license, and real look-ahead can be verified.

This is the fastest route to interactive evidence without pretending Basic
Pitch is permanently suitable or truly causal. The proposed bounded slice is
[`003-live-browser-transcription-spike.md`](../tactical/003-live-browser-transcription-spike.md).

## Required Measurements

- input sample continuity and explicit gaps;
- capture buffer, transport, receive, resample, scheduler, inference,
  reconcile, delivery, and browser-paint timing;
- source-onset-to-provisional and source-onset-to-committed p50, p95, and max;
- precision, recall, and F1 visible at 250 ms, 1 second, and 3 seconds;
- provisional revision/retraction rate and time to stability;
- final-pass disagreement and parity with untouched offline output;
- CPU, memory, inference queue, and WebSocket queue high-water marks; and
- silence, room noise, repeated notes, chords, pedal, bass, treble, Stop tail,
  disconnect, and reconnect behavior.

## Open Questions

- Is roughly one-second provisional feedback already satisfying in practice?
- Should provisional notes appear faded, outlined, or indistinguishable until
  revised?
- May the final pass revise rolling-committed notes, and how should that be
  explained visually?
- What hop and commit horizon best preserve the current target-piano quality?
- Does pedal-aware streaming matter more than improving note-onset latency?
- When a remote accelerator is tested, is raw LAN PCM still acceptable or
  does codec latency and reliability become the next frontier?
