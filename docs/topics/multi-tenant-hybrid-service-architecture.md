# Multi-Tenant Hybrid Service Architecture

Topic: multi-tenant-hybrid-service-architecture

Status: **deferred future architecture as of 2026-07-28.** Phases 1 through 5
are complete and R2 through R5 are accepted. The user does not currently plan
to build the managed PostgreSQL, object-storage, identity, tenancy, or sync
system. The near-term deployment is the working Mac-hosted local application
shared on demand through the home Pi/Caddy; that current direction is owned by
[`home-hosted-family-sharing.md`](home-hosted-family-sharing.md).
Phase 4 is recorded under
[`017-python-application-core.md`](../tactical/017-python-application-core.md)
and Phase 3 under
[`016-shared-react-application.md`](../tactical/016-shared-react-application.md)
with its live-feedback, horizon presentation, score publication sanity, and
session-addressed review URLs corrected through R3 feedback. Stop progress and
automatic post-settle scoring are also implemented. React now preserves
distinct inferred sustain and soft-pedal lanes and flags unusually long
controller estimates instead of merging them as apparent stuck sustain,
and it provides seekable recorded-audio playback synchronized to exact
source-sample inspection.

Phase 5 is implemented through its bounded review slice under
[`030-early-tauri-sidecar-boundary.md`](../tactical/030-early-tauri-sidecar-boundary.md).
The unsigned, self-contained macOS arm64 Tauri development application now
contains a standalone Python runtime, CPU-only model pack, relocated media
tools, authenticated loopback IPC, thin Rust supervision, the shared React
workspace, real golden replay, and reconciled installed/compressed bundle
inventories. Its archive launches outside the repository with Python
development state cleared, preserves history, fails visibly on sidecar exit,
and passes direct-versus-packaged reference-relative parity. The exact R5
review packet is
[`r5-desktop-boundary-review.md`](../r5-desktop-boundary-review.md).
The user accepted R5 on 2026-07-28 after validating the revised artifact
export flow. Tactical 031 owns a
separate opt-in internal build of the unresolved score runtime after the user
provisionally accepted the checkpoint as following the paper's CC BY 4.0
terms for internal testing. That build has passed packaged replay-to-score and
post-launch immutability audits, and the user confirmed that its engraving
renders successfully. Tactical 032 responds to the same review by moving the
original model MusicXML into the shared Exports panel and adding one bounded
native Save As path. Large desktop artifacts stream from the authenticated
sidecar without crossing IPC as bytes, while the web adapter retains normal
browser downloads. The webview still has no general filesystem, dialog,
shell, or remote HTTP permission. The ordinary R5 and every public artifact
remain score-free. Windows, Linux, final signing, updates, and microphone
parity remain outside this bounded proof.

The local Python path now composes framework-independent application services
for sessions, capture, score jobs, storage, artifacts, and recoverable
deletion over explicit local adapters. Replay and microphone use the same
sample-indexed capture service. New Phase 4 sessions ordinarily retain a
verified 128 kbps MP3 and retire WAV source after every enabled lane settles;
`--retain-wav` explicitly keeps lossless source when needed. Ordinary
diagnostics are off, bounded debug retention is separate, and
one-hour/three-hour category evidence is reproducible. This is local
modularity evidence, not evidence of hosted accounts, authorization,
PostgreSQL, object storage, cloud durability, or multi-tenant isolation.

The Pi's existing public Caddy service proxies the real Mac-hosted React and
Python/model application over the LAN for on-demand family sharing. Its Mac
upstream runs as a restart-supervised launchd job with retained lifecycle and
process logs; it deliberately does not register as a reboot or login service.
Versioned Pydantic contracts, generated OpenAPI/TypeScript, the
`AtpianoRuntime` boundary, an executable fixture provider, and explicit local
compatibility paths exist. R2 feedback removed the generic `product`
namespace and premature application ports while retaining the cross-client
provider seam needed by web, future Android, and desktop clients. The shared
React application runs against the retained local engine. A zero-install
managed hosted service and auto-updating offline-capable Tauri distribution
remain future options, not the active product plan.

## Scope And Relationship

This topic retains the durable system shape designed for a possible future
managed hybrid product:

- the shared frontend and its hosted and desktop runtime adapters;
- account, workspace, membership, session, job, and artifact boundaries;
- hosted API, real-time ingest, model-worker, database, and object-storage
  responsibilities;
- local desktop sidecar, metadata, artifact, model-pack, and update
  boundaries;
- multiple-user and multiple-capture concurrency;
- offline operation and the deliberately narrow first synchronization model;
- API and worker contract versioning;
- service and desktop observability;
- privacy, authorization, distribution, and dependency-license gates; and
- the staged path from the current v2 application to the target shape.

