# 023 — Backend Capability And Graceful Degradation

Master phase: 4. Python application core

Topic: acoustic-transcription-latency-quality

Topic: live-acoustic-transcription

Topic: linux-development-portability

Status: **complete on 2026-07-27. Profile identity, automatic selection,
explicit modes, Linux real-model measurement, browser acceptance, and one-way
real-load demotion are validated.**

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

`16e5864` added explicit session behavior for live, delayed, after-Stop, and
unavailable correction. After-Stop starts no commit inference during capture;
unavailable preserves recording and Basic Pitch preview. The selected mode
and reason are visible in the shared application and retained with the
session.

`8fad2a3` added `atpiano.backend-profile.v1` and the
`atpiano profile-backend` command. A profile records:

- model, version, adapter, checkpoint and configuration hashes, device, and
  thread limit;
- operating-system, machine, processor, and logical-CPU host class;
- fixture manifest and audio hashes, sample rate, source length, repetitions,
  silence, and warm-up duration;
- commit buffer, base and maximum hop, guard, and minimum context; and
- every decode wall-time sample plus total, mean, p95, maximum, service
  ratio, and maximum-to-base-hop ratio.

The command warms one isolated Transkun worker, runs the fixed musical
fixture through the ordinary corrected replay, and retains the full session
and per-decode evidence beside the compact profile. The profile ID is a
SHA-256 digest of its versioned contents.

Automatic mode is now the local default. A missing, invalid, wrong-host,
wrong-model, wrong-checkpoint, wrong-device, wrong-thread, or wrong-scheduler
profile selects after-Stop. A matching profile selects live only when
measured total service ratio is at most 0.75 and the maximum decode is at most
0.85 of the four-second base hop. Sustainable throughput below source rate
without that headroom selects delayed; service ratio at or above one selects
after-Stop. Explicit configuration remains available for diagnosis and is
recorded as such.

The local Apple Silicon validation used the 42-second musical fixture,
Transkun 2.0.1, CPU execution, and two Torch threads. After an unmeasured
16-second-source warm-up, eight decodes took 27.991 seconds total, 3.499
seconds mean, 3.843 seconds p95 and maximum. The 0.666 service ratio was
sustainable, but the 0.961 maximum-to-base-hop ratio lacked live headroom, so
the matching profile selected **delayed**. This establishes the command and
selector on this host; it is not a Linux capability claim.

`f0a8d5e` added one-way runtime demotion. A live session whose commit decode
exceeds its base hop becomes delayed. A live or delayed session whose decode
exceeds the configured maximum hop defers subsequent commit work until Stop.
Commit worker failure becomes unavailable while PCM capture and preview
continue. No automatic promotion occurs within the session, each reason is
retained, and a dead warmed worker is replaced before the next session.

The Linux packet completed on 2026-07-27. Profile
`3616915c6b4dea54dcd617bd74e3b034634c8edcea505159ffcace550b3a18f9`
used the fixed two-repeat, 84-second musical source, Transkun 2.0.1 on CPU,
and two Torch threads. Ten measured decodes took 180.235 seconds total,
18.024 seconds mean, and 19.491 seconds maximum. Its 2.146 service ratio
selected **after-Stop**, with the reason that decode service cannot keep up
with continuous source audio.

The matching-profile Chrome session retained that profile ID and mode,
accepted 60.693 source seconds in 60.687 wall seconds, ran no commit inference
during capture, acknowledged Stop in 0.257 seconds, survived an immediate
reload, and settled seven real decodes from durable audio. A separate explicit
delayed-mode diagnostic saturated Transkun during capture. Its 14.566-second
first decode did not interrupt PCM acceptance or the one-second Basic Pitch
preview lag, and the session demoted one way to after-Stop with the exact
eight-second maximum-hop reason. Stop acknowledged in 0.258 seconds and the
session completed every accepted frame and export.

These results satisfy the real-host selection, user-visible mode, safe
demotion, and preserved-capture acceptance criteria. They do not promote this
Linux backend to delayed or live correction; after-Stop remains the measured
automatic choice.
