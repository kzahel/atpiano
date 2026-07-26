# Long-Session Storage And Debug Retention

Topic: long-session-storage-retention

Status: direction clarified and scheduled under
[`017-python-application-core.md`](../tactical/017-python-application-core.md)
on 2026-07-26. The immediate product concern is that long sessions and local
debug data must not consume surprising or unbounded disk space. Phase 4 will
exercise the existing 128 kbps MP3 as the interim ordinary retained recording
for new sessions, subject to measured R4 review. Permanent codec, concrete
quota, and cleanup defaults remain unselected.

## Purpose

This topic answers one practical question:

> What may Atpiano keep during long-running local use, how much space may it
> consume, and what happens as the disk budget is approached?

The default application should retain only data that supports the player's
session experience plus a small record of pipeline health. Detailed model
outputs and execution traces may be useful when an agent or developer is
investigating a failure, but they belong to a separate local debug mode with
hard limits and straightforward cleanup.

This topic does not establish a general research-evidence archive, a cloud
billing model, or a promise to preserve every intermediate result. It also
does not select FLAC or a lossy audio codec without measurements.

## Scope And Relationship

This topic owns:

- ordinary-session disk growth;
- temporary-file and duplicate-audio cleanup;
- a separate bounded local debug mode;
- workspace and debug-data budgets, warnings, and low-disk behavior;
- visibility into which categories are using space; and
- measurements needed before calling hour-long sessions storage-safe.

[`live-acoustic-transcription.md`](live-acoustic-transcription.md) owns
capture, source time, model scheduling, and event horizons.
[`session-workspace-management.md`](session-workspace-management.md) owns
session identity, history, selection, and user-requested deletion.
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
owns any later cloud quotas and hosted retention policy.

The bounded-memory and segmented-audio foundation is recorded in
[`009-three-phase-unbounded-sessions.md`](../tactical/009-three-phase-unbounded-sessions.md)
and
[`010-corrected-note-workbench-v2.md`](../tactical/010-corrected-note-workbench-v2.md).
Those tacticals show that processing can remain bounded in memory. They do
not yet prove that disk use is acceptably bounded.

## Current Evidence

The v1 benchmark keeps extensive intermediate data so model and decoder
behavior can be inspected later. Two recent two-minute jobs each use about
274 MiB, which would be roughly 8 GiB/hour if that directory shape grew
linearly. About 117 MiB per take is live native-model windows. This can be
useful for a deliberate debugging run, but it is not an acceptable default
for ordinary practice.

V2 bounds memory with a roughly 40-second PCM ring, segmented disk audio,
capped recent native windows, bounded event queries, and no whole-file Stop
pass. Its current 48 kHz mono PCM16 recording grows by 96,000 bytes per source
second, or 345.6 MB/hour before small container overhead. V2 therefore fixes
the unbounded-memory problem, but its stopped-session disk policy is still
unfinished.

After Stop, V2 also derives one 128 kbps MP3 from the complete WAV segment
sequence. The browser prefers that file for seekable playback and synchronized
scrubbing, and falls back to the WAV segments when FFmpeg is unavailable. The
MP3 grows by roughly 57.6 MB/hour; the measured 37.6-second review session
produced a 602,540-byte file.

The MP3 is currently an additional playback cache. It does not replace or
remove the segmented PCM source, so current stopped-session audio growth is
roughly 403 MB/hour for WAV plus MP3. This playback feature does not by itself
solve the storage concern or select the long-term recording format.

Normalized notes, pedal events, revisions, indexes, and a compact manifest
are expected to be much smaller than audio. That expectation still needs an
actual per-category measurement over hour-long and multi-hour runs.

## Data Classes

### User session data

User session data is retained because it makes a saved session useful to the
player. It currently includes:

- the playable recording;
- normalized note and pedal output needed for review;
- source-time ranges and a bounded index needed to seek and render the
  session; and
- user-requested exports, scores, names, or annotations.

This data is not automatically discarded merely because a debug budget is
full. Its encoding and retention still need a product decision: for example,
the recording could use raw PCM, a lossless codec, or a measured
quality-appropriate lossy codec. The decision should be driven by observed
size, playback needs, and whether future retranscription from the stored
recording matters.

Derived artifacts that can be regenerated need not be retained indefinitely
unless regeneration is expensive or the user explicitly chose to keep them.
The current post-Stop MP3 belongs to this derived-cache category: it is useful
for browser playback and scrubbing, but it is not currently the authoritative
recording.

### Compact pipeline status

Every session may retain a small machine-readable summary that helps the
application and an agent understand what happened:

- pipeline and model versions;
- stage transitions and final state;
- source duration and processed horizons;
- event and error counts;
- compact timing aggregates; and
- explicit gaps, failures, or incomplete finalization.

This is status and provenance, not a verbose trace. It must have a small,
declared size bound and must not contain raw audio, native model arrays, or a
per-window dump.

### Local debug data

Detailed traces exist to diagnose pipeline failures and performance. Examples
include:

