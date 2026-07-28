# Live Acoustic Transcription

Topic: live-acoustic-transcription

Status: the strict-onset v1 live decoder remains a runnable MVP. On 2026-07-26
the separate stable corrected-note v2 milestone completed in
[`010-corrected-note-workbench-v2.md`](../tactical/010-corrected-note-workbench-v2.md):
a separate app with deterministic replay, bounded indefinite sessions,
provisional Basic Pitch, trailing Transkun correction, pedal, review, and
export. Tactical 012 subsequently added optional bounded committed-score
snapshots without claiming continuous progressive engraving. A later real
x86_64 Linux Chrome fake-microphone run preserved and recovered all data but
failed the live operational contract: same-process Transkun CPU inference
allowed input backlog and Stop settlement to exceed the client's 90-second
wait. Tactical
[`022-durable-capture-worker-isolation.md`](../tactical/022-durable-capture-worker-isolation.md)
is now the first Phase 4 implementation slice; Tactical
[`023-backend-capability-degradation.md`](../tactical/023-backend-capability-degradation.md)
then selects an honest live, delayed, or after-Stop correction mode from
isolated measurements. Their host-independent implementation now passes
locally. The 2026-07-27 Linux profile selects after-Stop, and real Chrome
acceptance now preserves real-time ingest, prompt Stop, reload settlement, and
Basic Pitch responsiveness under a separately saturated Transkun worker.
The Phase 4 application-core extraction subsequently moved capture ownership,
PCM acceptance, Stop, settlement, model lifecycle, and replay composition out
of HTTP. Microphone and replay now use the same sample-indexed application
service. Storage validation has also proved one-hour and three-hour compact
recordings seek to the exact source-clock range across every deterministic
repeat boundary. A 2.10-hour M4 Pro real-model soak also completed with full
commit coverage. R4 accepted application parity and compact retention on
2026-07-27. Local models still load only on first use and now unload after ten
fully settled idle minutes by default. The capture application cancels a
pending eviction when a new session claims ownership, rejects stale timer
callbacks by generation, and exposes the current load and deadline state for
diagnosis. A zero timeout retains the former keep-warm behavior. A
same-duration Linux soak is retained only as the narrower host-specific gap
documented in Tactical 022.

On 2026-07-28, Tactical
[`038-recording-import.md`](../tactical/038-recording-import.md) completed the
first product recording-import path. WAV and MP3 decoding produces contiguous
mono PCM16 blocks on the decoded source sample clock and then uses the same
capture application and transcription lanes as microphone input;
deterministic fixture replay remains an engineering-only source.

The next live family microphone attempt exposed a deployment dependency gap,
now fixed and live under
[`040-websocket-runtime-dependency.md`](../tactical/040-websocket-runtime-dependency.md).
The request reached `/api/live`, but the locked environment contained Uvicorn
without either supported WebSocket protocol implementation. Uvicorn rejected
the upgrade before the authenticated application handler ran. The ordinary
locked runtime now includes `websockets`, Uvicorn selects its Sans-I/O
protocol, and a public authenticated handshake reaches the application. The
fix does not change PCM, capture, or model semantics.

## Scope And Relationship

This topic owns the live user path:

- sample-indexed browser-to-host audio transport;
- session clocks, buffering, backpressure, gaps, and reconnect behavior;
- scheduling rolling inference while capture continues;
- provisional, revised, committed, and retracted UI behavior;
- v1's final full-file reconciliation pass after Stop and v2's proposed
  continuously committed replacement; and
- measured capture-to-browser-display latency.

