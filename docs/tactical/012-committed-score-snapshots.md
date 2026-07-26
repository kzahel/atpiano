# 012 — Committed Score Snapshots

Topic: performance-to-notation
Topic: live-acoustic-transcription

Status: in progress on 2026-07-26.

## Decision

Adopt MIDI2ScoreTransformer v0.0.1 as an internal score-inference experiment.
The user accepts its unresolved upstream license for this private,
non-distributed use. The runtime source, checkpoint, environment, and generated
scores remain ignored artifacts; atpiano tracks only acquisition facts,
checksums, its adapter, and the product contract.

OpenSheetMusicDisplay renders the transformer's MusicXML in the v2 page.
Rendering is not score inference and must remain replaceable.

## First Product Boundary

The upstream model consumes a complete performance MIDI and is not
incremental. The first v2 integration therefore produces an explicit
**committed score snapshot**, not a falsely append-only Lane C:

1. the user requests **Generate score**;
2. v2 snapshots latest committed note identities whose onsets are before
   `H_commit` and whose offsets are closed;
3. the snapshot MIDI and exact `H_commit` source sample are persisted;
4. a separate Python 3.11 CPU process runs MIDI2ScoreTransformer;
5. the resulting MusicXML and manifest are published atomically; and
6. OSMD replaces the prior rendered snapshot.

Each refresh may revise the entire score. The UI states the source-clock
boundary and never calls it final engraving. Recording and both transcription
lanes continue if setup, inference, or rendering fails.

This optional on-demand path is allowed to do work proportional to the
committed prefix for short internal sessions. It is capped and is not evidence
that Lane C supports indefinite automatic engraving. A later tactical must
establish musical chunk overlap, barline reconciliation, and `H_engrave`
before score work can run continuously on an unbounded session.

## Runtime Boundary

The score runtime is isolated from atpiano's pinned Python 3.10 environment:

```text
results/midi2score-runtime/
  .venv/                         Python 3.11
  MIDI2ScoreTransformer/         upstream source
  MIDI2ScoreTF.ckpt              released checkpoint
  runtime.json                   versions and checksums
```

The setup command pins:

- upstream MIDI2ScoreTransformer commit
  `115432bda16ca16e0fec2e9465788f2ba369971f`;
- checkpoint release `v0.0.1`, SHA-256
  `7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`;
- CPU execution because the known MPS path produced an empty score;
- the compatible Transformers version recorded by the bakeoff; and
- upstream custom `music21`, `score_transformer`, and `muster` dependencies.

The tracked adapter accepts only explicit repository, checkpoint, input MIDI,
and output MusicXML paths. It writes one machine-readable result and does not
read session audio or the event index.

## Piano-Roll Tail Rule

The solid right-edge bars currently turn an unknown release into a visually
asserted long duration. Replace that encoding:

- closed offset inside the viewport: solid duration bar;
- closed offset beyond the viewport: clipped solid bar with a continuation
  mark;
- open offset at or before `H_commit`: solid onset stub plus faint dashed tail
  ending at `H_commit`;
- open provisional offset after `H_commit`: solid onset stub plus faint dashed
  tail ending at the source head; and
- no open event uses the viewport edge itself as a synthetic offset.

## API And UI

The loopback API adds:

- `GET /api/score` for availability, active job, and latest snapshot;
- `POST /api/score` to claim one bounded background job; and
- a current MusicXML artifact route after success.

The independently toggleable **Score** view shows:

- the committed-through source time used by the snapshot;
- note count, generation duration, and stale/current state;
- Generate or Refresh action;
- a clear setup or inference error without affecting capture; and
- the OSMD-rendered grand staff plus MusicXML download.

## Acceptance

- unknown offsets no longer look like long known notes;
- fixture and microphone sessions can request a score before Stop;
- only committed, closed note identities enter snapshot MIDI;
- score execution is CPU-only, single-flight, timeout-bounded, and external to
  the workbench process;
- a newer session cannot publish an older job as its current score;
- the known generated musical fixture produces non-empty MusicXML through the
  actual checkpoint;
- OSMD renders the current artifact when available;
- missing runtime and model failures remain explicit and recoverable;
- v1 and stopped MIDI/JSONL export behavior remain unchanged; and
- the full regression suite passes.

