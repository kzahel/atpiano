# 023 — Backend Capability And Graceful Degradation

Master phase: 4. Python application core

Topic: acoustic-transcription-latency-quality

Topic: live-acoustic-transcription

Topic: linux-development-portability

Status: planned on 2026-07-26. Implement the policy and deterministic tests
after Tactical 022 supplies isolated worker measurements. Linux measurement
and product-mode acceptance remain mandatory.

## Outcome

Each local backend exposes a measured correction capability and every session
records the selected mode:

- **live correction** when sustained commit throughput has adequate headroom
  and the full correction-lag target is met;
- **delayed correction** when commit work may run safely beside ingest and
  preview but is expected to fall behind;
- **after-Stop correction** when concurrent commit work would threaten
  capture or preview responsiveness; and
- **unavailable** when the model, worker, or required resources cannot start.

Basic Pitch provisional feedback remains the prioritized live path in all
available modes. The UI states the selected correction behavior without
calling delayed output live.

## Invariants

1. Capability is derived from isolated, versioned measurements or an explicit
   user/developer override, not from processor names or package presence.
2. A profile names the model, checkpoint, adapter, settings, execution
   provider, thread limit, host class, and timing sample set that produced it.
3. Selection considers sustained service rate, tail latency, scheduler wait,
   algorithmic look-ahead, preview impact, and ingest impact. Mean inference
   time alone cannot establish live behavior.
4. Runtime pressure may demote a session to a safer mode. Automatic promotion
   does not oscillate within a running session.
5. Mode changes never drop acknowledged PCM, skip commit bands silently, or
   change decoder and hop policy without quality-parity evidence.
6. A profile is advisory. Ingest correctness continues to come from Tactical
   022 even when the profile is absent, stale, or wrong.

## Exact Scope

- Define a compact versioned backend-profile artifact and validation rules.
- Add an explicit local configuration for commit mode and thread limit.
- Select a conservative mode from a matching measured profile.
- Record the selected mode, reason, profile identity, and any runtime demotion
  in session status.
- Prioritize ingest, then preview, then commit. Score and compaction work must
  not silently take resources reserved for those stages.
- Show live, delayed, after-Stop, unavailable, and settling states in the
  shared application using additive runtime data where practical.
- Provide a reproducible capability command or validation lane using the
  fixed musical fixture, warm-up, controlled thread count, and repeated
  windows.

## Initial Linux Direction

The retained Linux evidence is insufficient for live correction. At the
better observed rate, one eight-second source hop takes about eleven seconds,
so the commit head advances at roughly 0.73 times real time. One hour of
continuous input would accumulate roughly sixteen minutes of source lag and
require roughly twenty-two more minutes to catch up after Stop. Later
contended runs were materially slower.

The host therefore defaults to after-Stop correction until isolated execution
proves that delayed background work preserves ingest and preview budgets.
That default is a conservative initial direction, not a processor-name rule.

## Acceptance

- Deterministic profile fixtures reject stale model, settings, provider, and
  thread-limit identities.
- Live is selected only with declared throughput and latency headroom.
- Delayed mode exposes growing `H_audio - H_commit` without capture failure.
- After-Stop mode starts no commit inference while capture is active and
  settles sequentially from durable audio afterward.
- Unavailable mode preserves recording and preview behavior.
- Forced resource pressure demotes safely and records the reason.
- The shared application clearly distinguishes capture complete from
  correction complete.
- Linux real-model results select the expected conservative mode and record
  the evidence used.

## Exclusions

- No checkpoint, decoder, reconciliation, or quality retuning.
- No automatic download of model packs.
- No general cross-machine benchmark leaderboard.
- No promise that a profile remains valid after model, runtime, power, or
  thread-setting changes.
- No use of a larger hop solely to improve throughput without separate
  quality-parity evidence.

## Execution Record

No implementation commits yet.