[`session-workspace-management.md`](session-workspace-management.md) owns the
first local refactor: explicit New, history, selected-versus-active session
identity, and recoverable deletion. It should establish useful domain
boundaries without prematurely implementing accounts, cloud persistence, or
sync.
[`long-session-storage-retention.md`](long-session-storage-retention.md) owns
ordinary local disk growth and bounded debug data. Its first implementation
is part of the Phase 4 application-service extraction so storage policy,
artifact finalization, accounting, and deletion share one owner.

[`live-acoustic-transcription.md`](live-acoustic-transcription.md) continues
to own sample-clocked capture, provisional and committed event lifecycles,
model-lane scheduling, horizon semantics, reconciliation, and latency
measurement. This topic owns where those responsibilities execute and how
their results cross process or network boundaries.

[`performance-to-notation.md`](performance-to-notation.md) owns score
semantics and readability. This topic treats score generation as a
session-addressed job and score output as a versioned artifact.
[`desktop-score-runtime-footprint.md`](desktop-score-runtime-footprint.md)
owns the measured score-runtime size, inference-minimal dependency direction,
and parity gates for reducing that internal bundle without weakening the
process or release boundaries.
[`browser-only-wasm-deployment.md`](browser-only-wasm-deployment.md) remains
an optional client-side executor investigation, not the product architecture
or a constraint on model quality.

This is a deferred target architecture, not evidence that hosted accounts,
collaboration, sync, or multi-tenant behavior works and not an instruction to
implement them.

## Deferred Decision Summary

If the managed hybrid product is revived, the proposed shape has three
workspace modes:

1. **Local-only workspace:** no account is required; capture, inference,
   metadata, recordings, and generated artifacts stay on the device.
2. **Cloud workspace:** the service is authoritative and supports accounts,
   shared membership, browser or desktop access, concurrent sessions, hosted
   inference, and durable cloud artifacts.
3. **Synced workspace:** a later mode in which the desktop retains a useful
   local copy and explicitly transfers mostly immutable sessions and
   artifacts to or from a cloud workspace.

In that deferred design, the hosted web application provides the
lowest-friction trial and
collaboration path. The desktop application provides local/offline use,
stronger privacy, direct access to local accelerators, and resilience to
network quality. Neither is a compatibility shell around an unrelated
product: both use the same frontend, domain vocabulary, event schemas, and
artifact formats.

The provisional future technology choices are:

| Concern | Proposed choice if resumed |
| --- | --- |
| Shared application | React, TypeScript, and Vite |
| Remote/server state | TanStack Query |
| Small client-owned state | Zustand plus an explicit capture state machine |
| Hosted API | Python FastAPI modular monolith |
| Model execution | Separate Python worker processes or images |
| Cloud metadata | PostgreSQL |
| Recordings and large artifacts | S3-compatible object storage |
| Ephemeral routing | Redis only when measured needs justify leases or pub/sub |
| Desktop shell | Tauri 2 with a thin Rust security and process layer |
| Desktop inference | Versioned Python sidecar and separate model packs |
| Desktop metadata | SQLite plus a local artifact directory |
| Public API contracts | Pydantic/OpenAPI and a generated TypeScript client |
| Internal worker contracts | Versioned binary messages; protobuf/gRPC when justified |
| Observability | OpenTelemetry, structured logs, metrics, and audit events |

The exact React router, OIDC provider, cloud vendor, object-store vendor, job
queue implementation, and first internal worker transport remain bounded
implementation choices only if the hosted architecture is reopened.

## Architectural Overview

```text
                         React + TypeScript SPA
                              /          \
                             /            \
                    hosted web          Tauri desktop
                         |                    |
                 HTTPS / WebSocket     local runtime adapter
                         |                    |
                cloud API + workers    Python inference sidecar
                         |                    |
             PostgreSQL + object store SQLite + local artifacts
                             \              /
                              optional sync
```

The shared frontend depends on an `AtpianoRuntime` boundary rather than on
browser globals, Tauri commands, or cloud endpoints throughout components.
The hosted adapter implements it with HTTPS and WebSockets. The desktop
adapter implements it through the constrained Tauri shell and local sidecar.

If resumed, the cloud deployment begins as a **modular monolith**: one
versioned application and repository with explicit internal modules and
independently runnable process roles. It is not one operating-system process
and it is not a pre-emptive fleet of microservices. API, real-time
coordination, and model workers can scale separately without inventing
unrelated service contracts.

## Non-Negotiable Invariants

Later tacticals may change implementation details but must preserve these
properties or explicitly revise this topic first:

1. The v1 MVP and current v2 workbench remain runnable and their existing
   artifacts remain readable during migration.
2. Musical event time comes from the source audio sample clock, never packet
   arrival, worker completion, database time, or browser paint time.
