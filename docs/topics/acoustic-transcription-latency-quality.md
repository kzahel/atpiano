# Acoustic Transcription Latency And Quality

Topic: acoustic-transcription-latency-quality

Status: prototype. No permanent model or runtime is selected. The first
deterministic live-replay benchmark is complete with a Basic Pitch 0.4.0 Core
ML reference, normalized revisable events, timing/quality artifacts, a local
run reviewer, native file-producing microphone adapter, and a local browser
live-transcription/reconciliation workbench. The live lane now uses a measured
strict-onset decoder while the full-file reference remains untouched.

## Scope

This topic owns the acoustic-piano audio-to-note investigation:

- candidate models and reusable implementations;
- offline quality ceilings and rolling/streaming adaptations;
- window, overlap, hop, look-ahead, batching, and reconciliation policy;
- execution backends on Apple, NVIDIA, AMD, and CPU hosts;
- end-to-end latency and transcription-quality measurement; and
- the normalized event boundary exposed to downstream consumers.

It does not own piano-roll rendering, harmonic or chord analysis, score
generation, or MIDI-device capture. Those belong in a separate consumer
program that can accept either atpiano events or direct MIDI. Continuing
performance-to-score research is now owned by
[`performance-to-notation.md`](performance-to-notation.md).

Browser transport, session behavior, live display delivery, and final-pass
backfill are refined in
[`live-acoustic-transcription.md`](live-acoustic-transcription.md). This topic
continues to own the shared model, event, quality, and latency contracts used
by that live path.

## Product Question

What combinations of model, context, scheduler, decoder, hardware, and
recording conditions produce a useful transcription of a nearby acoustic
piano, and where is the quality/latency frontier?

"Real-ish time" is intentionally broader than digital-instrument latency. A
stable piano roll delayed by hundreds of milliseconds or even a few seconds
may be useful. We should measure three experience bands instead of optimizing
for an assumed threshold:

- **responsive:** notes usually become visible within 250 ms;
- **live feedback:** notes usually become visible within 1 second; and
- **delayed live:** notes usually become visible within 3 seconds.

These are experiment buckets, not acceptance promises. The first study should
show whether quality improves materially between them and what users notice.

## Current Prototype Evidence

[`docs/tactical/000-live-replay-benchmark.md`](../tactical/000-live-replay-benchmark.md)
is the completed execution record. The current pinned stack is Python 3.10,
Basic Pitch 0.4.0, and its shipped Core ML model on an Apple M4 Pro with
48 GiB RAM. This is a prototype choice, not a product selection.

The deterministic 19-note MIDI-derived fixture establishes:

- untouched offline onset F1 of 0.905 at both 25 and 50 ms;
- untouched offline note-with-offset F1 of 0.619;
- rolling replay onset F1 of 0.900 at 50 ms and 0.850 at 25 ms;
- rolling replay note-with-offset F1 of 0.450;
- rolling replay first-visible matched latency of 0.961 s p50, 1.310 s p95,
  and 1.446 s maximum;
- rolling replay committed matched latency of 1.085 s p50, 1.516 s p95, and
  1.916 s maximum; and
- per-window inference of 0.029 s p50 and 0.048 s p95.

The host has ample throughput for this model, but the result is in the
live-feedback or delayed-live bands because model context and commit policy
dominate inference time. The synthetic fixture recovers every offline onset
but still produces false notes and weak offsets. It is a plumbing diagnostic,
not acoustic-piano quality evidence.

The rolling adapter retains every native probability window with explicit
source-sample coordinates. It uses a deterministic 10-frame left guard and
20-frame right guard within Basic Pitch's 30-frame overlap. Center detections
commit immediately; right-edge detections emit provisionally and are committed
or retracted against the next window. The fixture exercised one provisional
revision to a committed event.

Aligned inputs receive objective quality scores. Microphone or other inputs
without reference MIDI are explicitly marked unscored while still producing
MIDI, normalized events, native outputs, timing, and review artifacts. The
local reviewer is an independent artifact consumer and does not move piano-roll
or harmonic analysis into the transcription service.

