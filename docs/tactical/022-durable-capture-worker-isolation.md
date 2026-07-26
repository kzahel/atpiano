# 022 — Durable Capture And Worker Isolation

Master phase: 4. Python application core

Topic: live-acoustic-transcription

Topic: multi-tenant-hybrid-service-architecture

Topic: long-session-storage-retention

Status: **implemented and locally validated on 2026-07-26; mandatory x86_64
Linux acceptance remains open.** This is the first Phase 4 implementation
slice and must pass that host review before the remaining extraction in
[`017-python-application-core.md`](017-python-application-core.md).

## Entry Evidence

- The real Linux Chrome fake-microphone run accepted 63.21 seconds of source
  audio in 168.63 seconds of wall time.
- Each of seven fixed-audio-head gaps matched one synchronous Transkun decode
  within about 40 ms.
- The session eventually completed with its full source range, committed
  events, exports, and playback audio, but the browser's 90-second Stop wait
  expired first.
- Basic Pitch preview and recording are viable on the host. Transkun commit
  inference is not sustainable at the current hop: the better Linux runs
  average about 11 seconds of decode work per eight seconds of source.
- The accepted architecture already assigns ingest, preview, and commit to
  separate logical roles and requires bounded queueing and explicit degraded
  modes.

This evidence establishes two independent facts. The host cannot advertise
current Transkun settings as live correction, and model execution in the
ingest call path is an architectural defect on every host.

## User-Visible Outcome

Microphone capture remains responsive even when preview or commit inference is
slow, blocked, or failed. The browser promptly releases the microphone after
Stop and leaves the session visibly **settling** while correction and export
work continue. Reloading or selecting that session reattaches to its durable
state instead of turning healthy background work into a capture failure.

The provisional and corrected note semantics, decoder parameters, source
clock, and model-quality tolerances do not change in this tactical.

## Invariants

1. Audio sample position remains the source timeline. Packet arrival, worker
   start, and worker completion remain diagnostics.
2. The ingest path validates continuity, appends recoverable PCM, advances
   `H_audio`, and acknowledges the accepted source horizon without invoking a
   model.
3. Acknowledged PCM exists in the session's durable source log before its
   ranges become eligible for worker scheduling.
4. Preview and commit inference execute in separately warmed operating-system
   processes. A blocked worker cannot block the WebSocket receive loop or the
   other model lane.
5. Each lane owns one running job and bounded pending scheduler state. Source
   audio and a durable next-required decode cursor replace queues of PCM blocks
   or one queued object per future decode.
6. Preview may coalesce obsolete provisional work only through an explicit
   recorded policy. Commit work remains sequential unless a separately tested
   quality policy says otherwise.
7. A worker reads a named session source range. It does not depend on that
   range still being present in the bounded in-memory PCM ring.
8. `H_prov` and `H_commit` advance only after their corresponding results are
   reconciled and persisted.
9. Stop freezes `H_audio` after the final ordered PCM block, records a durable
   settling transition, acknowledges capture completion, and closes the
   microphone independently of correction completion.
10. A correction or export failure does not erase or mislabel the accepted
    recording. Stage failure remains explicit in compact pipeline status.
11. V1 and the synchronous deterministic replay compatibility path remain
    runnable while the shared React microphone path adopts this coordinator.

## Exact Implementation Scope

### 1. Separate acceptance from model advancement

- Split `CorrectedSession.accept_block()` into a fast source-acceptance
  operation and independently callable lane advancement.
- Keep the existing synchronous method as a named compatibility composition
  for deterministic replay and focused lane tests.
- Serialize session mutation without holding a session lock across model
  inference.
- Make durable segmented audio provide bounded sample-range reads for a lane
  that has fallen behind the in-memory ring.

### 2. Bounded lane schedulers and worker processes

- Give preview and commit one coordinator-owned scheduler each.
- Warm both workers before the capture-ready message.
- Initialize models inside their worker processes so native dependencies,
  model memory, crashes, and thread pools are outside the ingest process.