3. Every persisted domain object is addressed explicitly. No server-global
   “current workspace” or “current session” selects the target of a read,
   mutation, score job, or artifact publication.
4. A shared cloud workspace can contain multiple simultaneous capture
   sessions. Exclusivity is one active writer lease per session, not one
   active session per workspace.
5. Browser selection is client-local. Viewing one session cannot redirect a
   capture writer, a score job, or another user's view.
6. Every cloud-owned domain row is tenant-addressable through `workspace_id`;
   service-layer authorization is mandatory on every access.
7. Audio, event history, scores, models, and evidence retain immutable,
   checksummed artifacts and enough provenance to identify the generating
   code, schema, adapter, checkpoint, and settings.
8. Large models do not load in stateless API processes.
9. Raw PCM does not pass through PostgreSQL or a general job queue.
10. Hosted and desktop implementations consume versioned contracts rather
    than importing each other's internal persistence or process assumptions.
11. Local-only desktop use works offline and does not require an account.
12. Initial sync transfers immutable session products and reconciles a small
    set of mutable metadata; it is not a general bidirectional database sync.
13. Browser-only WASM remains an optional execution adapter and cannot
    constrain the selection of a higher-quality model.
14. An unresolved third-party license blocks public hosted operation,
    bundling, or model distribution of that dependency even when internal
    research use was accepted.
15. Logs, traces, metrics, crash reports, and audit events must not contain
    raw audio, tokens, private filesystem paths, or unbounded musical payloads.

## Shared Frontend

### Why React now

The v2 proof-of-concept frontend already coordinates capture, replay,
session state, polling, timeline rendering, keyboard state, score jobs,
downloads, and errors in a large framework-free application. Accounts,
workspace switching, history, multiple viewers, offline state, and background
jobs would make implicit mutation and request ownership harder to reason
about.

React is now justified as the shared composition and lifecycle layer.
TypeScript makes the generated wire contracts and platform boundary
checkable. Vite produces a static application suitable for both ordinary
hosting and Tauri; the first product does not need server-side rendering or a
full-stack React framework. A separate public marketing site can be chosen
later without changing this application.

The migration is behavior-preserving. It does not authorize a visual redesign
or a rewrite of the transcription engine.

### State ownership

TanStack Query owns server-persisted or runtime-provided state:

- current user and authentication session;
- workspace catalog and memberships;
- session summaries and session detail;
- event ranges and horizons;
- jobs, score snapshots, and artifact manifests; and
- invalidation after capture, upload, deletion, or job completion.

Zustand owns only small client-local or device-local state:

- selected visualization modes;
- capture device and permission state;
- New-session intent;
- offline and sync indicators;
- local view preferences; and
- the capture state machine.

Do not copy a remote workspace or session catalog into a second general
Zustand cache. Derived state belongs in selectors or query results, and
durable state belongs behind the runtime provider.

Capture uses an explicit discriminated state, initially:

```text
idle
requesting
warming
recording
stopping
failed
```

Transitions identify their session and capture IDs and reject late responses
from an earlier transition. “New” is an unpersisted UI intent until capture or
replay actually creates a session.

### Runtime provider

The exact TypeScript interface will be generated and refined in its tactical,
but the responsibility boundary resembles:

```ts
interface AtpianoRuntime {
  listWorkspaces(): Promise<Workspace[]>
  listSessions(workspaceId: string): Promise<SessionSummary[]>
  startCapture(input: CaptureStart): Promise<CaptureHandle>
  streamPcm(block: PcmBlock): void
  stopCapture(captureId: string): Promise<Session>
  generateScore(sessionId: string): Promise<Job>
}
```

This is a behavioral sketch, not the frozen API. Reads, capture, subscriptions,
artifacts, cancellation, and errors will use explicit versioned types. UI
components must not infer whether a result came from cloud PostgreSQL, local
SQLite, a cloud worker, or a desktop sidecar.

## Deferred Hosted Service Shape

The remainder of this section is retained design guidance, not active
implementation scope.

### Why the control plane stays in Python

The initial hosted backend is FastAPI rather than a TypeScript control plane
plus Python inference services. Sharing a language with the browser does not
eliminate wire schemas, authorization boundaries, or generated clients. A
second backend language would immediately add another deployment,
observability, error-mapping, and service-call boundary while all existing
model, decoder, reconciliation, score, and artifact logic is Python.

Pydantic models and OpenAPI provide the stable public boundary and generate
the TypeScript client. Python internals remain ordinary typed modules behind
repositories and services. A separately scaled TypeScript control plane can
be considered later only if measured organizational or performance needs
outweigh the extra boundary.

### Process roles

The modular monolith defines these logical process roles from the beginning:

- **HTTP API:** authentication integration, authorization, workspace and
  session metadata, signed artifact access, query endpoints, and job control;
- **real-time ingest coordinator:** capture leases, binary PCM WebSockets,
  continuity and backpressure, audio segmentation, worker routing, horizons,
  and revision delivery;
- **warmed preview workers:** low-latency rolling inference for provisional
  feedback;
- **commit workers:** trailing, stronger-model correction and final flushing;
- **score workers:** bounded notation generation from committed session
  products;
- **background worker:** cleanup, retention, upload finalization,
  notifications, and later sync-related work.

One codebase and deployment release may run several of these roles. Model
workers are separate operating-system processes or container images so model
memory, native dependencies, accelerators, crashes, and autoscaling are
isolated from the API. Roles become independent services only where load,
availability, hardware, or release evidence justifies it.

### Hosted streaming path

```text
AudioWorklet
     |
     | sample-indexed binary PCM
     v
authenticated capture WebSocket
     |
     v
real-time ingest coordinator
     +----> checksummed immutable audio segments ----> object storage
     |
     +----> bounded PCM windows ----> warmed preview worker
     |
     +----> trailing commit scheduling ----> commit worker
     |
     +<---- event revisions, horizons, and timing evidence
     |
     +----> subscribed browser and desktop viewers
```

The browser supplies monotonically sample-indexed blocks. The coordinator
validates format and continuity, maintains bounded queues, records gaps and
backpressure, and acknowledges a source horizon. It does not reinterpret
network arrival as musical time.

WebSockets are appropriate for the current full-duplex capture and revision
path. Ordinary catalog, history, job, and artifact operations remain HTTPS.
A long-lived connection receives a short-lived capture credential scoped to a
workspace, session, capture lease, format, and expiry; the ordinary browser
authentication credential is not embedded in captured artifacts or logs.

At larger scale, connection routing can use a session owner lease and sticky
reconnection. Redis is permitted for ephemeral lease, presence, and pub/sub
coordination only when more than one coordinator requires it. PostgreSQL and
object storage remain authoritative; Redis is not the durable session ledger.

### Latency accounting

Every hosted and local run must preserve separate measurements for:

- source capture to transport availability;
- transport and ingest;
- preprocessing;
- scheduler wait or queue time;
- algorithmic context and look-ahead;
- model inference;
- decoding and reconciliation;
- persistence;
- delivery to the subscribed client; and
- client receipt to paint.

Throughput or isolated inference time is not a real-time claim. The same
stage vocabulary and source-onset identifiers must work in cloud and desktop
diagnostics.

## Deferred Accounts, Workspaces, And Concurrency

### Identity and authorization

Use a managed OpenID Connect provider. Do not build password storage,
recovery, MFA, or session-token issuance in the first service. The backend
maps the provider's stable subject to an internal user and applies its own
workspace authorization.

The initial roles are:

- **owner:** membership, invitations, workspace settings, retention, and all
  editor actions;
- **editor:** create sessions, upload recordings, run jobs, and edit permitted
  workspace metadata; and
- **viewer:** read sessions and artifacts without capture or mutation.

Authorization is checked in the service layer before repository or
object-store access. PostgreSQL row-level security should be enabled as
defense in depth for tenant-owned rows, with default-deny policies and
explicit workspace context. It does not replace service-layer authorization,
object-key authorization, or multi-tenant tests.

### Core data model

The target model starts with:

```text
user
workspace
workspace_membership
workspace_invitation
session
capture_lease
transcription_run
score_snapshot
artifact
job
audit_event
```

Every tenant-owned row carries `workspace_id`, including records that can also
be reached through `session_id`. IDs are globally unique and may be
client-generated where offline creation needs stable identity before upload.
The exact UUID format is deferred.

Important relationships are:

- a user belongs to a workspace through a membership and role;
- a workspace owns many sessions, including concurrent active sessions;
- a session has at most one live writer lease at a time;
- a session owns one or more versioned transcription runs;
- a transcription run owns events, horizons, provenance, and exports;
- a session or transcription run owns score snapshots and other artifacts;
- jobs always name their target workspace, session, input horizon, and output
  kind; and
- material membership, deletion, retention, and artifact-access actions
  produce audit events.

“Active session” is therefore a session lifecycle status, not a singleton
column on the workspace. Several friends can record into separate sessions in
one shared workspace at the same time. Many clients can subscribe to one
session, but only the valid writer lease can append source audio to it.

### Session and job immutability

Recordings, source events, committed exports, model evidence, and published
score snapshots are immutable artifacts. A new inference, reconciliation, or
score attempt creates a new version with a captured input horizon and
provenance rather than overwriting prior evidence.

Small user metadata such as a title, description, tags, or archival state is
mutable and versioned separately. This distinction makes offline upload and
conflict handling tractable and keeps research evidence reproducible.

