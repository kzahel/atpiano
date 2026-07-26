# 017 — Framework-Independent Python Application Core

Master phase: 4. Python application core

Topic: multi-tenant-hybrid-service-architecture

Topic: session-workspace-management

Topic: long-session-storage-retention

Status: planned and authorized on 2026-07-26 after accepted R3 review and
storage-direction clarification. Its application-core implementation has not
started. The Linux browser evidence subsequently made
[`022-durable-capture-worker-isolation.md`](022-durable-capture-worker-isolation.md)
and
[`023-backend-capability-degradation.md`](023-backend-capability-degradation.md)
prerequisite Phase 4 slices. Their host-independent work has landed; this
tactical remains paused for their mandatory Linux evidence. R4 remains the
combined parity and storage-behavior review before Phase 5.

## Entry Evidence

- Phase 3 and R3 are complete under
  [`016-shared-react-application.md`](016-shared-react-application.md).
- The React application consumes the hand-owned `AtpianoRuntime` boundary and
  is accepted with deterministic replay, microphone capture, Stop, history,
  recoverable deletion, score jobs, artifacts, and synchronized audio
  playback.
- The current local provider reaches those behaviors through the
  proof-of-concept `CorrectedWorkbenchServer`, which still owns HTTP, capture,
  session selection, score-job state, artifact finalization, and recovery in
  one composition.
- `LocalSessionStore` supplies useful session-addressed filesystem behavior,
  but it is an adapter rather than the application policy owner.
- Current stopped sessions retain segmented 48 kHz PCM16 WAV at about
  345.6 MB/hour plus a derived 128 kbps playback MP3 at about 57.6 MB/hour.
  The MP3 is already accepted for playback and scrubbing but currently
  increases, rather than reduces, total disk use.
- Detailed model windows and traces are useful for local failure diagnosis,
  not ordinary user-session content.
- The former WebSocket ingest path invoked preview and commit lanes
  synchronously. Slow Transkun inference on Linux blocked PCM acceptance and
  exposed Stop settlement as transport failure. Tactical 022 has corrected
  that call path locally; its mandatory Linux rerun must pass before this
  broader extraction preserves the new behavior.

## User-Visible Outcome

The accepted Phase 3 application behaves the same through a thinner local
transport backed by framework-independent Python services. Replay,
microphone capture, live and committed notes, Stop and settling, history,
playback and scrubbing, scoring, artifact access, and recoverable deletion
retain their current `AtpianoRuntime` behavior.

New Phase 4 sessions also exercise an explicit local storage policy:

- ordinary sessions retain the existing 128 kbps MP3 as the interim compact
  playable recording after verified finalization;
- raw WAV segments are temporary capture input and are retired only after the
  compact recording is known to be usable;
- ordinary sessions retain normalized musical data and a small pipeline
  status summary, not verbose model evidence; and
- local debug data is off by default, separately classified, capped, and
  disposable.

This is an interim local retention choice, not a declaration that MP3 is the
permanent archival codec. Existing v1, v2, and historical session directories
are not rewritten.

## Invariants

1. The React `AtpianoRuntime` interface and accepted Phase 3 behavior remain
   stable. Additive internal Python APIs do not force a frontend redesign.
2. Source audio samples remain the authoritative timeline during capture.
   Stored recording artifacts declare their complete source range and sample
   mapping.
3. Every session read, capture operation, job, artifact operation, and delete
   operation names explicit workspace and resource IDs.
4. Selecting history cannot retarget capture, scoring, artifact publication,
   finalization, or deletion.
5. Python application services import neither HTTP-server nor browser code.
6. Filesystem, SQLite, FFmpeg, wall-clock, free-space, model-process, and
   score-process details remain behind adapters used by the application core.
7. The local coordinator retains at most one active capture and one score job
   initially; those are explicit local policy constraints, not domain
   invariants for hosted workspaces.
8. Artifact publication and audio compaction are transactional. A crash may
   leave a recoverable raw segment, never a manifest that points only to a
   missing or invalid compact recording.
9. Debug cleanup cannot remove the user's retained recording, musical events,
   annotations, or explicitly retained exports.
10. V1 and v2 commands and existing session formats remain runnable and
    readable without migration.

## Exact Implementation Scope

### 1. Application package and service boundaries

Create a small `atpiano.application` package containing framework-independent
services for:

- workspace and session catalog queries;
- capture Start, PCM append, Stop, settling, and finalization coordination;
- historical session, horizon, and bounded event reads;
- score-job start, status, failure, and publication;
- artifact listing, access authorization, publication, and lifecycle;
- recoverable session deletion; and
- workspace storage accounting, ordinary retention, and debug retention.

Extract proven behavior from `CorrectedWorkbenchServer` and
`LocalSessionStore`; do not reimplement transcription, reconciliation, or
score selection from their documentation. The application layer may compose
the existing corrected-session engine behind a focused adapter while that
engine remains useful.

The expected dependency direction is:

```text
contracts + transcription/score behavior
                    ^
                    |
          application services
                    ^
                    |
 local filesystem / SQLite / encoder / process adapters
                    ^
                    |
       HTTP, replay CLI, and microphone composition
```

Introduce only ports consumed by this executable slice. Do not create
interfaces for future cloud databases, object stores, queues, accounts, or
sync.

### 2. Session, capture, and historical-read extraction

- Move active-capture ownership and lifecycle transitions out of the HTTP
  server.
- Make replay and microphone use the same application capture service after
  their source adapters produce sample-indexed PCM.
- Preserve bounded PCM/model execution and monotonic audio, provisional, and
  commit horizons.
- Move catalog, explicit resolution, session summaries, event paging, and
  restart recovery behind application queries.
- Preserve existing-session compatibility through the local adapter; do not
  mutate historical manifests while reading them.
- Return structured application errors that the local HTTP adapter translates
  to the existing runtime errors.

### 3. Score jobs, artifacts, and deletion extraction

- Move target freezing, single-job coordination, status, cancellation
  boundaries, failure isolation, and publication out of the server.
- Keep score input fixed to the named session and commit horizon.
- Centralize artifact classification and publication so playback audio,
  event history, MIDI, MusicXML, debug data, temporary files, and trash are
  not discovered through unrelated route-specific filesystem scans.
- Preserve byte-range artifact access and the exact selected-session target.
- Make recoverable deletion an application operation with active-capture and
  running-job guards. Permanent purge and restore remain outside this phase.

### 4. Ordinary recording finalization

Use the already implemented 128 kbps MP3 path as the first compact ordinary
recording format for new Phase 4 sessions:

1. PCM remains available to the live transcription path and a bounded raw
   capture spool.
2. Closed raw audio is handed to an application-owned recording finalizer
   through a local encoder adapter.
3. The compact representation records byte count, checksum, source start,
   source frame count, sample rate, media type, and encoder settings.
4. Raw segments remain until the compact audio is decodable, covers the
   declared source range, is durably published, and every enabled
   transcription lane has advanced its earliest required read cursor beyond
   the segment.
5. Verified raw segments are retired without leaving an untracked duplicate.
6. Stop finalizes a seekable complete-session playback view. The existing
   React transport must still play, seek, and move exact-sample inspection
   across the entire session.

The adapter may use one recoverable encoder stream or bounded compact
segments. Its encoder backlog and open file count must not grow with total
session duration. Raw transcription source may grow with the explicitly
reported `H_audio - H_commit` backlog on a delayed or after-Stop backend; it is
not a decode-job queue and it cannot be retired merely because a playback MP3
exists. After successful settlement, its temporary raw source must be retired
without unexplained growth. Codec delay, padding, and segment boundaries must
be represented well enough that playback remains aligned to the source sample
clock.

If the encoder is unavailable or finalization fails, preserve the raw audio,
mark compaction incomplete in pipeline status, and keep WAV playback working.
Never delete the only usable recording.

The compact-retention mode applies only to sessions created through the new
Phase 4 core. It remains explicitly enabled during implementation and becomes
the ordinary default only if R4 accepts the lossy-storage tradeoff. No
background migration touches older sessions.

### 5. Pipeline status and bounded local debug data

Add a compact, size-bounded session status record containing:

- application, model, decoder, and encoder versions;
- stage transitions and final state;
- source and processed horizons;
- aggregate event, error, and timing counts; and
- explicit gaps, failed jobs, incomplete compaction, or recovery decisions.

The ordinary policy does not retain model-native arrays, repeated
intermediate audio, or verbose per-window traces after their bounded live
use.

Debug policy is separate and off by default. When enabled, it requires byte
and age caps, rotates oldest unpinned debug data first, records truncation,
and supports an explicit local pin or export. Tests use deliberately small
limits; selecting permanent product defaults is not required for Phase 4.
Debug data is never uploaded by this tactical.

### 6. Storage accounting and low-disk behavior

The application service reports workspace and current-session bytes by:

- retained recording;
- events and indexes;
- derived artifacts;
- debug data;
- temporary/raw data; and
- recoverable trash.

It also reports observed current-session bytes/hour and the configured
free-space reserve. Capture warns through existing status/error mechanisms
and stops explicitly before it can no longer safely publish another bounded
unit. It does not automatically delete user sessions.

No new React storage-management screen is required. R4 receives the
machine-readable report and a concise before/after summary; a later additive
runtime capability may expose it in the product UI.

### 7. Thin adapters and compatibility

- Convert the proof-of-concept HTTP handler to request parsing, application
  calls, response mapping, WebSocket transport, and file-body delivery.
- Have deterministic replay and the local FastAPI-compatible path call the
  same application services.
- Keep the current `AtpianoRuntime` provider behavior and generated contract
  fixtures stable.
- Retain named compatibility shims for v1 and v2 with explicit removal
  conditions.
- Do not make the Phase 4 application package depend on a global singleton
  server or process-current session.

## Explicit Exclusions

