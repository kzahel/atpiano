# 009 — Three-Phase Unbounded Sessions (v2 Plan)

Topic: live-acoustic-transcription

Status: plan sketch for a separate v2 successor. Nothing implemented. Slice 1
is the only part scoped tightly enough to start.

## Product And Version Boundary

The existing `uv run atpiano workbench` application is the v1 MVP. It remains
runnable with its current behavior, session artifacts, review path, and tests.
This plan does not migrate, replace, or remove it.

V2 is a new live web application with a separate CLI entry point, frontend,
session schema, and artifact namespace. Slice 1 will choose their exact names.
V2 should reuse proven capture, transport, clock, model-adapter, and normalized
event code where that does not couple its lifecycle to v1. Shared internals are
desirable; changing the v1 product contract is not.

All references below to removing, replacing, or superseding behavior apply
only to v2. Existing v1 sessions must remain reviewable, and a v1 smoke test is
an acceptance requirement for every v2 slice that touches shared code.

## Motivation

Two user requirements arrived together for the new v2 application. Its live
view should stabilize into something progressively more legible and more
correct as playing continues, using the trailing-commit evidence in
[`live-acoustic-transcription.md`](../topics/live-acoustic-transcription.md).
And a session must be able to run indefinitely without growing less efficient,
replacing the current two-minute cap.

Those are one problem. Unbounded sessions are only possible if every stage has
a point past which it stops revising and stops retaining, and progressive
stabilization is exactly the mechanism that supplies those points.

## The Horizon Model

The whole design rests on one abstraction. Four monotonically advancing
timestamps on the audio sample clock, which never regress:

```text
   older ──────────────────────────────────────────────────► T_now
        H_engrave        H_commit          H_prov        capture head
            │                │                │               │
  engraved  │   committed    │   provisional  │   in-flight   │
  immutable │  notes stable  │  may move/die  │  not decoded  │
```

| Horizon | Typical lag | Set by | Meaning |
|---|---|---|---|
| `H_prov` | ~1 s | Lane A commit policy | Basic Pitch has decoded past here |
| `H_commit` | ~6–14 s | Lane B band advance | Transkun has committed past here |
| `H_engrave` | ~20–40 s | last settled barline | notation frozen past here |

Two invariants follow, and everything else is a consequence:

1. **Immutability.** No stage may alter data older than its own horizon.
2. **Bounded active state.** Each stage has a fixed-size in-memory working set.
   Backlog awaiting a slow or stalled stage lives in segmented append-only
   storage and is reloaded in bounded windows; no in-memory object graph grows
   with session length.

When the horizons advance normally, an eight-hour session therefore has the
same steady-state memory and per-second CPU cost as a two-minute session. The
append-only logs on disk grow with elapsed audio. A stalled `H_commit` or
`H_engrave` may also grow a disk-backed backlog, but must not grow RAM or the
amount of work attempted per scheduler tick without bound.

## Lanes

### Lane A — provisional

The v2 provisional lane starts with the existing rolling Basic Pitch
algorithm: 1.988-second model windows, 250 ms hop, strict onset 0.6,
room-calibrated energy gate, edge guards, and provisional and committed
lifecycle. It owns the sub-second feel: lit keys and onset ticks. The v1
implementation remains unchanged.

Nothing about Lane A changes except that its retention becomes bounded and its
output past `H_commit` is superseded in v2's materialized view rather than kept
in memory forever. Its append-only event history still records what the user
saw and how Lane B revised it.

### Lane B — commit

Transkun over a trailing buffer. Measured starting point: 28-second buffer,
4-second hop, 2–4 second right guard. It decodes `[T_now - 28s, T_now - guard]`
and commits only the band the previous step did not cover.

Committed notes replace Lane A identities in the same span through the existing
reconciler. This lane is expected to correct most of the octave errors observed
in Lane A and is where pedal first exists. The correction rate and remaining
errors are acceptance measurements, not assumed outcomes.

`H_commit` advances to the end of each committed band. Once it passes a span,
that span is final for the rest of the session.

Lane B must use Transkun's `forcedStartPos` / `onsetBound` /
`mergeIncompleteEvent` machinery rather than the crude onset-band filter the
simulation used, so notes spanning a commit boundary are stitched instead of
duplicated or dropped.

Only after repeated-WAV and finite full-file comparisons pass may Lane B
replace v2's Stop-time final pass. V1 keeps its existing exact Basic Pitch
full-file pass regardless.

### Lane C — engrave

Score inference over settled spans. It consumes bounded candidate windows from
the committed event log beginning at `H_engrave`, never provisional notes, and
emits measures that are appended and never redrawn. It must not load the whole
`[H_engrave, H_commit]` range at once.

The hard part is that engraving boundaries are musical, not temporal. A span
may only be frozen at a barline the beat inference is confident about, so
`H_engrave` advances in jumps rather than smoothly and must be allowed to stall
when the music is ambiguous. A stalled `H_engrave` is a visible UI state, not
an error. During a stall, committed input remains in segmented storage and
Lane C's RAM working set stays bounded.

