# 009 — Three-Phase Unbounded Sessions (v2 Plan)

Topic: live-acoustic-transcription

Status: plan sketch. Nothing implemented. Slice 1 is the only part scoped
tightly enough to start.

## Motivation

Two user requirements arrived together. The live view should stabilize into
something progressively more legible and more correct as playing continues,
using the trailing-commit evidence in
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
2. **Bounded state.** Each stage retains only the span between its horizon and
   `T_now`. Since every horizon advances at the same rate as `T_now`, that span
   is constant, so memory and per-second CPU are constant regardless of session
   length.

A session that runs for eight hours therefore costs the same per minute as one
that runs for two, and the only thing that grows is the append-only log on
disk.

## Lanes

### Lane A — provisional (unchanged)

The existing rolling Basic Pitch path: 1.988-second model windows, 250 ms hop,
strict onset 0.6, room-calibrated energy gate, edge guards, provisional and
committed lifecycle. It owns the sub-second feel: lit keys and onset ticks.

Nothing about Lane A changes except that its retention becomes bounded and its
output past `H_commit` is superseded rather than kept forever.

### Lane B — commit

Transkun over a trailing buffer. Measured starting point: 28-second buffer,
4-second hop, 2–4 second right guard. It decodes `[T_now - 28s, T_now - guard]`
and commits only the band the previous step did not cover.

Committed notes replace Lane A identities in the same span through the existing
reconciler. This is where octave errors disappear and where pedal first exists.

`H_commit` advances to the end of each committed band. Once it passes a span,
that span is final for the rest of the session.

Lane B must use Transkun's `forcedStartPos` / `onsetBound` /
`mergeIncompleteEvent` machinery rather than the crude onset-band filter the
simulation used, so notes spanning a commit boundary are stitched instead of
duplicated or dropped.

### Lane C — engrave

Score inference over settled spans. It consumes only `[H_engrave, H_commit]`,
never provisional notes, and emits measures that are appended and never
redrawn.

The hard part is that engraving boundaries are musical, not temporal. A span
may only be frozen at a barline the beat inference is confident about, so
`H_engrave` advances in jumps rather than smoothly and must be allowed to stall
when the music is ambiguous. A stalled `H_engrave` is a visible UI state, not
an error.

## What Gets Deleted

The current design cannot run indefinitely for four specific reasons, each of
which the horizon model removes:

| Current behavior | Why it blocks unbounded sessions | Replacement |
|---|---|---|
| two-minute session cap | a workaround for the three below | removed |
| every native probability window retained (~117 MiB per two minutes) | unbounded growth | retain only `[H_commit, T_now]`; optional bounded disk spill for diagnostics |
| full session PCM held in memory | unbounded growth | ~40 s RAM ring plus segmented append-only disk log |
| exact full-file adapter re-run at Stop | cost grows with session length; impossible for an hour | Lane B *is* the final pass; Stop only flushes the tail |

That last row is the biggest simplification. The project currently maintains
two different notions of "best transcript" — rolling committed events and a
separate final pass — and a named reconciliation between them. With Lane B
running continuously there is one transcript, and Stop stops being a
transcription event at all.

## Retention Policy

| Data | Retained for | Where | Growth |
|---|---|---|---|
| PCM ring | `T_now - 40 s` | RAM | constant |
| PCM log | whole session | disk, 60-second segments | ~345 MiB/hour at 48 kHz mono PCM16 |
| Lane A native arrays | `[H_commit, T_now]` | RAM | constant |
| Lane B native output | last decode only | RAM | constant |
| note events | whole session | append-only JSONL | ~10k notes/hour, negligible |
| engraved measures | whole session | append-only | negligible |

Segmenting the PCM log matters as much as bounding RAM: review and export must
never require loading an entire session.

## Backpressure

If Lane B cannot keep up, `H_commit` falls behind `T_now` and the provisional
zone grows. The policy must be explicit and must never drop audio:

1. lengthen Lane B's hop before anything else;
2. if lag still grows, shorten its buffer, accepting the measured quality cost;
3. surface the horizon lag directly in the UI; and
4. record lag distributions as a first-class metric.

Silence and long pauses are the easy case and should be exploited: Lane B can
skip decoding a band whose gate rejected every candidate, which is also what
makes an all-day idle session cheap.

## UI

Three zones on one timeline, visually distinct, with the horizons drawn as
lines the user can see moving:

- newest ~1 s: onset ticks and lit keys, obviously ephemeral;
- ~1 s to `H_commit`: provisional notes, faded or otherwise marked as revisable;
- `H_commit` to `H_engrave`: committed notes, stable, pedal shown; and
- past `H_engrave`: engraved measures.

Rendering must be virtualized — only the visible time range is drawn — or an
hour-long session will kill the page regardless of how good the backend is.

## Slices

Each becomes its own tactical when started. Only slice 1 is currently scoped
tightly enough to begin.

1. **Horizons and retention, Basic Pitch only.** Implement the horizon model,
   bounded retention, segmented PCM log, and virtualized UI. Remove the
   two-minute cap. No new model. This alone makes the current app unbounded and
   is independently valuable.
2. **Lane B.** Trailing Transkun with proper stitching, continuous
   reconciliation replacing the Stop-time final pass, backpressure policy.
3. **Lane C.** Engraving of settled spans with a stallable `H_engrave`.
4. **Long-session review and export.** Seek, scrub, and export without loading
   the whole session.

## Measurements To Require

- steady-state RSS and disk growth per minute over a session of at least
  30 minutes, and again at several hours;
- `H_prov`, `H_commit`, and `H_engrave` lag distributions, p50/p95/max;
- Lane A to Lane B correction rate: how many provisional notes are moved or
  retracted, and how visible that is;
- CPU duty per lane, and behavior when the machine is deliberately loaded;
- silence, pause, resume, disconnect, reconnect, and sleep/wake; and
- that a long session's committed transcript still matches a single offline
  Transkun pass over the same recorded audio.

That last one is the regression test that keeps the whole design honest.

## Risks And Open Questions

- **Deployment tension.** Transkun is a six-layer transformer plus a semi-CRF.
  Running it in browser WASM is implausible, so v2 is server-backed or a
  desktop application, which conflicts with
  [`browser-only-wasm-deployment.md`](../topics/browser-only-wasm-deployment.md).
  That topic's premise needs revisiting, or Lane B needs a smaller model.
- **Is Lane A still needed?** If Lane B's lag is acceptable, Lane A may only be
  earning the sub-second key-lighting feel. Worth testing by turning it off.
- **Identity churn.** A note that appears, then moves or vanishes several
  seconds later, may be more distracting than useful. The correction rate
  measurement should decide whether corrections are shown or applied silently
  behind a visual boundary.
- **Lane C on improvisation.** Beat inference was already shown to be the weak
  link on free playing. `H_engrave` may stall permanently on some material,
  which is honest but may feel broken.
- **Session identity.** An indefinite session has no natural end, so review,
  naming, and export need a concept the current job-directory model lacks.