- No React redesign, storage dashboard, new session-management interaction,
  or breaking `AtpianoRuntime` change.
- No Tauri shell, sidecar packaging, hosted service, authentication,
  PostgreSQL, object storage, cloud quota, collaboration, or sync.
- No permanent purge, automatic deletion of user sessions, restore UI,
  continuation, or resumption.
- No FLAC/Opus/AAC bakeoff and no claim that MP3 is the permanent archival
  format.
- No migration, compaction, or deletion of existing v1/v2 session audio.
- No model, decoder, reconciliation, latency-policy, pedal-quality, or
  score-quality change.
- No remote telemetry or diagnostic upload.
- No public distribution or operation of MIDI2ScoreTransformer.
- No Phase 5 implementation.

## Automated Acceptance

### Application boundary

- Application-service tests exercise catalog, historical reads, capture,
  Stop, score jobs, artifacts, deletion, storage accounting, and errors
  without starting an HTTP server.
- Dependency tests reject imports from the application package into HTTP,
  browser, FastAPI, Tauri, or concrete local adapter modules.
- Replay CLI and local HTTP adapters exercise the same application service
  instances and versioned products.
- Explicit target, concurrency, cancellation, stale-result, and restart tests
  pass.

### Behavioral parity

- The golden replay matches Phase 1 normalized events, horizons, MIDI, and
  accepted score behavior within existing tolerances.
- The React fixture and local runtime suites pass without a breaking runtime
  or contract change.
- Microphone, Stop/settling, historical selection, playback, score failure,
  artifacts, and recoverable deletion retain their Phase 3 behavior.
- V1 and v2 regression lanes remain green and their existing sessions remain
  readable.

### Storage behavior

- A deterministic ordinary one-hour replay leaves one complete playable
  128 kbps MP3, normalized session data, and compact status; it leaves no WAV
  source segments, detailed native arrays, repeated intermediate audio, or
  verbose window traces after successful finalization.
- Final retained MP3 audio is approximately 57.6 MB/hour, with actual total
  and per-category bytes reported rather than inferred from nominal bitrate.
- A multi-hour accelerated replay demonstrates bounded scheduler state,
  encoder backlog, RSS, and open file count. Raw transcription-source growth
  is explained by and reconciles with the measured correction backlog; it is
  retired after successful settlement.
- Playback and seeking cover the entire compacted session and remain aligned
  with source-sample inspection across every internal boundary.
- Encoder-unavailable, encoder-failure, restart-mid-compaction, partial-file,
  and low-disk tests retain usable audio and report an explicit state.
- Debug mode honors byte and age caps; the following ordinary session retains
  no debug-only artifacts.
- Several sequential sessions leave no unexplained bytes outside the reported
  recording, event/index, derived, debug, temporary, and trash categories.

## Manual Validation And R4 Review Gate

R4 receives one compact review build and:

- one deterministic replay command and one microphone action;
- New, history, selected-versus-active identity, Stop/settling, timeline,
  keyboard, score, artifact, and recoverable-delete parity checks;
- one newly compacted session played and scrubbed at its beginning, an
  internal boundary, and near its end;
- one old segmented-WAV session opened without migration;
- a before/after disk report that distinguishes raw, compact, derived, debug,
  temporary, and trash bytes;
- an explicit explanation that accepted compact mode removes new sessions'
  WAV source after verified MP3 publication;
- one encoder-failure recovery demonstration;
- the application/adapter/React code map;
- the exact automated test report and commit range; and
- known differences and intentionally deferred work.

The user decides both whether basic application behavior survived extraction
and whether MP3-only ordinary retention is an acceptable local default.
Phase 4 is not accepted and Phase 5 does not begin until both decisions are
explicit.

## Rollback Or Disable Path

The extracted services remain behind the existing local runtime adapter, so
the independently runnable v1 and v2 commands remain fallbacks.

Compact retention is enabled only for newly created Phase 4 sessions during
implementation. Disabling it before R4 returns new sessions to the retained
WAV-plus-MP3 behavior. A session whose WAV was already retired still has its
verified MP3 and declared source mapping; Phase 4 never claims that deleted
lossless source can be reconstructed.

No existing session tree is rewritten. Reverting the application extraction
does not require a data migration.

## Planned Implementation Sequence

1. Land Tactical 022's durable ingest, worker isolation, and asynchronous Stop
   contract, then Tactical 023's measured degradation policy.
2. Freeze the remaining Phase 4 service-level parity fixtures and add the application
   package/dependency checks.
3. Extract catalog, historical reads, artifact access, and recoverable
   deletion.
4. Extract the proven capture, settling, and score-job coordination.
5. Add artifact classification, compact status, storage accounting, and debug
   policy.
6. Move recording finalization behind the application boundary and implement
   bounded raw-spool compaction for new sessions.
7. Thin the HTTP/replay adapters and run the React/local integration lanes.
8. Run longevity, recovery, low-disk, and migration regression evidence.
9. Prepare R4 and stop for explicit parity and retention approval.

## Execution Record

No implementation commits yet.