Delete first becomes a tombstone plus retention policy in cloud storage and a
recoverable trash move locally. Permanent purge is a distinct authorized
operation that must account for object versions, derived artifacts, audit
requirements, and active jobs.

## Persistence Boundaries

### PostgreSQL

PostgreSQL stores queryable, transactional metadata:

- users, workspaces, memberships, invitations, and roles;
- session lifecycle and capture-lease state;
- transcription runs, source and commit horizons, and compact event indexes;
- job state and publication transactions;
- artifact manifests, hashes, sizes, media types, and storage keys;
- mutable labels and sync cursors; and
- audit events.

It must not store an unbounded raw PCM stream or large model tensors.
Queryable note events may live in PostgreSQL where that proves useful, but
the canonical export and revision evidence remain checksummed versioned
artifacts.

### Object storage

S3-compatible object storage contains:

- lossless captured audio and finalized audio segments;
- MIDI, JSONL, MusicXML, evidence bundles, and previews;
- model-native diagnostic arrays when explicitly retained;
- score-rendering products; and
- server-side model manifests or checkpoints in a separately protected
  distribution boundary.

Object keys are opaque implementation details, not authorization tokens.
Clients receive short-lived, content-scoped access only after an authorized
metadata lookup. Multipart or segmented uploads are finalized by hash and
manifest; a database row must not claim a complete artifact before its object
is durably present.

### SQLite and local artifacts

Desktop metadata uses SQLite as a rebuildable, transactional catalog over a
local artifact root. Sessions and immutable artifacts keep manifests and
hashes sufficient for repair or re-indexing. SQLite holds local query state,
relationships, jobs, sync status, and mutable annotations; it is not the only
place that says which recording bytes exist.

Local paths never cross the cloud API. A sync upload produces cloud object
identities and retains an explicit mapping to the local artifact hash.

## Worker And Schema Contracts

The public contract is versioned Pydantic schemas exposed through OpenAPI.
The repository generates and checks a TypeScript client rather than
hand-maintaining parallel interfaces. Breaking changes require a new API or
schema version and a compatibility window for released desktop clients.

The high-volume PCM client path uses a small versioned binary envelope with
declared:

- protocol version;
- workspace, session, capture, and stream identities;
- source sample rate, channel count, sample format, and start sample;
- block sequence and frame count; and
- acknowledgements, gaps, backpressure, and terminal status.

Internal coordinator-to-worker messages are also versioned and must be
serializable. An initial local binary protocol or process queue is acceptable.
Protobuf/gRPC is the expected evolution when remote workers, polyglot tools,
schema compatibility, or streaming observability justify it. Python object
pickles, shared mutable globals, and database polling are not durable worker
contracts.

Model adapters remain accelerator-neutral. CPU, Apple, CUDA, and AMD workers
consume the same input contract and emit the same model-native and normalized
output contracts. A backend is promoted only after replay parity against a
known-good result; a zero-exit empty result is a failure.

Every generated artifact records:

- input artifact hashes and source horizon;
- schema and serialization versions;
- application and worker build versions;
- model adapter, checkpoint hash, and execution backend;
- decoder, reconciliation, and score settings; and
- creation time and producing job identity.

## Tauri Desktop Runtime

### Packaging boundary

Tauri 2 packages the same Vite-built frontend. Rust remains a thin privileged
layer responsible for:

- capability-scoped filesystem and process access;
- starting, authenticating, monitoring, and stopping the local sidecar;
- update verification;
- secure local paths and application lifecycle integration; and
- a narrow command or event bridge where browser APIs are insufficient.

The Tauri webview must load bundled, reviewed frontend assets. It must never
load the hosted application or other remote content into a webview that has
privileged Tauri capabilities.

The Python sidecar owns inference, decoder and reconciliation logic, local
session services, score jobs, and their native dependencies. The first
implementation may reuse the existing binary loopback WebSocket protocol on
an ephemeral port protected by a per-launch secret. A Tauri event bridge,
local socket, or framed standard-stream protocol may replace it after
measurement. No local server port is assumed to be trustworthy merely
because it binds to loopback.

### Version and compatibility handshake

Before capture, the shell and sidecar exchange:

- desktop application and frontend build;
- local schema version and migrations;
- sidecar protocol and build version;
- installed model-pack IDs, hashes, and adapter requirements;
- detected device and accelerator backend; and
- compatibility result with a human-readable recovery action.

The sidecar cannot silently substitute an unrecorded model or corrupt a newer
catalog. Failed migrations and incompatible model packs leave prior data
readable and surface a bounded repair or rollback path.

### Updates and model packs

Desktop distribution has two signed update layers:

1. the Tauri application, Rust shell, frontend, and compatible sidecar; and
2. separately versioned, signed, and checksummed model packs.