[`docs/tactical/001-browser-capture-workbench.md`](../tactical/001-browser-capture-workbench.md)
adds the first user-operated acoustic input path. One loopback-only server lets
the browser record AudioWorklet PCM, audition a WAV, submit it to the existing
full-file Basic Pitch adapter, and inspect the completed piano roll. The
deterministic fixture completed through the real HTTP/job/model path with an
identical audio hash and 23 estimates. This establishes usability plumbing,
not acoustic-piano quality or live transcription latency.

### First target-piano workbench take

The user exercised the workbench on the target acoustic piano on 2026-07-24
and judged the result as pretty good. The downloaded WAV is byte-identical to
workbench job `20260724T104057-1c108a0915e3`, so a duplicate model run was not
needed:

```text
audio SHA-256:
3d747d653d8f7a30c2e3261c85b8b9207959a7e00e8b009aac5fd969247f6f47
format: mono PCM16 WAV, 48,000 Hz, 34.688 s
peak: -4.25 dBFS
RMS: -21.94 dBFS
clipped samples: 0
Basic Pitch estimates: 133
pitch range: 45–76
velocity range: 39–109
model inference: 0.497 s
artifact completion: 0.973 s
```

This is the first subjective target-piano evidence. It is technically healthy
audio with no obvious clipping, but it has no aligned MIDI and remains
unscored. A duration-and-velocity-weighted pitch-class profile ranked A major
first with correlation 0.907. Tempo evidence was ambiguous: `pretty_midi`
estimated 165.6 BPM while onset-grid candidates were spread across tempo
octaves and phases. Those are analysis hypotheses, not ground truth.

The browser also reset one artifact response while the server was writing its
body. The run and artifacts completed; this was not a capture or model
failure. The response writer now treats `ConnectionResetError` and
`BrokenPipeError` as ordinary client cancellation, and an integration test
confirms that delivery stops without a traceback.

### First live target-take replay

[`docs/tactical/003-live-browser-transcription-spike.md`](../tactical/003-live-browser-transcription-spike.md)
implements the first actual browser-stream contract and rolling model lane.
The AudioWorklet sends sample-indexed mono PCM16 over a same-origin loopback
WebSocket. The server validates continuity, retains exact capture and clock
evidence, runs stock Basic Pitch windows every 250 ms, emits stable revisable
identities, and preserves every native probability window. Stop automatically
runs the untouched full-file adapter and records live-versus-final
reconciliation.

The same 34.688-second target take was sent through the real WebSocket at
wall-clock cadence on the Apple M4 Pro. Its 132 rolling windows produced 140
committed live tracks. The exact-final adapter produced 133 notes; 127 matched
a live note of the same pitch within 80 ms, with six final additions and 13
live removals.

Source-onset-to-first-server-emission latency was 0.428 seconds p50, 1.649
seconds p95, and 1.876 seconds maximum. Matched onset changes from live to
final were 0.006 seconds p50 and 0.034 seconds p95. Offset changes were much
less stable at 0.013 seconds p50 and 0.866 seconds p95.

This supports an onset-first display and shows that local compute can sustain
the selected lane. It does not establish acoustic precision or recall because
the recording lacks aligned MIDI. The replay also did not execute a browser,
so its latency ends at server emission; actual page sessions retain fitted
browser clocks and paint acknowledgements for full delivery timing. Basic
Pitch remains a non-causal portable reference, not a selected live model.

### Target-room onset gate

The first subjective microphone pass confirmed an isolated piano note but also
produced false notes from background sound. Tactical
[`004-noise-gated-onset-display.md`](../tactical/004-noise-gated-onset-display.md)
adds an evidence-preserving live-only gate before reconciliation:

- calibrate the median RMS of 50 ms frames over the first source second;
- require a candidate's -20 through +120 ms onset window to exceed that floor
  by 8 dB;
- clamp the threshold to -48 through -34 dBFS; and
- retain every native probability window and every gate decision.

Re-decoding the preserved windows from the two reported microphone sessions
and applying the gate rejected 256 of 1,902 and 247 of 1,164 overlapping-window
candidates. Their room floors were -55.71 and -61.85 dBFS. By contrast, the
earlier target take calibrated to -60.72 dBFS, its -48 dBFS gate accepted all
1,282 native candidates, and its quietest exact-final onset window measured
-40.57 dBFS.