- per-window model-native probabilities or tensors;
- verbose scheduler, decoder, reconciliation, and transport traces;
- repeated intermediate audio;
- per-event delivery timings; and
- temporary diagnostic renderings or bundles.

This data is local debug material, not part of the ordinary session contract.
Debug mode is off by default and visibly separate from the session's useful
recording and transcription.

Enabling debug mode does not authorize unbounded retention. A debug run must
declare byte and age limits. When the limit is reached, the system rotates or
evicts the oldest unpinned debug data and records that truncation in the
compact status summary. A useful failure bundle may be explicitly pinned or
exported before routine cleanup; otherwise debug data is disposable.

Debug mode should be possible without uploading anything. Any later upload of
audio or a diagnostic bundle requires a separate, explicit action.

### Temporary working data

PCM rings, scheduler buffers, upload retries, partially written segments, and
materialized visible ranges are transient. They remain bounded by time or
count and are cleaned after their durable replacement is verified.

A crash may leave a recognizable recoverable temporary file. It must not
leave accumulating anonymous spools or cause the session manifest to claim
that missing or incomplete audio is usable.

## Disk-Budget Contract

The implementation should make the following behavior true:

1. Ordinary capture does not persist detailed native model output or verbose
   traces.
2. The workspace reports bytes used separately for recordings, events and
   indexes, derived artifacts, debug data, temporary data, and trash.
3. The application can estimate the current session's bytes/hour after enough
   data has arrived to make the estimate meaningful.
4. Debug data has a hard sub-budget and automatic expiry or rotation. Its
   cleanup never deletes the player's session data.
5. Temporary raw and compressed copies may coexist only while a verified,
   recoverable conversion is in progress.
6. A configurable free-space reserve protects the rest of the machine. The
   application warns before reaching it and stops capture explicitly if it
   cannot safely write another segment.
7. Low-disk behavior produces an understandable incomplete-session state; it
   does not silently drop acknowledged audio.
8. Starting and stopping many sessions does not leak temporary files, model
   windows, open files, or hidden caches.
9. Old session formats remain readable until an explicit, recoverable
   migration policy says otherwise.

The ordinary-session quota and cleanup policy are deliberately not specified
yet. Automatically deleting a player's older recordings would be a separate
product decision and must not be introduced as a side effect of debug
rotation.

## Next Bounded Implementation Slice

Storage ownership and the first compact-retention implementation are folded
into Phase 4 rather than landing in the proof-of-concept HTTP server. The
bounded execution plan is
[`017-python-application-core.md`](../tactical/017-python-application-core.md).
Within that extraction:

1. inventory every file written during one v1 and one v2 session, including
   WAV source segments, the derived playback MP3, temporary, debug, cache,
   export, and trash files;
2. measure bytes by category during deterministic one-hour and multi-hour v2
   replay;
3. stop ordinary v2 sessions from retaining model-native windows or other
   debug-only data after their bounded live use;
4. add a compact per-session pipeline-status record with a tested size bound;
5. implement a separate local debug policy with byte and age caps, rotation,
   truncation reporting, and an explicit pin or export path;
6. expose workspace usage, current-session growth, projected bytes/hour,
   debug usage, temporary usage, trash usage, and the free-space reserve;
7. test repeated sessions, restart recovery, low disk, and deliberately
   interrupted finalization; and
8. measure candidate recording encodings only after the inventory identifies
   audio as the remaining dominant category.

The existing MP3 is the interim Phase 4 implementation choice, not a permanent
codec selection. R4 must review its measured storage behavior and the explicit
loss of new sessions' WAV source before it becomes the ordinary default.
Other codec work remains a later measured decision and should not be bundled
with cloud quotas, permanent deletion, or a general artifact-schema rewrite.

## Acceptance Evidence

Long local sessions are storage-safe enough to advertise when:

- an ordinary one-hour run contains no detailed native arrays, duplicated
  intermediate audio, or verbose per-window traces after finalization;
- actual and projected bytes/hour are reported by category;
- several sequential long sessions leave no unexplained growth outside their
  visible session, debug, temporary, cache, or trash categories;
- debug mode honors both its byte and age limits and ordinary mode immediately
  returns to debug-off behavior;
- a deliberately failed run leaves either a bounded inspectable trace or a
  clear status summary without leaking an unbounded spool;
- restart during recording or finalization recovers acknowledged data or
  records an explicit gap;
- low-disk tests warn and stop cleanly before crossing the reserve; and
- review of a late session range does not read the whole recording or event
  history into memory.

## Open Decisions

- the default workspace budget and protected free-space reserve;
- whether ordinary session data is kept until manual deletion or receives a
  separately designed retention policy;
- recording codec, quality, segment duration, and measured bytes/hour;
- which derived exports are cached versus regenerated;
- the debug byte cap, expiry interval, and pin/export workflow; and
- how much pipeline status is sufficient to diagnose common failures without
  turning the default session into a trace archive.
