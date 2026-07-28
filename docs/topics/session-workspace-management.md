# Session Workspace Management

Topic: session-workspace-management

Status: accepted foundation on 2026-07-26; the player-facing workspace refresh
is complete and live under
[`036-musical-session-workspace-refresh.md`](../tactical/036-musical-session-workspace-refresh.md).
It provides application-owned human names, aggregate musical summaries, a
dedicated Sessions homepage, compact selected-session identity, contextual
feedback, and keyboard audition without changing session evidence or the
selected-versus-active boundary. The completed and live
[`037-detachable-score-playback.md`](../tactical/037-detachable-score-playback.md)
moves selected-session playback behind a persistent app-level controller so
workspace and score-reader controls share one lifecycle. Its focused Zustand
store publishes observable playback state while the provider privately owns
the media element and seek mechanics. Phase 3 and R3 are
complete under
[`016-shared-react-application.md`](../tactical/016-shared-react-application.md).
The Phase 4 extraction is implemented locally under
[`017-python-application-core.md`](../tactical/017-python-application-core.md)
and accepted at R4. Framework-independent services now own catalog and
historical reads, capture identity, score targets, artifact access, and
recoverable deletion while the local filesystem remains an adapter. Existing
session artifacts remain authoritative and no historical directory is
migrated while being read.

## Scope And Relationship

This topic owns the local v2 workspace experience around recorded sessions:

- session identity, lifecycle, summaries, and history;
- the distinction between the session being captured and the session being
  viewed;
- explicit New behavior;
- session-addressed events, scores, and artifacts;
- recoverable deletion; and
- the boundary that leaves future continuation or true resumption possible.

[`live-acoustic-transcription.md`](live-acoustic-transcription.md) continues to
own capture transport, sample clocks, lane scheduling, revisions, horizons,
and latency. [`performance-to-notation.md`](performance-to-notation.md)
continues to own score inference and rendering quality. This topic owns how
the workspace selects and addresses those session-bound products.
[`long-session-storage-retention.md`](long-session-storage-retention.md) owns
ordinary-session disk growth, bounded local debug retention, disk budgets, and
the still-open permanent recording-codec decision; session history and
deletion apply that policy without redefining it.

Phase 4 has moved catalog, capture coordination, historical reads, score jobs,
artifacts, retention, and deletion into one framework-independent application
boundary. Direct application tests exercise those services without HTTP.
The React runtime contract and accepted selected-versus-active behavior remain
stable; R4 confirmed that parity on 2026-07-27.