This is useful target-room separation evidence, not precision or recall.
Candidate counts contain repeats across windows, and none of these microphone
sessions has aligned MIDI. The exact full-file adapter remains untouched so
live-gate misses and final additions remain observable.

### Held-chord decoder failure

The second subjective pass finds the onset-only view more legible but rejects
stock Basic Pitch as a literal onset source. A held chord produces many new
notes and overtone pitches without new attacks. The absolute-energy gate
correctly admits them because sustained resonance remains far above the room
floor.

The behavior exists in both rolling and untouched full-file outputs. The two
latest exact-final results contain 62 and 38 same-pitch re-onsets less than one
second apart. Basic Pitch's stock decoder enables two non-strict paths:
`infer_onsets=True` derives onsets from frame-activation changes, and
`melodia_trick=True` turns remaining frame energy into notes without onset
peaks.

Re-decoding preserved full-file probabilities with both paths disabled reduces
the two held-chord results from 214 to 155 and 137 to 70 notes. Sub-second
same-pitch re-onsets fall from 62 to 39 and 38 to 14. The earlier subjectively
useful take also falls from 133 to 92 notes. Therefore strict decoding is a
promising experiment, not an established improvement: no aligned reference
currently distinguishes removed overtones from removed true notes.

The bounded comparison below tests those decoder paths and thresholds from
retained output before integrating a live policy. Any later active-note
suppression still must preserve repeated strikes and true harmonic intervals;
octaves and fifths are not duplicates merely because they are related.

### Selected strict-onset live baseline

Tactical
[`005-strict-onset-decoder-spike.md`](../tactical/005-strict-onset-decoder-spike.md)
adds a reusable decoder study over retained Basic Pitch arrays. It records
each candidate's explicit onset confidence and whether the official decoder
created it from an onset-head peak, frame-derived inference, or melodia
fallback.

The selected live policy disables inferred onsets and melodia and raises the
onset threshold from 0.5 to 0.6. It recovers all 19 deterministic fixture
onsets with no extras at both 25 and 50 ms. Threshold 0.7 also scores perfectly
on that fixture, but 0.6 is the lowest perfect threshold and is less likely to
delete unaligned acoustic notes. Threshold 0.8 misses one fixture note.

On the unaligned target-room evidence, stock-to-strict note counts and
sub-second same-pitch restarts change as follows:

| Case | Stock | Strict 0.6 |
|---|---:|---:|
| Earlier useful take | 133 / 37 | 81 / 15 |
| Held-chord A | 214 / 62 | 149 / 38 |
| Held-chord B | 137 / 38 | 52 / 10 |

These are decoder-busyness measures, not accuracy scores. No fixed same-pitch
refractory or source attack-novelty threshold was selected: the fixture
protects E4 reattacks 450 ms apart, and the unaligned acoustic examples do not
distinguish every apparent restart from a true strike. A 3 dB source novelty
threshold preserves the fixture but deletes 23 of 81 strict notes from the
earlier subjectively useful take.

The actual rolling Core ML path produces 83 committed identities on that
34.688-second take, close to the 81-note full-file strict decode and below the
previous stock rolling result of 140. The rolling fixture has 18 of 19 onset
matches plus one false estimate; its missing reference begins at 0.5 seconds
and is intentionally suppressed by the live room-calibration period. This
validates the implementation boundary while leaving target-piano accuracy for
controlled or aligned acoustic evidence.

The first strict-onset subjective session,
`20260724T144840-82ee228fd1bf`, completed 473 rolling windows and 154 committed
identities. The user judged it to work “pretty great.” Its remaining observed
failure is a lower-note strike that also activates the octave above on the
resonant target piano. Because this is an explicit learned onset-head response,
not a frame-derived or melodia start, confidence inspection and controlled
low-note/true-octave examples are now more informative than further stock
decoder tuning.

### Octave errors are a model-class property

[`008-score-pipeline-bakeoff.md`](../tactical/008-score-pipeline-bakeoff.md)
tested the reported low-note/upper-octave failure by swapping the model rather
than filtering its output. On the same reference WAV:

```text
model         notes  range  dur_med  dur_p95  octave-sync pairs  sub-s restarts  pedal CC
basic-pitch     133  45-76    0.627    1.875                 17              37         0
transkun         80  47-76    1.153    3.632                  2              11        30
```