- Pass bounded model inputs or durable range references through a versioned
  local worker protocol and return bounded native model output.
- Detect worker exit, protocol mismatch, stale result, and wrong-session
  result without publishing partial output.
- Limit commit-worker compute threads through an explicit local setting. Do
  not rely on process separation alone to preserve preview responsiveness.

### 3. Durable asynchronous Stop and settlement

- Close browser capture after final PCM acceptance and return a stopping
  session without waiting for either lane's tail flush.
- Continue lane finalization and export creation in background work owned by
  the session coordinator rather than by the WebSocket handler.
- Publish complete only after lane results, horizons, audio indexes, and
  exports are internally consistent.
- Preserve a failed stage and usable recording when correction or export
  cannot finish.
- Let ordinary session and horizon queries observe settlement. Reload does not
  require the original capture socket.

### 4. Operational evidence

Record separately:

- browser worklet frames produced and bytes queued;
- last received, durably accepted, and acknowledged source samples;
- transport receive and persistence latency;
- preview and commit eligible, running, and completed decode heads;
- scheduler wait, worker wall time, worker utilization, and process exit;
- `H_audio - H_prov` and `H_audio - H_commit`;
- pending-state and source-backlog high-water; and
- Stop-to-capture-close and Stop-to-session-complete durations.

The compact ordinary status stores aggregates and state transitions. Verbose
per-window evidence remains subject to the separate bounded debug policy.

## Explicit Exclusions

- No model, decoder threshold, reconciliation, pedal, or notation-quality
  change.
- No automatic hardware classification or live/delayed/post-Stop policy;
  Tactical 023 owns that product decision after isolated measurements exist.
- No hosted queue, PostgreSQL, object storage, authentication, Tauri shell, or
  sync implementation.
- No unbounded in-memory or on-disk decode-job queue.
- No attempt to make this Linux CPU sustain Transkun in real time.
- No longer Stop timeout presented as the correction.
- No assumption that MP3 is a transcription-safe source.

## Automated Acceptance

- A fake commit model blocked for longer than the test timeout cannot delay
  acknowledgement of later valid PCM blocks by the fake decode duration.
- A blocked commit worker does not prevent preview work from advancing.
- A commit lane more than one PCM-ring duration behind settles from durable
  source ranges with no missing or duplicated commit bands.
- Long accelerated input retains one running job and bounded pending state per
  lane rather than one job per block or decode head.
- Stop returns a stopping session promptly while an intentionally slow final
  decode continues, and later queries observe complete.
- Closing the capture WebSocket after acknowledged Stop does not abort the
  settling session.
- Worker failure leaves accepted audio readable and produces an explicit
  failed correction stage.
- Stale, duplicate, wrong-session, and out-of-order worker results cannot
  advance a horizon.
- Existing rolling quality fixtures remain within their declared tolerances.
- V1, v2, shared React, contract, and migration regression lanes remain green.

## Local Validation Before Linux

The implementation may proceed on macOS through:

1. deterministic slow and blocked fake-model tests;
2. a source duration greater than the configured PCM ring;
3. browser-runtime Stop and reload tests with settlement longer than the old
   timeout;
4. worker kill and malformed-result injection;
5. bounded scheduler and storage accounting assertions; and
6. ordinary replay and frontend regression gates.

Use portable process startup semantics. Passing on macOS must not depend on
Linux `fork`.

## Mandatory Linux Acceptance

Do not mark this tactical complete until the slower host demonstrates:

- real model workers start and warm with the locked environment;
- commit thread limits and priority settings are recorded;
- a 60-second Chrome fake-microphone capture keeps `H_audio` near the browser
  source head without decode-shaped plateaus;
- Basic Pitch preview remains responsive while Transkun is saturated;
- Stop releases capture promptly and settlement survives reload;
- source duration and checksums cover every accepted frame;
- worker and transport high-water metrics are distinct; and
- a longer soak leaves bounded scheduler state, explicit correction backlog,
  and no anonymous temporary files.