Model packs are large, hardware-sensitive, and independently licensed. They
should not force a complete application update, and an application update
should not silently download every model. Manifests declare supported app,
sidecar, adapter, platform, architecture, and device ranges.

Start with macOS arm64 because it is the current measured environment. Add
Windows next through a separately validated packaging lane. Tauri's
cross-platform UI does not make Python wheels, model runtimes, accelerators,
codesigning, or installers automatically portable.

### Offline promise

A local-only workspace requires no login and remains usable with the network
disabled after installation and model acquisition. Capture, transcription,
history, score generation, review, and export use local services and
artifacts. Update, login, invitation, upload, and cloud browsing may report
offline status but cannot disable local work.

Desktop diagnostic telemetry is opt-in and privacy-aware. Users can always
produce an inspectable local diagnostic bundle without uploading audio.

## Deferred Cloud, Local, And Sync Semantics

Cloud and local workspaces are explicit modes. The client must not make a
local folder silently collaborative or upload audio merely because a user
signs in.

The first hybrid transfer is intentionally one-directional and
session-oriented:

1. capture and finish a session locally;
2. retain the complete local recording and artifacts;
3. explicitly choose a destination cloud workspace;
4. create or resume an idempotent upload using artifact hashes;
5. publish the immutable cloud session only after required objects verify;
6. transfer separately mutable labels with an explicit last-write or conflict
   rule; and
7. retain local-to-cloud identity and provenance.

Downloading a cloud session for offline review can use the inverse artifact
transfer later. Editing the same mutable record on two disconnected devices,
merging live event histories, and continuing one capture on another device
are not first-sync requirements.

Raw audio transfer is explicit and privacy-labelled. A product may later
offer workspace-level defaults, but membership alone is not consent to upload
an existing local recording.

Hash-addressed immutable artifacts, client-stable IDs, idempotency keys, and
tombstones make retry and partial failure recoverable without pretending the
two databases are a single replicated database.

## Security, Privacy, And License Gates

The hosted service must establish:

- managed OIDC login and secure browser session handling;
- short-lived, scoped capture and object credentials;
- service-layer authorization and default-deny tenant tests;
- PostgreSQL row-level security as defense in depth;
- protected object namespaces and authorization before signed access;
- workspace and user quotas, bounded queues, upload limits, and backpressure;
- encryption in transit and provider-appropriate encryption at rest;
- auditable membership, role, retention, deletion, and artifact actions;
- explicit retention and purge behavior; and
- dependency, model, dataset, and asset manifests with versions, licenses,
  sources, and hashes.

The desktop application additionally requires:

- least-privilege Tauri capabilities;
- no privileged remote web content;
- signed application updates and platform distribution;
- signed and checksummed sidecars and model packs;
- per-launch authentication of local IPC;
- validated filesystem roots and artifact paths; and
- secrets in operating-system credential storage rather than SQLite or logs.

MIDI2ScoreTransformer currently has no confirmed published license for its
GitHub source or v0.0.1 checkpoint. The paper's Zenodo and arXiv records are
CC BY 4.0, and on 2026-07-27 the user provisionally accepted the checkpoint as
following those terms for a private internal desktop test. Tactical 031 may
therefore stage an explicitly internal-only build, but neither the checkpoint
nor implementation may enter a public archive, model pack, hosted offering,
or release until their own rights are confirmed. A licensed replacement or
reimplementation may satisfy the same score-worker contract.

Tactical 031 has now proven that boundary in a separate macOS arm64
application. The internal build validates pinned source and checkpoint
hashes, advertises score capability only when its isolated runtime is valid,
and completed a real packaged replay-to-score run without mutating the
application tree. The normal staging and archive paths remain score-free and
reject those assets. This is implementation evidence for the local process
boundary, not resolution of the release gate. R5 was accepted independently
after the later export revision.

## Observability And Operations

Instrument the boundaries from the first hosted and desktop slices with
OpenTelemetry-compatible traces, metrics, and structured events. The
correlation vocabulary includes:

```text
request_id
user_id
workspace_id
session_id
capture_id
stream_id
transcription_run_id
job_id
model_revision
artifact_hash
```

Use opaque or hashed user identifiers where operationally sufficient.
Structured JSON logs record bounded identifiers, state transitions, reason
codes, versions, durations, and counts. They do not record raw PCM, auth
headers, signed URLs, private local filenames, full event streams, or model
tensors.

Required metrics include:

- active and rejected capture leases;
- connection, reconnect, gap, duplicate, and dropped-frame counts;
- per-stage latency and algorithmic look-ahead;
- queue depth, scheduling delay, worker utilization, and accelerator type;
- preview, commit, score, upload, and cleanup job outcomes;
- event revision, retraction, and horizon lag summaries;
- object write/finalization and database transaction failures;
- client and server schema/version incompatibilities; and
- desktop sidecar startup, crash, model-load, and local storage failures.