Octave-sync pairs are note pairs exactly 12 semitones apart whose onsets fall
within 30 ms. Transkun 2.0.1 is piano-specific, MIT-licensed, pip-installable,
and runs on CPU in 5.5 s warm for this 34.688-second take. It also supplies the
project's first sustain-pedal output.

Basic Pitch consumes a harmonic-stacked CQT and is instrument-agnostic, so bins
`p` and `p+12` share much of their evidence and a low piano string's strong
second partial can drive the shared onset head. A proposed inharmonicity and
envelope-correlation veto was **rejected before implementation**: it can only
separate a partial from a struck string in sparse, dry textures, and the target
failure occurs with pedal and overlapping notes. Changing the model addressed
the same failure without a heuristic.

This is one unaligned take, so it is comparative evidence and not precision or
recall. It does support promoting a piano-specific offline adapter above
further Basic Pitch decoder tuning.

### Transkun does not survive short context

Transkun is an offline adapter, not a live one. Its shipped 2.0 configuration
uses 16-second segments with an 8-second hop, a six-layer transformer attending
over both frequency and time within the segment, and a semi-CRF that decodes
whole note intervals by dynamic programming. Nothing about that is causal, and
a note is not emitted until its span is decided.

Sweeping segment size on the reference WAV, scored against its own default
16-second output as the reference:

```text
segment  hop  raw notes   wall    xRT      P      R     F1
     16    8         96   4.09s   8.5x  1.000  1.000  1.000
      8    4         52   2.85s  12.2x  0.769  0.417  0.541
      4    2         44   2.91s  11.9x  0.750  0.344  0.471
      3  1.5         77   3.04s  11.4x  0.870  0.698  0.775
      2    1         47   3.54s   9.8x  0.702  0.344  0.462
      1  0.5         40   5.62s   6.2x  0.675  0.281  0.397
```

Recall collapses to roughly a third once context drops below the trained
segment size, while throughput stays near ten times real time throughout. The
limit is context, not compute — the same conclusion the rolling Basic Pitch
work reached, for a different reason.

The 3-second row is out of order relative to its neighbours. Treat the sweep as
a single-take feasibility probe rather than a curve; it is enough to reject
naive windowing and not enough to locate an optimum.

Counts here are raw semi-CRF estimates. Transkun's `writeMidi` drops 96 raw
estimates to the 80 notes in the emitted MIDI, so the two numbers are not
interchangeable.

This confirms the two-lane split the implemented architecture already has: a
small causal model for the rolling live feed, and Transkun on Stop for the
final backfill and any score conversion.

## Accepted Pipeline Boundary

```text
timestamped audio source
        │
        ▼
sample normalization and circular buffer
        │
        ▼
window scheduler ──► model adapter ──► native model output
        │                                      │
        └──────────────────────────────────────▼
                              overlap/revision reconciler
                                             │
                                             ▼
                              normalized note-event stream
                                             │
                    ┌────────────────────────┴──────────────┐
                    ▼                                       ▼
             piano-roll consumer                 analysis consumer
```

Local microphone capture, phone capture, and deterministic replay are
interchangeable timestamped audio sources. Acoustic transcription and direct
MIDI are interchangeable note sources at the downstream boundary; MIDI must
not pass through an acoustic model.

The first source should be deterministic replay. It can feed recorded samples
at wall-clock cadence while preserving an exact ground-truth timeline. This
gives reproducible end-to-end latency evidence without mixing in microphone,
browser, clock-synchronization, or network behavior.

## Time And Event Contracts

Audio sample position is the source of truth. Each input stream needs a stable
session origin, sample rate, first-sample index, frame count, and monotonic
capture timestamp. Packet arrival time and inference completion time are
diagnostics, not musical time.

The normalized event representation should be able to express:

- source (`acoustic` or `midi`) and session identity;
- stable note identity and revision number;
- MIDI pitch 21–108;
- onset in the source audio timeline;
- optional offset, velocity, confidence, and pedal relationship;
- lifecycle (`provisional`, `committed`, or `retracted`); and
- emitted-at time for latency measurement.