[`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md)
continues to own model adapters, raw model evidence, transcription quality,
and the general latency/quality benchmark. This topic applies those contracts
to a user-operated browser session. The downstream piano-roll or notation
consumer remains separable and must also accept direct MIDI.

[`session-workspace-management.md`](session-workspace-management.md) owns the
accepted refactor that separates the active capture session from each
browser's selected session, then adds explicit New, history, and recoverable
deletion without changing the capture sample-clock contract.
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
retains the deferred hosted and Tauri execution topology, multi-user
workspace model, streaming process boundaries, persistence, and
observability. [`home-hosted-family-sharing.md`](home-hosted-family-sharing.md)
owns the current single-host deployment. Any future cloud transport must
preserve this topic's sample clock, event lifecycle, horizons, and separate
latency stages.

## Product Version Boundary

The current `uv run atpiano workbench` application is the v1 MVP. Its command,
frontend behavior, session artifacts, exact Basic Pitch final pass, review
path, and tests remain supported. Existing sessions remain reviewable.

The plan in
[`009-three-phase-unbounded-sessions.md`](../tactical/009-three-phase-unbounded-sessions.md)
builds a separate v2 live web application. V2 gets its own CLI entry point,
frontend, session schema, and artifact namespace. It may share proven capture,
transport, clock, adapter, and event internals with v1, but shared changes must
pass a v1 smoke test and must not silently turn v1 into an alias for v2.

V2 bring-up is file-driven. The frozen 19-note diagnostic fixture, a new
aligned 16-bar musical fixture, and the checksummed golden-reference WAV feed
the same sample-indexed session engine used by live capture. The musical
fixture contains a declared progression, block chords, Alberti bass, melody,
and pedal evidence rather than only isolated smoke-test events. Long
continuous-clock loops establish repeatability, horizon movement, and bounded
resources before a pianist is asked to perform into a microphone. Because the
golden-reference recording has no aligned MIDI, it is an operational and
offline-parity oracle, not absolute note truth.

Implementation began under tactical 010. The aligned musical fixture and the
model-independent v2 session foundation now exist. `atpiano replay-v2` feeds a
WAV through one continuous source clock into a fixed 40-second PCM ring,
60-second WAV and event segments, monotonic horizon evidence, and an indexed
range-query store. A two-repeat 84-second source check preserved all 4,032,000
frames across the expected two repetition boundaries. At that foundation
checkpoint no model was connected.

The bounded v2 Lane A has since landed behind `replay-v2 --preview`. On the
aligned 42-second musical fixture it processed 161 real Basic Pitch windows,
retained the configured final 32 after 129 evictions, and ended with `H_prov`
1.101 seconds behind capture. Its 181 latest non-retracted identities score
0.860 onset F1 at 50 ms and 0.850 at 25 ms. This is the provisional baseline
against which Lane B corrections are measured.

The trailing Transkun Lane B now lands behind `replay-v2 --commit` with the
optional `corrected` dependency extra. On the aligned musical fixture, eight
bounded CPU decodes consume 22.455 seconds total over 42 seconds of source.
The lane corrects 132 preview identities in place, retracts 56, adds 32,
closes 26 open boundary tails, preserves 12 pedal intervals, and flushes
`H_commit` to the source head at Stop.

Compared with one independent full-file Transkun control, the final 147-note
rolling transcript scores 0.936 onset F1 at 25 and 50 ms and 0.827
note-with-offset F1. Ten of 11 control pedal onsets match and nine of those
offsets are within 200 ms. This passes the planned onset-parity band but is not
exact equivalence.

The separate `atpiano workbench-v2` browser app now accepts server-driven WAV
replay or AudioWorklet microphone blocks through that same session engine. Its
fixed canvas queries only 15–120 seconds from a maintained materialized-event
index, shows both horizons and pedal bands, and writes committed MIDI plus
full revision-history JSONL without reading PCM. The v1 command and frontend
remain separate.

Live viewport reads explicitly skip append-history paging, which the display
does not consume; recovery clients can still request bounded history pages.
Replay viewport invalidation follows the audio head and session status rather
than relying on the microphone-only block acknowledgement. The canvas reports
visible note and pedal counts and places range-load errors beside the
timeline. This followed a manual replay where all 152 committed notes were
present in the index and exports while the first empty viewport response
remained cached, confirming a presentation failure rather than an inference
or fixture failure.

The roll is no longer v2's only pitch view. The Performance card independently
toggles the roll and an 88-key keyboard. The roll has an aligned key gutter
with A0, C-octave, and C8 labels; the keyboard names and lights the latest
detected attack, with amber provisional and mint corrected states. Clicking
the roll or moving a source-time slider pins the keyboard to notes sounding at
that exact sample-clock time. This exact-pitch view does not infer score
rhythm, meter, key, spelling, hands, or chord names; those remain Lane C
concerns.

The shared React successor must preserve the controller distinction already
present in v2. Sustain (CC64) and soft pedal (CC67) are separate
model-estimated lanes, not one generic sustain state. Long intervals remain
possible model errors: the Phase 3 review session
`20260726T113845-517f8d425847` produced a false 25.5-second soft-pedal
interval when the performer used no pedal. The UI labels controller output as
inferred and visibly flags unusually long estimates for verification; it does
not silently suppress them or claim acoustic correctness. Committed
controller gestures, like committed notes, stop at `H_commit`.

Saved-session review now uses the same source clock for recorded audio,
scrubbing, roll inspection, and the detected keyboard. The React transport
plays and seeks across the session rather than treating the prior inspection
range as a permanently paused control. Local artifact delivery supports byte
ranges so a seek addresses the requested audio time.

After Stop, the ordinary v2/v3 workflow derives one 128 kbps MP3 from the
complete bounded WAV segment sequence. Only after all enabled model lanes
settle is the MP3 atomically published, fully decoded, probed against the
source range, and durably mapped before WAV retirement. Encoder, verification,
or cursor failure retains WAV, and `--retain-wav` preserves it deliberately.
One-hour and three-hour validation decoded aligned probes after all 86 and 258
repeat boundaries. R4 accepted this compact default; MP3 is not declared a
permanent archival codec or a transcription-safe future source.

V2 now also has an independently toggleable committed Score view. It is an
explicit, on-demand downstream snapshot rather than part of either acoustic
lane: the server freezes one `H_commit`, selects only closed committed notes,
and runs a pinned MIDI2ScoreTransformer process in the background. The page
states the snapshot boundary, generation duration, freshness, and failures
while capture continues. The real two-repeat musical fixture produced a valid
311-note, 19-measure MusicXML snapshot through the loopback API in 4.257
seconds. See
[`012-committed-score-snapshots.md`](../tactical/012-committed-score-snapshots.md)
for the runtime and evidence.

Open offsets on the roll now use a short solid onset stub plus a faint dashed
tail to the applicable commit or source horizon. A note with no known ending
therefore no longer appears to assert a solid duration all the way to the
viewport edge.

Final page-facing acceptance used both aligned and target-piano WAV loops. Two
musical-fixture repetitions differed by 0.009 aligned-reference onset F1 and
scored 0.939 directly against each other. Two repetitions of the retained
34.688-second target-piano take each produced 79 committed notes with 1.0
repeat-to-repeat pitch/onset F1 at 50 ms. A fresh stopped server recovered an
old range and the same exports.

A 30-minute two-lane source-clock test and the existing eight-hour preview
test hold their declared rings, native windows, identities, pending offsets,
and indexed delivery pages within fixed bounds. Real 42–84 second Transkun
runs remained below the four-second hop, while a forced slow-adapter test
proves that v2 exposes degraded mode and raises the hop no farther than eight
seconds. A later 2.10-hour M4 Pro Transkun soak completed 950 decodes with full
commit coverage, bounded pending state, and no temporary files. A consentful
physical browser microphone audition remains recommended evidence; no ambient
microphone was activated automatically.

The first x86_64 Linux Chrome fake-microphone run adds necessary negative
evidence. At 24 displayed seconds, the real React/AudioWorklet/WebSocket path
showed 98 notes with 44 corrected and no page error. Under CPU contention,
however, seven Transkun decodes totaled 148.85 seconds, browser audio queued
ahead of the server, and the completed artifact reached 63.21 seconds. The
server eventually flushed the full commit horizon and exports, but the
frontend's 90-second Stop wait expired first and left a stale failure state.
A reload correctly recovered 228 committed notes, 20 pedal intervals, six
artifacts, seekable MP3 playback, and synchronized key inspection.

The retained timing evidence distinguishes slow inference from the scheduling
defect. Two earlier Linux executions of the 42-second fixture averaged 10.87
and 11.14 seconds per commit decode; a later instrumented repeat averaged
16.90 seconds and peaked at 23.16. This host is slower than the M4 Pro record,
and its non-isolated results are variable enough that a controlled benchmark
is still needed. The browser run averaged 21.26 seconds and peaked at 23.65.

Regardless of that performance variance, all seven browser commit decodes
blocked ingest. The horizon log has seven fixed-audio-head gaps of 16.30 to
23.71 seconds, each matching one decode wall time to within about 40 ms. It
took 168.63 wall seconds to accept 63.21 source seconds and 192.35 seconds to
reach the final commit horizon. The WebSocket handler synchronously calls
`CorrectedSession.accept_block`, which synchronously invokes Lane B `_decode`,
before acknowledging the block or reading another PCM frame. This is direct
evidence for the worker boundary: faster inference reduces each plateau but
does not make the current ingest path independent.

This is not a request for a longer timeout. It shows that the local runtime
must isolate model execution from ingest, measure transport and worker queue
high-water independently, and represent Stop settlement as durable
reattachable work. Until that boundary lands and a real browser pass remains
responsive, the corrected Linux microphone path is functionally durable but
not operationally real-time.

The implementation sequence is deliberately split. Tactical 022 owns the
correctness boundary—durable PCM acceptance, bounded worker scheduling,
process isolation, prompt Stop, and reattachable settlement—without changing
model quality. Tactical 023 owns capability policy only after measurements no
longer include synchronous-ingest contention.

That split is now implemented locally. Microphone PCM acceptance and
acknowledgement perform no inference. Preview and commit each own one bounded
scheduler thread and one separately spawned model process; commit reads old
source ranges from segmented audio when it falls beyond the memory ring.
Stop persists `stopping` and returns before background correction and exports
complete. Ordinary session reads make browser reload reattachable, and a
host-process interruption becomes an explicit failed-but-preserved stage
rather than an orphan that blocks future capture.

Sessions record live, delayed, after-Stop, or unavailable correction behavior.
Automatic selection requires an exact matching versioned backend profile and
otherwise uses after-Stop. The measured two-thread Linux profile has a 2.146
service ratio and selects after-Stop. Its real Chrome session accepted 60.693
source seconds in 60.687 wall seconds, acknowledged Stop in 0.257 seconds, and
reattached after reload while seven Transkun decodes settled in the background.

A separate forced delayed-mode Chrome session saturated Transkun during live
capture. Its first decode took 14.566 seconds, but the audio head continued at
capture cadence and Basic Pitch remained one second behind. Runtime evidence
then demoted the session one way to after-Stop with the explicit eight-second
maximum-hop reason. The session stopped promptly, reattached, and completed
all accepted audio and exports. The separate 2.10-hour macOS real-model soak
has now passed. A same-duration Linux rerun remains only under the strict
host-specific reading of Tactical 022, and physical browser-microphone review
remains open.

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
per accepted onset and draws notes from left to right on a grand staff. The
staff can show every raw onset identity or group onsets within a configurable
0–250 ms window anchored at the first onset; grouped mode defaults to 80 ms.
Optional labels show each strict live event's onset score, absolute source
time, previous-onset gap, or both.

A selectable fixed-tempo guide maps each inter-onset gap to the nearest
sixteenth, eighth, quarter, half, or whole glyph. It defaults to 120 BPM and
revises the previous group only when the next onset arrives. It is explicitly
not detected key duration, inferred tempo, meter, rests, or score notation.
This remains a pitch/onset diagnostic rather than harmonic analysis or the
paused performance-to-notation consumer.

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

### First strict-onset subjective review

Workbench job `20260724T144840-82ee228fd1bf` completed 473 rolling windows over
almost two minutes with strict onset 0.6. It produced 154 committed identities
and two retractions. The user judged the behavior to work “pretty great.”

The remaining reported error is attack-synchronous rather than a stream of
held-note starts: striking a lower E can also produce the octave above on the
resonant target piano. That upper partial is real acoustic energy and can
activate Basic Pitch's learned onset head, so strict decoding alone cannot
remove it. A generic high-frequency or octave filter would also destroy real
upper notes and octave dyads.

Tactical
[`006-live-confidence-display-controls.md`](../tactical/006-live-confidence-display-controls.md)
adds raw and grouped staff modes, a configurable chord window, and optional
two-decimal onset-score labels beside noteheads. The view explicitly describes
scores as uncalibrated model evidence. Settings persist locally and are
retained with capture metadata, but never alter accepted events.

### Source timing and rough rhythm guides

Tactical
[`007-live-timing-rhythm-guides.md`](../tactical/007-live-timing-rhythm-guides.md)
adds source-onset time and previous-onset gaps to the same live view. Musical
time still comes from `onset_sample / sample_rate`; transport and display
clocks are not substituted.

Basic Pitch's native hop is 256 samples at 22,050 Hz, so its onset grid is
approximately 11.609977 ms even when the retained source recording has a
finer sample period. In the descending-scale session
`20260724T152536-b607d6fd4434`, most late scale gaps are 197–250 ms, while a
suspicious lower-pitch/upper-octave pair is one model frame apart. The new
labels expose both patterns directly.

The rough-rhythm guide uses only inter-onset gaps and one selected fixed-tempo
preset. At the default 120 BPM, the scale's roughly 200–250 ms gaps appear as
eighth-note glyphs. The most recent group remains a quarter-like pending mark
until the next onset supplies its interval. These are reversible display
settings retained in capture metadata, not changes to normalized events or
the model.

### Trailing commit lane is viable

The user proposed stabilizing the live view continuously instead of only at
Stop: run the stronger offline model over settled audio behind the play head
while Basic Pitch keeps the newest second responsive.

A simulation on the reference WAV decoded a sliding buffer ending `guard`
seconds behind the capture head and committed only the newly exposed interior
band, scored against Transkun's own full-file result:

```text
window guard  hop steps  decode  duty commits     P     R    F1  lat p50  lat max
    20     8    4     7   17.6s  0.51      97 0.928 0.938 0.933     9.4s    12.0s
    20     4    4     8   19.1s  0.55      95 0.947 0.938 0.942     5.9s     8.0s
    20     2    4     9   22.7s  0.65      99 0.929 0.958 0.944     4.0s     6.0s
    28     8    4     7   20.0s  0.58     100 0.940 0.979 0.959     9.4s    12.0s
```

A trailing lane recovers 93 to 96 percent of the full-file result at roughly
half of one core. Shrinking the right-edge guard from 8 s to 2 s costs nothing
measurable, while lengthening the buffer from 20 s to 28 s gives the best
agreement: this model wants past context, not future context, because its own
16-second internal segmentation already supplies local look-ahead.

Reported latencies are audio-time lag and exclude the roughly 2.5-second decode,
so expect about 6.5 s best case and 14 s worst case end to end.

Caveats: one unaligned take; the reference is the model's own full-file output
rather than ground truth; and the band filter is crude. Transkun exposes
`forcedStartPos`, `onsetBound`, and `mergeIncompleteEvent`, which appear
designed for exactly this stitching problem and were not used. The 0.5 duty
cycle is also wasteful, since each step recomputes work the previous step
already did.

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

The current architecture is the three-phase, unbounded-session design
sketched in
[`009-three-phase-unbounded-sessions.md`](../tactical/009-three-phase-unbounded-sessions.md):
a separate v2 live web application with a provisional Basic Pitch lane, a
trailing Transkun commit lane, and a separable engraving consumer. The first
two lanes and bounded storage/review surface are complete. The current score
consumer is an on-demand bounded-prefix snapshot, not the plan's final
monotonic `H_engrave`. Monotonic horizons plus bounded in-memory working sets
and segmented disk logs let capture run indefinitely without retaining the
whole session in RAM. V2 removes the two-minute cap; the v1 MVP remains
runnable and unchanged.

Bring up and stress the pipeline with both aligned fixtures and the checksummed
golden-reference WAV before microphone review. Preserve the existing
diagnostic fixture unchanged, and use the new 16-bar progression for repeated
musical correctness checks. The loop uses a continuous sample clock, records
each boundary, and compares each repetition with a single-take control rather
than merely checking that the process survives. Microphone testing is later
subjective confirmation of capture, room gating, clock mapping, and display
delivery.

The octave failure below no longer needs a dedicated Lane A fix if the trailing
commit lane demonstrates that it corrects the error a few seconds later using
a piano-specific model. That is a measured v2 acceptance criterion, not an
assumption that every octave error disappears.

The stable corrected-note milestone is recorded in
[`010-corrected-note-workbench-v2.md`](../tactical/010-corrected-note-workbench-v2.md).
The bounded internal score snapshot is recorded in
[`012-committed-score-snapshots.md`](../tactical/012-committed-score-snapshots.md).
The next Lane C architecture work, if requested, is progressive musical
chunking and reconciliation rather than another whole-prefix converter.

Do not tune the absolute-volume gate or add a generic harmonic filter for this
failure. The former cannot distinguish a new strike from loud resonance; the
latter would erase legitimate piano octaves and fifths.

Use raw mode and onset-score labels to compare low-note-only octave errors
against real octave dyads. Record representative lower and upper score pairs,
but do not treat score magnitude as calibrated probability.

Then record a short controlled local clip with low notes alone, their octave
partners alone, true octave dyads, lower-note-then-upper-note sequences,
isolated soft and loud notes, a held chord, repeated strikes, bass, treble, and
pedal. Retain or manually annotate enough onset truth to separate false
resonance starts from real reattacks.

If strict decoding still confuses sustained harmonics with new attacks, keep
the proven transport, clock, artifact, keyboard, and staff boundaries and open
the causal/piano-onset model bakeoff. An onset-specific or piano-specific lane
is more justified than adding a refractory period or harmonic filter without
ground truth.

The current display implementation records are
[`006-live-confidence-display-controls.md`](../tactical/006-live-confidence-display-controls.md)
and
[`007-live-timing-rhythm-guides.md`](../tactical/007-live-timing-rhythm-guides.md).

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
- Which raw/grouped window is most legible for chords, rolls, and fast melodic
  runs on the target piano?
- Which fixed-tempo rhythm preset makes runs and rolls easier to read without
  implying more musical structure than the onset stream contains?
- Are false upper-octave onsets marginal threshold crossings or confident
  learned-onset mistakes?
- Which remaining learned-onset responses in a controlled held-only clip are
  false, and do they justify a source-attack or active-note policy?
- Is the current named live-versus-final summary sufficient to explain changes
  to rolling-committed notes?
- What hop and commit horizon best preserve the current target-piano quality?
- Does pedal-aware streaming matter more than improving note-onset latency?
- When a remote accelerator is tested, is raw LAN PCM still acceptable or
  does codec latency and reliability become the next frontier?