Audit events are a user-visible security record, not debug logs. Traces and
metrics diagnose execution. Model evidence and artifact manifests reproduce
musical results. Do not collapse the three into one unbounded event table.

Desktop telemetry defaults and hosted data retention require explicit product
policy before public release. Local exportable diagnostics remain available
even when remote telemetry is disabled.

## Failure And Recovery Contracts

Implementation tacticals must make these failures explicit:

- capture connection loss preserves the last acknowledged source sample and
  either resumes under the same valid lease or records a declared gap;
- duplicate or reordered PCM blocks are rejected or idempotently recognized;
- worker loss cannot publish a partial result as a committed artifact;
- a capture lease expires and can be recovered without making two writers
  valid;
- upload retry does not duplicate a session or silently replace a different
  artifact;
- database publication cannot reference an absent or hash-mismatched object;
- sidecar death preserves completed local artifacts and leaves an inspectable
  failed run;
- an application or model update cannot mix incompatible cached versions;
- offline actions remain queued or explicitly local rather than appearing
  synced; and
- authorization loss immediately blocks new reads, signed access, capture,
  and mutation without deleting the user's valid local data.

All queueing is bounded. Backpressure and degraded modes are visible rather
than converted into ever-growing memory, stale live feedback, or falsely
successful jobs.

## Deferred Scalability And Deployment Evolution

If revived, the first hosted vertical slice can run one API deployment, one
real-time coordinator deployment, a small worker pool, managed PostgreSQL,
and managed object storage. That is already horizontally extensible at the
expensive boundaries without requiring microservices for catalog, membership,
score, and artifact metadata.

Scale by measured pressure:

- API replicas for ordinary request volume;
- connection coordinators for simultaneous captures;
- warmed preview pools by model, accelerator, and latency target;
- commit and score workers by queue delay and hardware class;
- object transfer paths independently from inference;
- read replicas, partitions, or event-storage changes only from query
  evidence; and
- Redis routing or pub/sub only when coordination crosses replicas.

Preserve one logical transaction boundary for workspace authorization,
session publication, jobs, and artifact manifests until a real availability
or scaling requirement demands separation. An outbox can publish durable
work after database commit without making an ephemeral broker authoritative.

## Implementation Sequence

The master sequence and human review gates are tracked in
[`013-hybrid-product-migration-master.md`](../tactical/013-hybrid-product-migration-master.md).
Phases 1 through 5 landed through bounded, reversible child tacticals. The
remaining entries are retained only as deferred scopes:

1. **Freeze and characterize.** Turn v1, v2, the aligned fixture, retained
   recordings, microphone behavior, sessions, exports, and score snapshots
   into a reproducible migration baseline.
2. **Contracts and structure.** Establish versioned domain schemas, the
   runtime-provider boundary, generated-client workflow, explicit local
   session services, and repository dependency directions.
3. **Shared React application.** Migrate useful v2 behavior to React,
   TypeScript, and Vite over fixture and compatibility/local runtime adapters.
   Review the product interaction before further backend extraction.
4. **Python application core.** Extract framework-independent session,
   capture, transcription, score-job, artifact, and provenance services while
   preserving deterministic and microphone behavior. Stop for explicit human
   parity review before Phase 5.
5. **Early Tauri walking skeleton.** Package the shared frontend, launch and
   authenticate a versioned Python sidecar, perform compatibility handshake,
   and run the golden replay. This early proof prevents later hosted
   assumptions from making the shared application browser-only.
6. **Deferred complete local desktop vertical slice.** Add durable SQLite/local
   artifacts, microphone and review parity, model packs, signed update
   infrastructure, diagnostics, and network-disabled validation.
7. **Deferred hosted service vertical slice.** Add managed identity, cloud workspaces,
   memberships, PostgreSQL, object storage, worker boundaries, secure PCM
   ingest, collaboration, authorization, and observability.
8. **Deferred collaboration, distribution, and limited sync.** Harden both products and
   add explicit idempotent immutable-session transfer before considering
   broader offline reconciliation.

Completion of Phase 5 does not queue Phase 6 or Phase 7. Focused local work
may proceed under its own topic without accepting the full scope of either
phase.

Phase 1 completed in
[`014-freeze-migration-baseline.md`](../tactical/014-freeze-migration-baseline.md).
The normalized fixture and route baseline, automated regression report, manual
lanes, known platform constraints, and deliberate non-parity are summarized
in [`migration-baseline.md`](../migration-baseline.md). R1 found no ambiguous
useful behavior requiring a product decision, so the next bounded slice may
establish contracts and structure.