Do not force early model output to pretend to be final MIDI. A low-look-ahead
lane may emit a provisional onset, while a later window corrects timing,
supplies an offset, or retracts a false positive. Consumers should choose
whether to show the revisable tail or only committed events.

## Latency Accounting

For a note onset, report end-to-end latency from the onset's source-sample time
to event emission, with at least p50, p95, and maximum values. This includes
time spent waiting for required future samples. Also record:

1. audio device or replay buffering;
2. resampling and feature extraction;
3. transport and receive buffering, when remote;
4. algorithmic look-ahead or unavailable future context;
5. scheduler wait and batch formation;
6. model inference;
7. decoding and overlap reconciliation; and
8. delivery to the consumer.

Real-time factor only answers whether a system can keep up on average. It does
not include future context, a ten-second input block, batching waits, or tail
latency and therefore cannot establish product latency by itself.

## Quality Accounting

Retain model-native output so thresholds and reconciliation can be replayed.
Report at least:

- note-onset precision, recall, and F1 at 50 ms and tighter tolerances;
- note-with-offset precision, recall, and F1;
- frame F1 or another sustained-note measure;
- velocity error and pedal metrics when the model supports them;
- false activations during silence and room noise;
- duplicate, stuck, shortened, and missed repeated notes;
- provisional-to-committed delay and revision/retraction rate; and
- accuracy by pitch range, polyphony, dynamics, and recording condition.

Aggregate dataset scores must be accompanied by focused clips for low bass,
high treble, dense chords, repeated notes, legato with sustain, soft attacks,
release tails, speech/noise, and silence.

## Windowing And Reconciliation Matrix

For every runnable model, first establish its ordinary full-context result.
Then sweep only configurations the architecture can actually support:

- context/window length;
- hop length and overlap;
- left context and future look-ahead;
- single-window versus batched inference;
- decoder thresholds and minimum note duration;
- edge discard or center-only commit region;
- provisional versus committed event horizon;
- numeric precision and execution provider; and
- raw PCM versus any later transport codec.

Overlapping windows require deterministic reconciliation. Associate candidate
notes by pitch and onset/offset proximity, prefer estimates farther from
window edges when confidence is otherwise comparable, and keep revision
history. Score both the best final transcript and what was visible at each
latency deadline.

The experiment output should be a machine-readable run manifest plus a compact
Pareto table. Every result needs the source revision, model/checkpoint hash,
runtime/provider versions, device, input identity, parameters, warm-up policy,
and raw timing samples.

## Candidate Lanes

### Runnable prototype shortlist

Research on 2026-07-24 narrowed the immediate runnable candidates:

| Priority | Candidate | Why it remains interesting | Constraint |
|---|---|---|---|
| 1 | [Spotify Basic Pitch](https://github.com/spotify/basic-pitch) 0.4.0 | Small, Apache-2.0, polyphonic, 88-key output, native activations, and an official Core ML form | Instrument-agnostic, no pedal output, file-oriented two-second windows, and no released streaming decoder |
| 2 | [ByteDance high-resolution piano transcription](https://github.com/bytedance/piano_transcription) | Piano-specific notes, offsets, velocity, and sustain-pedal events with released checkpoints | Archived in 2025, based on a Python 3.7/PyTorch 1.4 stack, and officially exposes only CPU/CUDA inference |
| 3 | [Aria-AMT](https://github.com/EleutherAI/aria-amt) | Piano-specific sequence model with note, velocity, and pedal tokens; Apache-2.0 code and released weights | Official inference documentation is oriented toward Linux/CUDA and full-file processing |
| 4 | [Onsets & Velocities](https://github.com/andres-fr/iamusica_demo) | Piano-specific onset/velocity lane with a released checkpoint and live demonstration | Omits offsets and pedal; published demo commonly uses 4–9 seconds of context and an older Ubuntu/PyTorch stack |
| Watch | [MuScriptor](https://huggingface.co/MuScriptor/muscriptor-small) | Current open-weight general AMT with 100M–1.3B sizes and instrument conditioning | Five-second segments, no velocity, non-piano specialization, and CC-BY-NC-4.0 weights |
| Watch | [Mobile-AMT](https://eurasip.org/Proceedings/Eusipco/Eusipco2024/pdfs/0000036.pdf) and its [causal audit](https://arxiv.org/abs/2509.07586) | Directly targets robust streaming piano transcription and exposes important hidden-latency failures | A clean, versioned public implementation/checkpoint acquisition path has not yet been confirmed |

Hugging Face search is useful for checkpoint discovery but currently returns
several third-party mirrors and undocumented ONNX conversions for piano
transcription. Do not treat a conversion as equivalent to its upstream model
until provenance, license, output fidelity, and sample alignment are verified.

Start with Basic Pitch to prove the harness and local execution path. The next
quality comparison should be piano-specific and should include pedal output;
ByteDance and Aria-AMT are the leading offline candidates. A streaming lane
should be added only after its released implementation and true algorithmic
look-ahead have been audited.

### 1. Basic Pitch portability baseline

[Spotify Basic Pitch](https://github.com/spotify/basic-pitch) is lightweight,
polyphonic, designed to work on a single instrument at a time, and ships
TensorFlow, Core ML, TensorFlow Lite, and ONNX model forms. Its broad runtime
support makes it the fastest way to establish the benchmark and execution
boundary. It is not piano-specific and its file-oriented decoder/windowing
must not be assumed to be streaming-correct.

[NeuralNote](https://github.com/DamRsn/NeuralNote) is useful implementation
evidence for running the Basic Pitch network in a native audio-to-MIDI tool,
but its architecture and license must be reviewed before reusing code.

### 2. Piano-specific offline quality baseline

[ByteDance's high-resolution piano transcription
model](https://github.com/bytedance/piano_transcription) predicts piano notes,
velocity, and pedal events and is a valuable full-context comparison. Its
released implementation is archived and based on an older PyTorch stack. The
model's bidirectional/full-context behavior makes rolling-window latency,
edge quality, and accelerator portability questions to measure rather than
assume.

### 3. Onset-first live baseline

[Onsets & Velocities](https://github.com/andres-fr/iamusica_training) has a
released pretrained model and a companion
[real-time demo](https://github.com/andres-fr/iamusica_demo). It focuses on
onsets and velocities rather than complete offsets and pedal state, so it is
best evaluated as an immediate/provisional onset lane or as evidence for a
two-pass system, not as the only full piano-roll source.

### 4. Streaming research lane

[Mobile-AMT](https://eurasip.org/Proceedings/Eusipco/Eusipco2024/pdfs/0000036.pdf)
targets lightweight, in-the-wild online piano transcription. A
[2025 causal follow-up](https://arxiv.org/abs/2509.07586) is especially
relevant because it audits hidden non-causal operations, preprocessing delay,
and the quality cost of strict causality. A separate
[streaming onset/offset/pedal
model](https://arxiv.org/abs/2503.01362) suggests that streaming-specific
decoding may retain better note consistency than repeatedly applying an
offline model.

Checkpoint availability, licensing, reproducibility, and actual runtime
support must be confirmed before any of these become implementation
dependencies. They are research lanes, not selections.

### Deferred comparators

MT3 and other multi-instrument sequence models are not first candidates. They
solve a broader problem, add runtime complexity, and do not directly answer
whether a piano-specific or lightweight model is already useful. Revisit them
only if the first lanes reveal a quality ceiling they can plausibly move.

## Corpus Direction

Use three layers:

1. **Aligned reference corpus:** a fixed MAESTRO v3 subset gives real acoustic
   piano recordings with aligned performance MIDI and comparable metrics.
2. **Controlled local corpus:** scales, intervals, repeated notes, chords,
   dynamics, pedal gestures, and silence recorded at planned MacBook and phone
   positions near the target piano.
3. **Stress corpus:** room noise, speech, movement, distant placement, clipping,
   reverberation, and non-piano interference.

Never commit the audio or upstream datasets. Track immutable clip identifiers,
acquisition recipes, hashes, device/placement metadata, and any annotations.
For local material without MIDI ground truth, begin with qualitative review
and manually annotate only a small diagnostic set.

## Host And Phone Direction

Do not begin with compressed phone audio. On a LAN, timestamped mono PCM is
simple enough for the first capture proof and avoids confounding model quality
with codec artifacts. Add Opus or another codec as a measured experiment if
bandwidth, browser behavior, or remote use requires it.

A browser phone source should derive sequence and time from the AudioWorklet
sample clock, send sample-indexed frames, and maintain an explicit mapping to
the host monotonic clock. The host owns buffering and inference. Local Mac
capture should produce the same frame contract without network transport.

The local browser workbench now proves the file-producing half of this
direction. Its AudioWorklet checks source-frame continuity and records the
effective browser microphone settings, but it uploads only after Stop. It has
no browser-to-host clock mapping and correctly makes no source-to-emission
latency claim. Live block transport, backpressure, reconnect behavior, HTTPS,
and authentication remain separate work.

Execution providers are an experimental dimension:

- Apple Silicon: start with the model's supported Core ML, ONNX, or PyTorch/MPS
  path and measure conversion fidelity;
- NVIDIA: CUDA-backed framework or ONNX provider;
- Windows/Linux AMD: evaluate available ONNX, DirectML, ROCm, or Vulkan-capable
  paths per model; and
- CPU: retain a portable control and fallback.

Do not promise one common accelerator runtime until models have been converted
and compared. The stable boundary is the model adapter, not a particular ML
framework.

## Completed Tacticals

`docs/tactical/000-live-replay-benchmark.md` completed the bounded slice:

1. a versioned input/run manifest;
2. deterministic real-time-cadence replay from a small aligned corpus subset;
3. source-sample and stage timing instrumentation;
4. one unmodified Basic Pitch reference adapter;
5. preservation of raw model output and normalized note events;
6. offline and replay-mode quality scoring; and
7. a report that plots or tabulates quality against event latency.

It also added a small file-producing microphone adapter and local debug
reviewer at the user's request. It did not add phone transport, a polished
product piano roll, model conversion, harmonic analysis, or a second model.

`docs/tactical/001-browser-capture-workbench.md` added a loopback-only browser
source and one-page workflow:

1. request mono microphone access with speech processing disabled;
2. capture sample-indexed PCM in an AudioWorklet;
3. stop, inspect, and audition a lossless WAV;
4. create a versioned unaligned input through a bounded local upload;
5. queue the existing full-file adapter outside the audio callback; and
6. review the completed artifacts at a durable job URL.

Recommended next work is to review a controlled recording from the target
acoustic piano through this workbench, compare its browser and native-capture
audio, acquire a checksummed MAESTRO v3 diagnostic subset for real-audio
aligned scoring, repeat cold and warm timing trials, and then add one
piano-specific offline adapter with pedal output.

The first target-piano take now supplies the initial subjective evidence.
[`002-performance-notation-spikes.md`](../tactical/002-performance-notation-spikes.md)
is complete: the workbench can render a traceable local score and import
separate Ivory WAV and atpiano-MIDI MusicXML results. Its target-piano score
failed subjective readability review, while the Ivory preview was readily
playable.

[`003-live-browser-transcription-spike.md`](../tactical/003-live-browser-transcription-spike.md)
is complete and established the sample-indexed browser stream, rolling model,
event lifecycle, and exact-final backfill. The model-comparison work above
remains valid.

[`005-strict-onset-decoder-spike.md`](../tactical/005-strict-onset-decoder-spike.md)
is complete. It establishes strict onset 0.6 as the current live Basic Pitch
baseline, preserves decoder-origin evidence, and rejects an ungrounded
refractory or source-attack filter. Next collect a controlled held-chord and
reattack clip, review the live behavior, and move to a piano-specific onset
lane if the learned Basic Pitch onset head still produces false held-note
starts.

## Open Questions

- How much delay is subjectively acceptable for passive piano-roll feedback?
- Should provisional notes be shown immediately, faded, or hidden until
  committed?
- Does a two-pass onset-first/full-reconciliation system dominate a single
  windowed model?
- How much do the target room, piano, lid position, device placement, and
  microphone response shift quality from MAESTRO?
- Are pedal events required for the first useful output, or can consumers infer
  enough from sustained notes initially?
- Which model forms reproduce their reference outputs closely enough across
  Core ML, ONNX, CUDA, MPS, DirectML, and CPU?
- Can phone PCM remain reliable under screen lock and browser lifecycle rules,
  or will a native capture client eventually be required?
