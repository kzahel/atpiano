# Live Acoustic Transcription

Topic: live-acoustic-transcription

Status: strict-onset live decoder implemented and ready for subjective review.
The live lane now requires an explicit Basic Pitch onset-head peak at 0.6;
frame-inferred and melodia fallback starts remain available only in the
untouched exact-final lane.

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

The near-term target is not instrument-control latency or readable full
notation. It is an onset display that begins filling while the pianist plays:

- suppress candidates that do not rise meaningfully above the calibrated room
  floor;
- show credible onsets in roughly the existing one-second live-feedback band;
- make recent pitches and broad chord shape obvious without requiring reliable
  note offsets;
- light the correct physical piano keys and place nearby onsets together on a
  sequential grand staff;
- retain revisions, offsets, and lifecycle evidence without forcing those
  details into the pianist-facing view; and
- after Stop, run the exact full-file path that already sounded useful to the
  user and backfill the final result.

This deliberately separates **time to first useful feedback** from **time to
best available transcript**. A genuinely causal model may later improve the
first lane without changing the browser or event contracts.

The first subjective success criterion is deliberately simple:

> While playing, can the pianist tell whether the system recognized the
> intended notes and broad chord shape?

The UI therefore ignores model duration. It lights one accurately placed key
per accepted onset and draws filled quarter-note-like marks from left to right
on a grand staff. Onsets within 180 ms of the first onset in a group form one
visual chord. There is no tempo, meter, barline, key signature, hand, voice, or
rhythmic-value claim. This is a pitch/onset diagnostic, not notation or
harmonic analysis.

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

The later notation review made retrospective piano-roll judgment insufficient.
The generated score was unreadable while a hosted Ivory preview was easy for
the user to sight read. To isolate acoustic recognition from score inference,
the user wants to see notes and broad chord shapes while still remembering
exactly what was played.

The target take's Basic Pitch durations are sustained but not extreme:

```text
median: 0.627 s
p95: 1.870 s
maximum: 3.148 s
notes at least 2 s: 5 of 133
```

This reinforces an onset-first live display. Offset and pedal behavior remain
important evidence, but they should not delay or visually obscure initial
pitch feedback.

### Implemented target-take live replay

The 34.688-second target take was streamed at wall-clock cadence through the
actual workbench WebSocket and rolling Core ML model on the Apple M4 Pro. Run
`20260724T130652-50255becb667` retained 132 native model windows and produced:

```text
first-visible server emission: p50 0.428 s, p95 1.649 s, max 1.876 s
live committed notes: 140
exact-final notes: 133
matched live/final onsets: 127
final additions: 6
live removals: 13
matched onset change: p50 0.006 s, p95 0.034 s
matched offset change: p50 0.013 s, p95 0.866 s
```

This is stronger evidence for useful live onsets than for live durations.
Most final notes had a nearby live identity and their onset changes were small,
but the live lane also retained 13 notes removed by the final pass and missed
six final additions. Offset p95 changed by 0.866 seconds, confirming that
open-ended provisional tails are the honest first interaction.

The replay did not run inside a browser, so these figures end at server event
emission and its browser-delivery metric is explicitly null. Actual browser
sessions retain clock exchanges and paint acknowledgements for full delivery
measurement. There is still no aligned MIDI for this take, so agreement with
the exact-final adapter is not acoustic accuracy.

### First subjective microphone review

The first live piano pass detected a played isolated note, but Basic Pitch also
emitted notes from ordinary background sound before the piano was played. The
user found the duration roll unhelpful and the keyboard visibly wrong: it
assigned equal width to all 88 pitches, so black keys displaced white keys.
Its recent provisional highlight was orange even though the legend advertised
yellow.

Two retained sessions captured the reported room and playing:

```text
job                                    room floor    gate       rejected/native
20260724T134000-5e1c8bd9c117           -55.71 dBFS   -47.71     256 / 1,902
20260724T134321-64e32730188c           -61.85 dBFS   -48.00     247 / 1,164
```

Those figures re-decode the already-preserved native windows and apply the
implemented onset-energy policy: median 50 ms RMS over the first second, plus
8 dB, clamped to -48 through -34 dBFS. They are overlapping-window candidate
decisions, not unique notes or accuracy scores. The gate rejected 13.5% and
21.2% respectively. The 34.688-second target take's -48 dBFS gate accepted all
1,282 native candidates; its quietest exact-final attack measured -40.57 dBFS.

Both reviewed sessions also exposed a boundary bug: the old page reached two
minutes with one AudioWorklet block in flight, and the server rejected that
block. The page now initiates Stop from the block path and the server permits
one bounded final block.