## What V2 Replaces

Copying four v1 behaviors into v2 would prevent unbounded sessions. V2 replaces
them as follows; none is deleted from v1:

| V1 behavior | Why it blocks unbounded v2 sessions | V2 replacement |
|---|---|---|
| two-minute session cap | a workaround for the three below | removed |
| every native probability window retained (~117 MiB per two minutes) | unbounded growth | retain a capped recent diagnostic window; optionally spill bounded segments to disk |
| full session PCM held in memory | unbounded growth | ~40 s RAM ring plus segmented append-only disk log |
| exact full-file adapter re-run at Stop | cost grows with session length; impossible for an hour | Lane B *is* the final pass; Stop only flushes the tail |

That last row is the biggest v2 simplification. V1 maintains two different
notions of "best transcript" — rolling committed events and a separate final
pass — and a named reconciliation between them. Once Lane B passes its
acceptance gate, v2 has one transcript and Stop stops being a transcription
event at all.

## Retention Policy

| Data | Retained for | Where | Growth |
|---|---|---|---|
| PCM ring | `T_now - 40 s` | RAM | constant |
| PCM log | whole session | disk, 60-second segments | ~345 MiB/hour at 48 kHz mono PCM16 |
| Lane A native arrays | fixed recent diagnostic window, with a hard cap chosen in slice 1 | RAM; optional bounded disk spill | constant |
| Lane B native output | last decode only | RAM | constant |
| note events and revisions | whole session | append-only JSONL; bounded active index in RAM | ~10k notes/hour, negligible on disk |
| Lane C unsettled input | until engraved or exported | segmented committed-event log | disk-backed backlog if engraving stalls |
| engraved measures | whole session | append-only disk log; visible measures only in RAM | negligible on disk |

Segmenting the PCM log matters as much as bounding RAM: review and export must
never require loading an entire session. The same rule applies to event logs
and an engraving backlog.

## Backpressure

If Lane B cannot keep up, `H_commit` falls behind `T_now` and the provisional
zone grows on disk, not in RAM. Lane A native arrays remain capped, normalized
events are appended, and reconciliation reloads only the band Lane B is
committing. The policy must be explicit and must never drop audio:

1. lengthen Lane B's hop before anything else;
2. if lag still grows, shorten its buffer, accepting the measured quality cost;
3. surface the horizon lag directly in the UI; and
4. record lag distributions as a first-class metric.

Silence and long pauses are the easy case and should be exploited: Lane B can
skip decoding a band whose gate rejected every candidate, which is also what
makes an all-day idle session cheap.

## V2 UI

Three zones on one timeline, visually distinct, with the horizons drawn as
lines the user can see moving:

- newest ~1 s: onset ticks and lit keys, obviously ephemeral;
- ~1 s to `H_commit`: provisional notes, faded or otherwise marked as revisable;
- `H_commit` to `H_engrave`: committed notes, stable, pedal shown; and
- past `H_engrave`: engraved measures.

Rendering must be virtualized — only the visible time range is drawn — or an
hour-long session will kill the page regardless of how good the backend is.

## Deterministic WAV Bring-Up

Microphone performance is not the first integration input. V2 must provide a
file-source adapter that feeds sample-indexed PCM blocks into the same session
engine, scheduler, model lanes, reconciliation, persistence, and event
delivery used after live capture. It must support both one-shot wall-clock
replay and indefinite repetition without resetting the session.

The existing 12.25-second `deterministic-midi-smoke-v2` fixture remains frozen.
Its deliberately isolated 19 events protect historical decoder and latency
evidence, but it is not a musical performance and must not be stretched into
one.

Slice 1 adds a second aligned fixture,
`deterministic-musical-loop-v1`, specifically for v2 integration:

- 16 bars of 4/4 at 96 BPM, approximately 40 seconds of music, preceded by
  calibration silence and followed by a deterministic release tail;
- an eight-bar C-major progression
  `C - G/B - Am - F - Dm - G7 - C - C`, repeated with a different texture;
- a first section with bass notes, inversions, block triads, a dominant
  seventh, and a simple right-hand melody;
- a second section with an explicit low-high-middle-high Alberti pattern under
  a varied melody, ending with block-chord cadence evidence;
- fixed dynamics, repeated-note reattacks, pedal changes at declared harmonic
  boundaries, and useful bass, middle, and treble coverage; and
- a resolved final tonic plus silence so ordinary repetitions do not create an
  unexplained chord collision at the loop boundary.

The Standard MIDI File is the structural source of truth and the WAV is
rendered by the repository-owned deterministic synthesizer. The manifest
records tempo, meter, bar boundaries, harmonic labels, texture sections,
pedal intervals, renderer version, and hashes of both files. Structural tests
must assert the progression, simultaneous chord onsets, the Alberti pitch
order, repeated strikes, pedal changes, duration, register coverage, and
byte-identical regeneration. It is still a synthetic model diagnostic, not a
claim that the renderer sounds like the target acoustic piano.

