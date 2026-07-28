# 037 — Detachable Score Playback

Topic: performance-to-notation

Topic: session-workspace-management

Status: **accepted implementation plan.** The user accepted the complete
interaction and architecture direction before implementation and authorized
end-to-end work with commits after each validated slice.

## Motivation

The selected-session transport, inspection views, and committed score share
one source-sample position, but they do not share one playback lifecycle.
`AudioPlayback` privately owns its media element, playing state, seeking
state, active audio segment, and error. Only `inspectionSample` is published
through the workspace store.

That split causes two user-visible failures:

- the score cannot distinguish active playback from a manual seek or another
  inspection action; and
- entering the dedicated reader unmounts the transport and media element.

The inline score also delegates following to OpenSheetMusicDisplay. OSMD
1.9.9 calls `scrollIntoView({block: "center"})` whenever the visible cursor
updates with following enabled. Because the score sits in a bounded
scrollable panel inside the workspace document, OSMD can move both the score
panel and the surrounding page. The next mapped attack therefore overrides a
user scrolling toward the Pause control.

The current line cursor identifies one score position but does not emphasize
the chord or noteheads at that attack.

## User-Visible Outcome

### Persistent playback

- Selected-session playback has one persistent application-level media host.
- Its session, status, position, duration, availability, error, and score
  follow state are published through a dedicated Zustand store.
- The media element, animation frame, seek lock, desired sample, and segment
  transition details remain private controller state rather than store data.
- Opening or closing the exact-score reader does not interrupt playback.
- The reader toolbar exposes a compact Play/Pause action and source-time
  position from the same transport.
- Selecting another session, returning to Sessions, starting New, or losing
  the configured source stops and resets selected-session playback.
- The Sessions homepage retains its bounded, lazy, row-local preview players.
  Those players do not hydrate a selected session and remain mutually
  exclusive within the library.

### Detachable inline score following

- A fresh selected-session playback run begins with score following attached.
- Attached following scrolls only the inline score panel. It never scrolls
  the workspace document.
- The panel moves only when the score cursor leaves a comfortable visible
  band; it does not recenter on every attack.
- A deliberate user scroll, wheel, touch move, scrollbar movement, or
  scrolling key detaches following immediately.
- Detachment stops only automatic movement. The score cursor, current-attack
  highlighting, piano roll, keyboard, scrubber, and audio remain synchronized.
- While playback continues detached, a floating **Follow playback** action
  remains visible over the score.
- Activating that action reattaches following and performs one bounded move to
  the current playhead.
- Detachment survives pause, resume, and seek. A new session/source or a new
  run after playback reaches the end restores the attached default.

### Current score attack

- Keep the existing discrete vertical score cursor as a subdued positional
  guide.
- Also highlight every rendered notehead under the current OSMD cursor,
  including chord members on both staves.
- Apply and remove a transient SVG class through OSMD's graphical-note API.
  Do not rerender or mutate the pinned MusicXML, source alignment, or original
  note colors.
- Treat this as the current score attack. It does not claim continuous tempo,
  acoustic sustain, or pedal-aware sounding-note reconstruction.

### Reader boundary

- Reader playback uses the persistent transport and current-attack highlight.
- Manual reader page turning remains the default from Tactical 020.
- Playback does not turn a reader page automatically in this slice.
- A later explicit reader **Follow playback** mode may turn pages only after
  separate subjective review.

## State And Controller Shape

Create a focused playback store rather than expanding the general workspace
store:

```text
session ID
source identity and availability
idle / playing / paused / ended / error
source-sample position, duration, and sample rate
following / detached
error detail
```

Mount one playback provider around both workspace and reader layouts. The
provider owns the hidden audio element and exposes Play, Pause, Toggle, and
Seek commands through a React context. It publishes observable snapshots to
Zustand and drives the existing shared inspection sample from the media clock.

`inspectionSample` remains a separate workspace concept because it also
represents manual roll and keyboard inspection. Manual transport seeks use
the playback controller, and playback ticks update inspection. The provider
must retain the existing feedback-loop guard when an external inspection
change asks the transport to seek.

Do not reuse `followHead`: that name belongs to following the live capture
horizon and is not the score-playback attachment state.

## Implementation Slices

1. Add the playback Zustand store, persistent provider/controller, transport
   context, and selected-session configuration.
2. Convert the workspace transport to the shared controller and add reader
   Play/Pause continuity.
3. disable native OSMD document following; add app-owned visible-band panel
   movement, automatic user detachment, and the floating reattach action.
4. Add current-attack notehead highlighting with complete restoration across
   seeks, rerenders, score changes, and unmount.
5. Add focused store, transport, score, reader, and application tests; run the
   complete regression and production build.
6. Record evidence here and in continuing topic docs, then restart and verify
   the shared service if it is active.

Each implementation commit should use:

```text
Topic: performance-to-notation
Topic: session-workspace-management
```

## Invariants

- The audio sample clock remains the playback timeline.
- The persistent controller never changes capture evidence, transcript
  events, score artifacts, or alignment artifacts.
- One selected-session controller cannot continue playing bytes from a
  previously selected session.
- Blob URLs are not revoked while the controller can still consume them and
  are released when their query data is retired.
- Store status reflects media outcomes; the DOM media element and imperative
  locks are not serialized into Zustand.
- Detached following never disables cursor or note synchronization.
- Programmatic panel movement cannot accidentally detach itself.
- OSMD never receives authority to scroll the workspace document.
- Old or invalid score alignment still renders notation without a cursor,
  note highlight, follow action, or playback claim.
- Reader page identity, exact artifact pinning, manual navigation, and
  responsive reflow remain intact.

## Automated Acceptance

- Play, pause, seek, end, media failure, segment transition, session reset,
  and source reset publish deterministic playback snapshots.
- Entering and leaving reader mode preserves playback and position.
- The reader can pause and resume the same persistent playback.
- Starting a fresh run attaches score follow.
- User scrolling detaches before another attack can move the panel.
- Detached pause/resume and seek remain detached.
- Reattach moves to the current cursor once and resumes bounded following.
- Playback-driven following changes only score-panel `scrollTop`; browser
  `scrollY` remains unchanged.
- Programmatic movement does not trigger detachment.
- Current cursor notes gain the playback class and prior notes lose it across
  forward movement, backward seeking, coverage loss, rerender, and unmount.
- Chords highlight every current notehead without changing MusicXML bytes.
- Reader pages remain manual during playback.
- TypeScript, focused UI tests, all frontend tests, production build, Python
  checks, migration regression, and Git whitespace pass.

## Manual Validation

On a representative retained score:

1. Start playback with the transport visible and confirm only the score panel
   follows.
2. Scroll the score and the outer page with mouse/trackpad and touch; confirm
   following detaches and Pause remains reachable.
3. Pause, resume, and seek while detached; confirm there is no snap back.
4. Activate **Follow playback** and confirm one bounded return to the cursor.
5. Inspect dense chords, repeated notes, rests, system transitions, low bass,
   and high treble for clear current-attack highlighting.
6. Enter the reader during playback, pause and resume there, turn pages
   manually, then return to the workspace without losing playback position.
7. Check narrow and wide layouts, keyboard access, reduced motion, and a
   minimum 44 CSS-pixel reattach target.

## Rollback

The new provider and store replace only the selected-session browser
transport. Removing them can restore the component-local media element.
Disabling panel following and note highlighting leaves audio, inspection,
score rendering, alignment artifacts, reader paging, piano roll, keyboard,
and exports intact.

## Execution Record

Pending implementation and validation.