### Second subjective microphone review

The physical 52/36-key keyboard and sequential grand staff are more legible.
The user then isolated a more fundamental recognition failure: holding a chord
causes many new noteheads, including overtone pitches, without new key attacks.

The two completed two-minute runs show that this is not merely UI relighting.
The first exact-final result contains 214 notes and 62 same-pitch re-onsets less
than one second apart; pitches 55, 60, 67, and 48 occur 30, 29, 28, and 27
times. The second has 137 notes and 38 sub-second same-pitch re-onsets. Similar
new starts are present in the rolling committed identities and the untouched
exact-final output.

The current gate cannot distinguish this from a real onset. It asks whether a
candidate's local signal is loud relative to the room, and a resonating chord
is loud. It does not measure a new attack or per-pitch activation transition.

The stock Basic Pitch decoder explains much of the behavior:

- `infer_onsets=True` creates onset candidates from changes in frame
  activation; and
- `melodia_trick=True` converts remaining frame energy into notes without an
  explicit onset peak.

Re-decoding retained full-file probabilities with both behaviors disabled
reduces the first held-chord run from 214 to 155 notes and sub-second
same-pitch re-onsets from 62 to 39. The second falls from 137 to 70 notes and
from 38 to 14 repeated starts. The earlier target take also falls from 133 to
92 notes, so the removed set cannot be called false without aligned MIDI.
Some repeated starts remain, showing that the learned onset head itself can
respond to sustained acoustic modulation or resonance.

### Strict-onset decoder result

Tactical
[`005-strict-onset-decoder-spike.md`](../tactical/005-strict-onset-decoder-spike.md)
turns the exploratory comparison into a reproducible decoder study. Each
candidate retains its native onset and frame confidence plus whether it came
from the explicit onset head, inferred frame change, or melodia fallback.

The aligned 19-note fixture selects a live onset threshold of 0.6:

```text
policy                    notes    25/50 ms onset F1
stock                       23          0.905
strict onset 0.5             20          0.974
strict onset 0.6             19          1.000
strict onset 0.7             19          1.000
strict onset 0.8             18          0.973
```

The lower perfect threshold avoids unsupported deletion from the unaligned
piano takes. Relative to stock, strict 0.6 changes the earlier useful take from
133 to 81 notes, held-chord A from 214 to 149, and held-chord B from 137 to 52.
Sub-second same-pitch restarts fall from 37 to 15, 62 to 38, and 38 to 10.
These reductions establish a less busy decoder, not acoustic precision.

No additional refractory or source-attack gate was selected. The fixture's
two E4 strikes 450 ms apart must both survive, and apparent repeated notes in
the retained acoustic takes often have strong separate source attacks. A 3 dB
attack-novelty threshold preserves the fixture but removes 23 of the 81
strict-decoded target notes without aligned evidence that they are false.

Real rolling Core ML validation on the 34.688-second target take produced 83
committed identities over 132 windows, close to the 81 full-file strict notes
and materially below the earlier stock rolling result of 140. The rolling
fixture produced 19 identities and matched 18 reference onsets; its missing
0.5-second bass note is intentionally inside the one-second room-calibration
period. After excluding that calibration-period reference, onset recall is
1.000, precision 0.947, and F1 0.973.

## Implemented Live Architecture

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
          |       strict onset decoder
          |             |
          |             v
          |       room/onset energy gate
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