## Rollback

The new coordinator remains behind the shared local runtime. Disabling it
returns that runtime to the current synchronous corrected-session composition;
v1 and v2 compatibility commands remain independent fallbacks. New session
artifacts must remain readable after rollback.

## Planned Commit Slices

1. Split durable source acceptance from synchronous lane processing.
2. Add bounded asynchronous per-lane scheduling and slow-worker evidence.
3. Move preview and commit models into separately warmed processes.
4. Make Stop a prompt durable settling transition with background exports.
5. Add worker failure, restart, backlog, and resource-accounting evidence.
6. Run local validation, prepare the Linux packet, and stop for host review.

## Execution Record

The host-independent implementation landed as a bounded series:

1. `4a37604` split durable PCM acceptance from synchronous lane work and
   allowed lanes to read ranges older than the memory ring.
2. `0d741bf` added independent bounded lane schedulers, immediate block
   acknowledgement, and prompt background Stop settlement.
3. `92d0c9d` moved Basic Pitch and Transkun behind portable spawned worker
   processes and limited Transkun to an explicit thread budget.
4. `16e5864` added live, delayed, after-Stop, and unavailable correction
   behavior without changing decoder or reconciliation policy.
5. `677106a` retained compact pipeline and browser transport high-water
   evidence and made process-interrupted sessions explicit recoverable
   failures rather than permanent workspace blockers.
6. `bbdd548` added durable catch-up, killed-worker, and malformed-result
   acceptance tests.
7. `f0a8d5e` made worker failure an explicit unavailable correction stage and
   replaced an exited warmed model before a later session.

The React microphone path now sends every binary block through
`CorrectedSessionPipeline.accept_block`. That call only validates and appends
PCM, advances the audio horizon, and wakes the two lane threads. Each thread
owns one synchronous request to its separately spawned model process, so
there is no queue of future PCM objects or decode jobs. Commit catch-up reads
the named source range from segmented WAV when the range has left the
40-second memory ring.

Stop closes and indexes accepted audio, persists `stopping`, responds on the
capture socket, and lets lane finalization and exports continue under the
server-owned pipeline. The shared runtime waits ten seconds only for this
acknowledgement; it no longer treats background correction as a 90-second
capture operation. Ordinary session and horizon requests expose settlement,
so a browser reload reattaches without the capture socket.

The final session manifest retains accepted block/frame counts, ingest
append time, per-lane run counts and wall time, lane errors, and the two
correction lags. Browser Stop evidence separately retains sent and
acknowledged frames/blocks plus WebSocket buffered-byte current and
high-water values. Worker status reports process ID, liveness, request count,
thread limit, and wall-time aggregates.

Local validation includes:

- blocked commit inference while later PCM is acknowledged within the test
  bound and preview advances independently;
- after-Stop commit catch-up from source ranges older than the PCM ring;
- prompt Stop followed by observable completion;
- browser transport evidence and pipeline evidence persistence;
- spawned-process startup, abrupt exit, and malformed result rejection;
- lane failure preserving accepted audio and completing with an explicit
  stage error;
- a simulated server restart changing orphaned active or stopping work to an
  explicit failed-but-preserved session rather than blocking new capture;
- 104 passing Python tests, generated-contract parity, TypeScript validation,
  40 focused frontend tests, and a successful production build.

The full migration command's application lane is intermittently blocked by
the separate in-progress score-reader test expecting four pages before its
render observer updates. Python, contracts, lint, syntax, and whitespace
lanes passed; this tactical did not modify that notation path.

Automatic continuation after a full host-process exit is not implemented.
Such an interruption now preserves and labels the recording but requires
correction to be rerun. Browser reload while the server remains alive does
continue to observe healthy settlement.

Do not mark this tactical complete or resume Tactical 017 until the mandatory
Linux checks above establish that the real browser head no longer develops
decode-shaped ingest plateaus and that Basic Pitch remains responsive while
the isolated Transkun worker is saturated.