[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
retains the deferred hosted-plus-Tauri architecture, including accounts,
shared cloud workspaces, multiple concurrent capture sessions, local-only
desktop workspaces, and later explicit sync.
[`home-hosted-family-sharing.md`](home-hosted-family-sharing.md) owns the
current single-host deployment. Here, **workspace** means the single local v2
process and its configured artifact root. Its one-capture limit is a local
coordinator constraint; no current multi-user concurrency claim is made.

The v1 MVP and its workbench are outside this refactor. V2 may share utilities
with v1 only when v1 behavior and artifacts remain unchanged.

## Original Problem Record

V2 already writes each microphone or replay run to a unique session
directory. Old sessions survive and the server recovers the newest valid
session after restart. Starting microphone capture or replay claims a new ID,
creates a new directory, and changes one server-global current-session
pointer.

That persistence is useful, but the product model is implicit:

- the newest session is selected silently at server startup;
- **Start microphone** and replay implicitly replace the current selection;
- older directories have no list or selection API;
- events, scores, and artifacts resolve through whichever directory the
  server currently points at;
- the server conflates the session being written with the session being
  viewed;
- the browser has no explicit fresh state, history, or deletion action; and
- `CorrectedSession` requires an empty directory and begins at sample zero, so
  a completed session cannot currently resume.

This becomes unsafe as soon as history, multiple tabs, score jobs, or deletion
exist. A browser's view selection must never redirect capture or cause a job
to publish into a different session.

## Vocabulary And Invariants

Use these terms consistently:

- **workspace**: the configured directory containing session directories and
  recoverable trash;
- **session**: one durable microphone or replay run with one stable ID;
- **active session**: the one session, if any, currently accepting source
  audio or settling its tail;
- **selected session**: the session one browser tab is viewing;
- **new-session intent**: a client-side blank and ready state that has not
  created durable data;
- **historical session**: a complete or failed session opened read-only; and
- **trashed session**: a recoverably removed directory excluded from the
  ordinary catalog.

The first implementation must preserve these invariants:

1. One local v2 workbench process has at most one active capture session.
2. Selection is per browser client and is never server-global.
3. Every read, score action, artifact request, and delete action names an
   explicit session ID.
4. Starting capture creates a new durable session; selecting history never
   does.
5. Completed and failed session evidence is immutable except for separate
   workspace annotations and recoverable trash movement.
6. An active session or a session with a running score job cannot be deleted.
7. Session IDs and resolved paths are validated before every filesystem
   operation.
8. Existing session directories remain discoverable without migration.

## Accepted Product Behavior

### New and capture

**New session** is an explicit primary action. It clears the selected
visualizations and enters an unpersisted ready state. It does not create a
directory because the microphone's actual sample rate and capture metadata
are not known yet, and abandoned clicks should not create empty history.

From that state, **Start microphone** creates the concrete session, returns
its ID, selects it in the initiating tab, and begins capture. Deterministic
replay is an engineering fixture, not sound-file upload; its UI is retained
only when the explicit fixture runtime is selected. A future **Import
recording** workflow requires its own upload and provenance contract.

When another tab connected to the same local process already owns the one
active capture, New may still show a blank intent, but starting another
capture is disabled with the active session identified. The future hosted
service instead permits multiple active sessions in one shared workspace,
while preserving one writer lease per session.

The first UI does not switch away from an active recording in its owning tab.
The backend nevertheless keeps reading historical sessions independent from
capture so another tab, and a later richer UI, can browse history without
redirecting the writer.

### Viewing history

The page exposes a session list ordered newest first. An initial summary
contains:

- stable session ID;
- local start time;
- microphone or replay source;
- active, stopping, complete, or failed status;
- duration;
- optional automatic display text derived from time and source; and
- availability of committed exports and a score snapshot.

Selecting a historical session opens its timeline, keyboard, score, exports,
and status read-only. The page clearly labels **Viewing completed session**
instead of presenting old data as a live current session.

On narrow mobile screens, history remains available from a persistent
**Sessions** control in the workspace top bar. It opens the complete
newest-first history in an overlaid drawer, supports explicit close, backdrop
close, and Escape, and closes after New or historical-session navigation.
Collapsing the desktop rail must never remove session navigation.

The root URL now shows the newest-first Sessions library whether or not an
active capture exists. Selecting a performance writes its ID to the URL; a
deep link restores that selection, while returning through the atpiano brand
clears it and restores the library. Selection belongs to browser state, not
the server, so reload and multiple tabs remain independent.

The accepted 2026-07-28 refresh adds human naming as application-owned
annotations rather than rewriting transcription evidence. Automatic
date-and-source text remains the fallback for sessions without an annotation.

The same refresh promotes the bounded history into a dedicated Sessions
homepage. Its opening-phrase previews and playback hydrate lazily; listing
history must not eagerly load every session's artifacts or events.

Selected-session playback now has a separate global snapshot and persistent
media provider. Entering the exact-score reader preserves the media element,
sample-clock position, status, and source identity; both layouts expose
controls for that same transport. Session selection or source identity
changes reset it, while the Sessions homepage keeps its bounded lazy
row-local preview players outside this selected-session lifecycle.

### Delete

The UI may say **Delete session**, but the first backend operation is
recoverable. After confirmation it atomically moves the exact session
directory to:

```text
<workspace>/.trash/<session-id>-<deletion-time>/
```

The confirmation identifies the session by start time, source, duration, and
ID. Active sessions and sessions with running score jobs reject deletion.
After deleting the selected session, the client returns to the Sessions
library and confirms the recoverable move with a transient toast.

Restore and permanent purge are later actions. Keeping them separate prevents
a simple UI mistake from destroying recordings, event history, or scores.

## Backend Shape

Replace the server-global current-session abstraction with four explicit
services.

### Session catalog

The catalog lists and resolves valid session directories, reads bounded
summary metadata, and excludes trash. Session manifests remain authoritative.
The first implementation may scan and paginate the workspace; a later SQLite
catalog must be a rebuildable index rather than a second source of truth.

### Capture coordinator

The capture coordinator owns the one active write lease, its lifecycle, and
model instances. It creates new IDs for microphone and replay starts and
reports active state independently of what any browser is viewing.

### Historical session reader

The reader resolves one validated session ID and provides its manifest,
horizons, indexed event ranges, exports, and score artifacts. It never mutates
capture state.

### Score-job coordinator

Score generation names a target session and captured commit horizon. The
workspace may retain one CPU score job at a time initially, but its status and
publication remain keyed to that target ID. Selecting another session cannot
retarget or hide the job.

Phase 2 established the versioned ordinary HTTP shape:

```text
GET    /api/v1/workspaces
GET    /api/v1/workspaces/{workspace-id}/sessions
GET    /api/v1/workspaces/{workspace-id}/sessions/{session-id}
PATCH  /api/v1/workspaces/{workspace-id}/sessions/{session-id}
GET    /api/v1/workspaces/{workspace-id}/sessions/{session-id}/horizon
GET    /api/v1/workspaces/{workspace-id}/sessions/{session-id}/events
GET    /api/v1/workspaces/{workspace-id}/sessions/{session-id}/artifacts
POST   /api/v1/workspaces/{workspace-id}/sessions/{session-id}/score-jobs
DELETE /api/v1/workspaces/{workspace-id}/sessions/{session-id}
GET    /api/v1/jobs/{job-id}
```

List responses are bounded and cursor-paginated. Resource responses include
the resolved session ID so the client can reject a late response after its
selection changes. Mutating requests retain the loopback host, same-origin,
single-flight, and exact-path checks already used by v2.

Capture Start, sample-indexed PCM, Stop, and fixture replay are behavioral
operations on `AtpianoRuntime`, with `atpiano.pcm.v1` as the envelope. They
are not ordinary generated HTTP routes because hosted and local providers may
use different WebSocket, loopback, sidecar, or Tauri transports. The
deterministic fixture provider exercises those methods now; Phase 3 supplies
the current-local compatibility provider.

The existing unqualified `/api/session`, `/api/events`, `/api/score`, and
artifact routes may remain as short-lived compatibility aliases while the
frontend migrates. They must not remain the durable contract because their
target is ambiguous.

## Frontend Shape

The shared React application planned in
[`013-hybrid-product-migration-master.md`](../tactical/013-hybrid-product-migration-master.md)
owns the durable New/history/delete UI. Do not invest in a feature-complete
framework-free rewrite of the proof-of-concept frontend immediately before
that migration.

Replace the single overloaded `state.session` concept with explicit state:

```text
catalog
selectedSessionId
selectedSession
activeSessionId
mode: new | viewing | recording | stopping
capture
```

The top-level workspace controls become:

- **New session**;
- session history;
- the selected session's identity, source, start time, duration, and status;
- microphone and replay actions only in New or active-capture context; and
- a secondary confirmed Delete action for eligible history.

Timeline, keyboard, score, and export requests always use
`selectedSessionId`. Capture acknowledgements update `activeSessionId`; they
update the selected visualization only when the two IDs match.

Keep the current framework-free application runnable as a
compatibility/reference client. Backend session catalog and
explicit-addressing work may add only the smallest compatibility changes
required there. The React migration must preserve focused responsibilities
for:

- runtime/API client behavior and response cancellation;
- session state and selection control;
- microphone capture;
- timeline and keyboard views;
- score view; and
- a small composition root.

This is a responsibility split and migration, not an unrelated visual
redesign.

## Continuation And Resumption Boundary

Do not expose Resume in the first implementation. True append-in-place
resumption must define:

- continued source-sample coordinates;
- sample-rate compatibility;
- the declared gap between captures;
- reconstruction of lane model and open-note state;
- event identity and revision continuity; and
- commit-horizon behavior after a cold start.

Completed sessions therefore remain immutable. A safer future feature is
**Continue as new session**, with a `continuation_of` or `parent_session_id`
relationship. That preserves provenance and permits comparison without
pretending two separately initialized captures are one continuous model run.
A later explicit resume contract can build on the same catalog and active
write-lease boundaries if the value justifies the complexity.

## Bounded Refactor Plan

Implement this through the master migration's small behavior-preserving
slices rather than rewriting the workbench at once:

1. Add characterization tests for current session creation, restart recovery,
   event reads, score publication, exports, and v1 separation.
2. Introduce a read-only session catalog and explicit session-addressed read
   routes while retaining current aliases.
3. Extract the capture coordinator and remove viewed-session selection from
   server-global state.
4. Move score jobs and artifact resolution to explicit session IDs.
5. Add catalog, selected/active state separation, history, and the unpersisted
   New state in the shared React application.
6. Add recoverable Delete with active/job guards and traversal tests.
7. Remove ambiguous compatibility routes only after the shared application
   and retained old consumers no longer require them.

Likely backend boundaries are a catalog/repository module, capture coordinator,
score-job coordinator, and a thinner HTTP handler. Exact filenames belong in
the bounded tactical written when implementation begins.

No initial backend slice should add a central authoritative database,
permanent purge, editable labels, or resumption. React belongs to the
separately reviewed shared-application phase, not an incidental part of a
backend route refactor.

## Validation Contract

The implementation tactical must prove:

- every existing valid v2 session appears after restart;
- New creates no directory before microphone or replay actually starts;
- Start creates a distinct ID and leaves prior sessions readable;
- two browser selections cannot redirect capture or each other;
- event, score, export, and artifact responses match the requested session;
- late responses for a prior selection are discarded;
- active and score-busy sessions reject deletion;
- deletion moves only the validated target to recoverable trash;
- traversal and malformed IDs cannot escape the workspace;
- a deleted selected session transitions predictably to history or New;
- stale active manifests still recover as failed after process loss;
- bounded pagination does not load every session artifact or event database;
  and
- v1 behavior plus the corrected-note transcription and score regression
  suites remain green.

## Recommended Direction

Keep the live musical-notebook hierarchy and explicit selected-versus-active
split stable. Human labels must remain application annotations; aggregate
counts must remain rebuildable from the materialized event index; previews
must remain bounded and source-sample-derived; and library playback must stay
read-only and on demand.

Same-session resumption, trash restoration, permanent purge, continuation
relationships, and library pagination beyond the current bounded page remain
separate future tacticals. Preserve explicit IDs and immutable evidence from
the deferred
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
without pulling cloud storage or sync into this local foundation.