The browser uses an
[`AudioWorklet`](https://www.w3.org/TR/webaudio-1.1/) so each block has a
source sample position. It sends binary PCM16 blocks through the standard
[`WebSocket`](https://websockets.spec.whatwg.org/) API with a small versioned
header containing session, sequence number, first source sample, frame count,
sample rate, and client clock observations.

The selected model window is Basic Pitch's unchanged 43,844 samples at
22,050 Hz, or 1.988 seconds. The scheduler runs every 250 ms, with 116 ms and
232 ms edge guards and a one-second commit horizon. This is one first measured
configuration, not the promised optimum. The model is warmed and cached before
the worklet begins. Live decoding requires an explicit learned onset-head peak
at 0.6 and disables frame-inferred onsets and the melodia fallback. Every
native probability window, candidate origin, and timing sample is preserved.

The first source second calibrates room noise as the median RMS of 50 ms
frames. A candidate's 140 ms onset-local window must clear a threshold eight
dB above that floor, clamped from -48 through -34 dBFS. Candidates within the
calibration second are suppressed. The gate runs before event reconciliation
and records every decision; it does not alter the preserved model-native
outputs or the exact final adapter.

The AudioWorklet never waits on the network. The page observes the WebSocket
queue outside the render thread and turns growth above 4 MiB into an explicit
failure. The host rejects gaps, duplicates, reordering, sample-rate changes,
invalid payloads, and oversized sessions rather than silently repairing them.
It stores the lossless session waveform independently of rolling inference so
every live run can be replayed.

Musical time remains the audio sample clock. Periodic clock exchanges fit
offset and drift between browser and host monotonic clocks. Browser paint
acknowledgements measure capture-to-visible delivery; a server send timestamp
alone remains only partial experience evidence.

## Revision And Backfill Contract

The browser consumer retains the normalized event lifecycle established by the
benchmark:

- `provisional`: useful recent estimate that may move or disappear;
- a higher revision of the same stable identity: corrected onset, offset,
  velocity, confidence, or other supported attributes;
- `committed`: past the declared rolling commit horizon; and
- `retracted`: a provisional identity removed by later evidence.

The pianist-facing keyboard and grand staff deliberately reduce this to
accepted onset identities: commit revisions do not relight a key, retractions
remove still-visible identities, and offsets are not drawn. The artifacts
still preserve the full lifecycle.

The final full-file result may differ even from rolling committed notes. That
is not an ordinary live revision; it is a named **final-pass reconciliation**.
The review UI and artifact preserve both what was visible live and what became
the best final transcript. Stable matching minimizes distracting note
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

## Resolved Workbench Disconnect

The reported `ConnectionResetError: [Errno 54] Connection reset by peer`
occurred in `_send_file` while the server was writing an artifact body to a
browser socket. The associated job and all transcription artifacts completed.
This is consistent with a browser cancelling an audio range request during
seek, source replacement, or navigation; it is not a model or recording
failure.

The response writer now treats `BrokenPipeError` and `ConnectionResetError`
as ordinary client cancellation and stops the response without a traceback.
A focused test covers the behavior.

## Recommended Direction

Do not tune the absolute-volume gate or add a generic harmonic filter for this
failure. The former cannot distinguish a new strike from loud resonance; the
latter would erase legitimate piano octaves and fifths.

First repeat the held-chord interaction with the selected strict 0.6 live
decoder. The workbench identifies that policy in the live status area. Judge
whether a chord held without restrikes remains visually stable and whether
ordinary repeated notes still appear.

Then record a short controlled local clip with silence, isolated soft and loud
notes, a held chord, repeated strikes at several gaps, true octaves/fifths,
bass, treble, and pedal. Retain or manually annotate enough onset truth to
separate false resonance starts from real reattacks.

If strict decoding still confuses sustained harmonics with new attacks, keep
the proven transport, clock, artifact, keyboard, and staff boundaries and open
the causal/piano-onset model bakeoff. An onset-specific or piano-specific lane
is more justified than adding a refractory period or harmonic filter without
ground truth.

The current implementation record is
[`005-strict-onset-decoder-spike.md`](../tactical/005-strict-onset-decoder-spike.md).

## Required Measurements

- input sample continuity and explicit gaps;
- capture buffer, transport, receive, resample, scheduler, inference,
  reconcile, delivery, and browser-paint timing;
- source-onset-to-provisional and source-onset-to-committed p50, p95, and max;
- precision, recall, and F1 visible at 250 ms, 1 second, and 3 seconds;
- provisional revision/retraction rate and time to stability;
- room-floor estimate, gate threshold, accepted/rejected candidate counts, and
  soft-note false rejection;
- final-pass disagreement and parity with untouched offline output;
- CPU, memory, inference queue, and WebSocket queue high-water marks; and
- silence, room noise, repeated notes, chords, pedal, bass, treble, Stop tail,
  disconnect, and reconnect behavior.

## Open Questions

- Is 0.43-second median but 1.65-second p95 provisional feedback satisfying in
  practice on actual microphone input?
- Does the automatic gate suppress pre-piano notes without losing soft attacks?
- Does the implemented 180 ms recent-onset grouping make rolled chords legible
  without merging melodic runs into one pitch set?
- Does strict onset 0.6 subjectively stabilize a held chord on the target
  piano while retaining ordinary repeated strikes?
- Which remaining learned-onset responses in a controlled held-only clip are
  false, and do they justify a source-attack or active-note policy?
- Is the current named live-versus-final summary sufficient to explain changes
  to rolling-committed notes?
- What hop and commit horizon best preserve the current target-piano quality?
- Does pedal-aware streaming matter more than improving note-onset latency?
- When a remote accelerator is tested, is raw LAN PCM still acceptable or
  does codec latency and reliability become the next frontier?