Phase 2 implementation completed in
[`015-contracts-and-structure.md`](../tactical/015-contracts-and-structure.md).
Its actual tree, public vocabulary, dependency map, runtime interface,
examples, generation workflow, compatibility policy, and evidence are in
[`r2-structure-contracts-review.md`](../r2-structure-contracts-review.md).
Do not open Phase 3 until R2 is explicitly accepted or revised.

Each phase gets one or more numbered tacticals with entry conditions,
migrations, validation, rollback or compatibility behavior, and an execution
record. The structure, interaction, and pre-Tauri parity reviews are explicit
holds rather than status updates. Do not combine cloud accounts, frontend
migration, worker extraction, desktop packaging, and sync into one rewrite.

## Deferred Full-Architecture Validation Gates

If the managed hybrid architecture is resumed, it cannot be described as
implemented until evidence shows:

- deterministic WAV replay produces equivalent normalized session products
  through the direct, hosted-worker, and desktop-sidecar paths within declared
  tolerances;
- the aligned musical fixture and retained recordings exercise chords,
  Alberti bass, progression, melody, pedal, silence, noise, repeated notes,
  dense chords, bass, and treble;
- event times and horizons remain source-sample-derived across process and
  network boundaries;
- two users can create distinct simultaneous sessions in one workspace while
  two writers cannot append to one session;
- role and tenant tests prove default-deny behavior for rows and artifacts;
- late requests, view changes, reconnects, retries, and job completion cannot
  retarget a different session;
- object, database, and job failure injection cannot publish incomplete
  artifacts as complete;
- every result records model, adapter, schema, build, settings, source
  horizon, and artifact hashes;
- hosted latency reports every required stage under realistic concurrency;
- a local-only desktop installation completes capture, transcription, score
  where licensed, history, review, and export with the network disabled;
- desktop app, sidecar, schema, and model-pack compatibility failures are
  detected before capture and have a recovery path;
- explicit session upload is idempotent, resumable, and never silently uploads
  audio;
- logs, traces, diagnostics, and audit exports pass privacy inspection; and
- v1 plus current v2 replay, microphone, export, and notation regressions
  remain green.

## Deferred Decisions

These choices intentionally remain open until their implementation tactical:

- whether a managed hosted service should be pursued at all;
- React Router versus TanStack Router;
- managed OIDC vendor and exact browser-session integration;
- cloud, PostgreSQL, S3-compatible storage, and deployment vendors;
- exact job queue and durable outbox implementation;
- whether the first real-time coordinator is a separate deployment or a
  dedicated process role beside the API;
- when internal worker messages justify protobuf/gRPC;
- loopback WebSocket, local socket, or Tauri event bridge for the mature
  sidecar protocol;
- globally unique ID representation;
- detailed workspace retention, quota, billing, invitation, and public-share
  policies;
- cloud-to-local download and multi-device mutable-metadata conflict UX;
- desktop telemetry defaults and diagnostic consent;
- Windows and later Linux packaging details; and
- the licensed score converter used in public distribution.

If hosted work is reopened, selecting one deferred component does not reopen
the safety boundaries. For example, choosing an OIDC vendor does not
authorize building password authentication, and choosing a queue does not
authorize sending raw PCM through it.

## Official References

- [Tauri frontend configuration and static frameworks](https://v2.tauri.app/start/frontend/)
- [Tauri sidecars](https://v2.tauri.app/develop/sidecar/)
- [Tauri updater API](https://v2.tauri.app/reference/javascript/updater/)
- [Tauri capabilities](https://v2.tauri.app/security/capabilities/)
- [Tauri distribution](https://v2.tauri.app/distribute/)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [PostgreSQL row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [TanStack Query documentation](https://tanstack.com/query/latest/docs/framework/react/overview)
- [Zustand introduction](https://zustand.docs.pmnd.rs/getting-started/introduction)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [OpenTelemetry JavaScript](https://opentelemetry.io/docs/languages/js/)

## Recommended Direction

Use [`home-hosted-family-sharing.md`](home-hosted-family-sharing.md) as the
current deployment direction. Continue local quality, storage, operational,
and footprint work through focused tacticals. Do not open a PostgreSQL,
managed-identity, object-storage, tenancy, or sync tactical merely because it
appears next in the old sequence.

Reconsider this architecture only from a concrete need such as mutually
untrusted users, simultaneous capture writers, availability while the Mac is
offline, off-site durable storage, or measured single-host capacity limits.
If that happens, begin with a new bounded architecture review and revalidate
the old choices against the then-current application.

The useful boundaries remain: avoid putting model runtimes in a stateless API
process, adding a TypeScript control plane only for shared language,
attempting general bidirectional sync, or publicly distributing unresolved
dependencies.
