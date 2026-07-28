# 039 — Continuous Library Playback

Topic: session-workspace-management

Topic: performance-to-notation

Status: **accepted for implementation on 2026-07-28.** The user approved the
complete interaction direction and authorized end-to-end implementation with
commits after validated slices.

## Motivation

The Sessions library and selected-session workspace expose the same retained
recording through two unrelated browser playback lifecycles. Each library row
creates a private audio element, while the workspace and exact-score reader
share an application-level media element. Opening a playing library session
therefore unmounts its player and interrupts the recording even though
navigation is an in-place application state change.

The library progress track is decorative rather than seekable, and its opening
piano-roll preview neither follows playback nor acts as a direct path into the
session. Recordings also begin at source sample zero even when silence precedes
the first detected note.

## User-Visible Outcome

### One continuous transport

- The application owns one playback media element for Sessions, a selected
  session, and the exact-score reader.
- Opening the currently playing session, returning to Sessions, or entering
  and leaving its score reader preserves source identity, position, and
  playing or paused state.
- Selecting a different session or beginning a new capture remains an
  intentional source change and stops or replaces the prior recording.
- Starting another library recording replaces the current source; two
  recordings never play concurrently.
- Navigation remains SPA-style and never reloads the document to move among
  these surfaces.

### Library seeking and preview

- Replace the decorative row progress track with an accessible source-time
  slider spanning the complete recording.
- Seeking the active row preserves its prior playing or paused intent.
- Seeking an inactive row prepares that recording paused at the requested
  source sample; it does not begin sound unexpectedly.
- The opening piano-roll preview shows a source-clock playhead while its
  session is current and playback lies inside the displayed phrase.
- The complete preview is a keyboard- and pointer-accessible path into the
  session. Playback controls do not accidentally trigger navigation.

### First-note cue

- A fresh playback run starts 750 milliseconds before the earliest visible,
  non-retracted note, clamped to source sample zero.
- Cueing occurs only when the listener has not already chosen a source
  position. Pause/resume, an ordinary route transition, and a manual seek to
  zero do not jump forward.
- Starting again after the recording reaches its end creates a fresh run and
  applies the cue again.
- Sessions without a detected note start at zero.
- Cueing changes only the initial media position. The complete recording and
  its leading silence remain available through every seek control and export.

## Controller And Query Shape

Playback identity must be independent from selected-page identity. Extend the
focused playback store with the current playback session and preparation
intent, and keep the media element, seek locks, blob URLs, and autoplay intent
private to the provider.

Move selected-session audio-source loading into a reusable playback-source
query keyed by the current playback session. Library Play or seek explicitly
prepares a session; selecting a page alone must not begin playback. The
provider retains its source configuration across layout changes when the
session and artifact identity are unchanged.

The existing bounded opening-preview query supplies the earliest note and the
short phrase display. It remains viewport-lazy for ordinary library browsing.
An explicit playback request may resolve the same bounded query before
applying the cue. Do not add an eager all-session artifact or event read.

Workspace inspection remains selected-session state. Playback ticks update
its piano roll, keyboard, and score only when the playback and selected session
identities match.

## Implementation Slices

1. Record this tactical, index it, and update the continuing topic direction.
2. Decouple playback identity from route selection, centralize recording
   source loading, and convert library controls to the shared transport.
3. Add full-duration library seeking, first-note cue state, clickable opening
   previews, and a phrase-local source-clock playhead.
4. Add focused provider, application, and Sessions-library tests; update
   continuing documentation with the landed contract and evidence.
5. Run TypeScript, the frontend suite, production build, migration regression,
   and Git whitespace; restart and verify the shared service only if active.

Each implementation commit should use:

```text
Topic: session-workspace-management
Topic: performance-to-notation
```

## Invariants

- The audio sample clock remains the playback and visualization timeline.
- Route transitions alone never recreate or reset an unchanged playback
  source.
- At most one browser media element owns retained-session playback.
- Selecting history never mutates capture, event, score, or recording
  evidence.
- Leading silence remains seekable and is never removed from an artifact.
- A deliberate manual seek always wins over automatic first-note cueing.
- Preview and audio hydration remain bounded, lazy, and session-addressed.
- Blob URLs remain valid while the persistent controller can consume them and
  are revoked when their query data is retired.
- Playback for one session never moves another selected session's inspection
  cursor.
- Active capture, recording import, v1, and v2 compatibility surfaces retain
  their existing behavior.

## Automated Acceptance

- Library Play prepares the row in the persistent provider and no row creates
  a private audio element.
- Only one library session can be current, and preparing another replaces it.
- A row slider seeks by source sample with pointer and keyboard input.
- Inactive-row seeking prepares paused playback without starting sound.
- Fresh Play cues to `max(0, first_note - 750 ms)`; no-note sessions cue to
  zero.
- Manual seek to zero, pause/resume, and same-session navigation do not
  reapply the cue.
- Replaying after `ended` applies the cue as a new run.
- Sessions → selected session → reader → selected session → Sessions preserves
  the same media element, position, status, and source identity.
- Selecting a different session or beginning New replaces or clears playback
  predictably.
- The opening preview exposes an Open action and displays a playhead only for
  its active session and visible source range.
- Mismatched playback and selection never publish a false inspection sample.
- Existing bounded-preview, score-follow, reader, capture, and import tests
  remain green.

## Human Review Boundary

Implementation may proceed without an intermediate review. Pause only if:

- route-independent playback would permit audio from one session to drive
  another session's musical views;
- applying the first-note cue requires unbounded event hydration;
- one persistent source cannot represent segmented retained recordings; or
- continuous playback conflicts with active-capture safety.

## Execution Record

Pending implementation.