The bring-up sequence is:

1. run the frozen diagnostic fixture once to preserve its historical
   assertions;
2. run the aligned musical-loop fixture once for exact source-clock,
   note-event, pedal, harmony-section, and texture assertions;
3. repeat the musical-loop fixture on one continuous sample clock and require
   the same aligned note result on every ordinary repetition, while scoring
   synthetic loop boundaries separately;
4. run the checksummed golden-reference WAV once and compare each lane with its
   established offline or finite-replay control;
5. repeat the golden-reference WAV at wall-clock cadence for at least 30
   minutes and then for several hours to measure resource stability and output
   repeatability; and
6. only then use a real microphone session for subjective capture, room-gate,
   browser-clock, and end-to-end paint confirmation.

Loop repetitions use one continuous sample clock. Every boundary and any
declared silence inserted between repetitions is recorded in the manifest.
Boundary bands are reported separately because joining the end of an
improvisation directly to its beginning creates audio context that was not in
the original take. Each completed repetition is compared with the single-take
control within a declared event-matching tolerance; it is not enough merely
for the process to stay alive.

The golden-reference take has no aligned MIDI, so it can prove repeatability,
agreement with offline model output, horizon advancement, bounded resource
use, and stable UI delivery, but not absolute transcription accuracy. The
two MIDI-derived fixtures remain the automated correctness oracles. Generated
loop audio and results stay outside Git.

## Slices

Each becomes its own tactical when started. Only slice 1 is currently scoped
tightly enough to begin.

1. **V2 foundation, horizons, and retention; Basic Pitch only.** Add the
   separate v2 entry point, frontend, schema, and artifact namespace. Add the
   aligned musical-loop fixture plus one-shot and looping WAV replay first,
   then implement the horizon model, bounded retention, segmented PCM log, and
   virtualized UI. V2 has no two-minute cap. No new model. V1 remains runnable
   and unchanged.
2. **Lane B.** Trailing Transkun with proper stitching, continuous
   reconciliation, repeated-WAV parity, backpressure policy, and only then
   replacement of v2's Stop-time final pass.
3. **Lane C.** Engraving of settled spans with a stallable `H_engrave`.
4. **Long-session review and export.** Seek, scrub, and export without loading
   the whole session.

## Measurements To Require

- steady-state RSS and disk growth per minute over a session of at least
  30 minutes, and again at several hours, using deterministic looping WAV
  replay before microphone testing;
- `H_prov`, `H_commit`, and `H_engrave` lag distributions, p50/p95/max;
- Lane A to Lane B correction rate: how many provisional notes are moved or
  retracted, and how visible that is;
- per-repetition event-count, pitch, onset, offset, pedal, and boundary-band
  variance against the single-take control;
- aligned note precision, recall, F1, pedal metrics, and source-clock error on
  every repeated deterministic musical-loop fixture;
- CPU duty per lane, and behavior when the machine is deliberately loaded;
- silence, pause, resume, disconnect, reconnect, and sleep/wake; and
- that each repeated take's committed transcript remains within a declared
  tolerance of a single offline Transkun pass over that take, with loop
  boundaries scored separately.

That last one is the regression test that keeps the whole design honest.

## Risks And Open Questions

- **Deployment is no longer a constraint.** The user clarified that
  browser-only WASM was an appealing idea rather than a requirement, and that
  any backend including NVIDIA/CUDA is acceptable if it clearly wins.
  [`browser-only-wasm-deployment.md`](../topics/browser-only-wasm-deployment.md)
  is deprioritized accordingly, and v2 is host-executed. The remaining
  obligation is the existing guardrail: accelerator code stays behind the model
  adapter, and every backend is validated against a known-good CPU result,
  because a bad backend fails silently rather than loudly.
- **V1 compatibility.** Shared internals must not make the MVP a compatibility
  alias for v2. Its command, frontend behavior, session artifacts, final pass,
  and review path remain protected by smoke tests.
- **Is Lane A still needed?** If Lane B's lag is acceptable, Lane A may only be
  earning the sub-second key-lighting feel. Worth testing by turning it off.
- **Identity churn.** A note that appears, then moves or vanishes several
  seconds later, may be more distracting than useful. The correction rate
  measurement should decide whether corrections are shown or applied silently
  behind a visual boundary.
- **Lane C on improvisation.** Beat inference was already shown to be the weak
  link on free playing. `H_engrave` may stall permanently on some material,
  which is honest but may feel broken. A stall must accumulate only a
  disk-backed backlog, never an unbounded in-memory range.
- **Session identity.** An indefinite session has no natural end, so review,
  naming, and export need a concept the current job-directory model lacks.
