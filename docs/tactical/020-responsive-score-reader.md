# 020 — Responsive Fullscreen Score Reader

Topic: performance-to-notation

Status: planned on 2026-07-26; implementation has not started. Implement after
the score renderer work in
[`018-score-playback-alignment.md`](018-score-playback-alignment.md) settles
so both features share one retained OpenSheetMusicDisplay instance and reflow
path.

## Motivation

The shared React application renders the current committed score inline with
the piano roll, keyboard, transport, session summary, and exports. That is a
useful preview, but the score paper is capped at 620 CSS pixels and scrolls
inside its card. It is not a practical view for placing a phone, tablet, or
laptop at the piano and turning pages while playing.

The score artifact and its presentation have different identities:

- the exact MusicXML bytes own notes, rests, rhythms, measures, voices,
  meter, spelling, and other score semantics; and
- the reader owns responsive page geometry, system breaks, zoom, density,
  one- or two-page presentation, and the current reading position.

Pinning a score must freeze the first identity, not freeze one set of rendered
pixels. The same MusicXML may occupy a different number of pages or screens
after a viewport resize, device rotation, density change, or fullscreen
transition.

The current generated MIDI2ScoreTransformer MusicXML supplies score semantics
and basic scaling without forced system or page breaks. OpenSheetMusicDisplay
1.9.9 can therefore reflow it using its page format, custom page format, zoom,
and container width. Future imported MusicXML may include explicit layout
directives and needs separate evidence rather than silent rewriting.

## User-Visible Outcome

The inline **Committed score** card remains a compact workspace preview and
adds **Open score reader** when MusicXML is available.

The reader is a dedicated, responsive application mode:

```text
← Workspace     Morning progression     Measure 9     3 / 8     ⛶
─────────────────────────────────────────────────────────────────
‹                     [ page 3 ] [ page 4 ]                     ›
```

It:

- fills the ordinary browser viewport even when the native Fullscreen API is
  unavailable;
- can enter native browser fullscreen from an explicit user action;
- presents one score screen on a phone or portrait tablet and one or two
  pages on larger viewports when both remain readable;
- turns with visible controls, keyboard commands, edge taps, and horizontal
  swipes;
- accepts common Bluetooth page-turn pedals that emit keyboard commands;
- reflows the pinned MusicXML after resize or orientation change;
- returns to the page containing the prior musical position after reflow;
  and
- never silently replaces the score when a newer snapshot finishes.

## Product Contract

### Exact snapshot pin

Opening the reader captures the selected session ID, MusicXML artifact ID,
full SHA-256, source horizon, and exact MusicXML bytes. Those values remain
the reader's score identity until the user explicitly chooses another
snapshot.

A score refresh may revise any earlier measure. If a newer MusicXML artifact
becomes current while the reader is open:

- continue displaying the pinned artifact;
- show a quiet **Newer score available** action;
- switch only after explicit confirmation; and
- use score alignment to recover the closest source position when available,
  otherwise fall back to the same measure ordinal or the nearest surviving
  measure.

The current local artifact catalog exposes only the snapshot followed by
`score/current.json`, even though prior snapshot directories remain on disk.
Exact pinning must survive reload and copied URLs. Add exact artifact lookup
for retained historical score snapshots without making every old snapshot an
ordinary export-list item. A known opaque artifact ID must continue to resolve
within its explicit workspace and session while that snapshot is retained.

The reader URL should name the selected session, reader mode, and opaque score
artifact ID. It must not identify the score as merely "current." Page number
is optional presentation state and is not a durable score identity.

### Semantic anchor, not page identity

Page numbers are layout-local. A score may be page 3 of 8 on a laptop and
screen 6 of 17 on a phone.

Maintain the reading position as:

1. a source sample when the exact score-alignment artifact supplies one;
2. otherwise the zero-based MusicXML measure ordinal in the pinned artifact;
   and
3. a page index only as derived state for the current render.

Before any reflow, capture the first visible measure or aligned source
position. After rendering, rebuild the page-to-measure map and select the page
containing that anchor. Do not infer the position from a percentage of total
SVG height.

### Responsive layout profiles

Select profiles from measured available width, height, pixel density, and
minimum readable score size, not from user-agent strings.

- **Phone:** one screen at a time, width-fitted notation, safe-area-aware
  controls, and a screen-shaped custom page format that favors one or a small
  number of grand-staff systems over a shrunken full A4 sheet.
- **Portrait tablet or narrow desktop:** one portrait page at a time.
- **Wide tablet or desktop:** a two-page portrait spread only when each page
  remains at least as readable as the accepted one-page minimum; otherwise
  retain one page.
- **Print-like view:** conventional A4 portrait pagination, independent from
  the phone screen profile.

Offer **Large**, **Comfortable**, and **Compact** density choices. Responsive
defaults choose a profile, while the explicit choice persists for the current
client. Density changes are view-only and trigger anchor-preserving reflow.

The first implementation may tune profile thresholds through representative
fixtures and manual review. It must not promise an exact number of measures
per system: OSMD derives measure fit from musical density, available width,
engraving rules, and zoom. Any later exact break override belongs in
reader-layout state or a derived presentation artifact, never as an
unrecorded mutation of the pinned MusicXML.

### Page turning

Support:

- previous and next buttons with at least 44 by 44 CSS-pixel touch targets;
- tap zones at the left and right edges that do not cover the toolbar;
- horizontal swipe with a deliberate distance and direction threshold;
- `ArrowLeft`, `PageUp`, and supported pedal-back commands for previous;
- `ArrowRight`, `PageDown`, and supported pedal-forward commands for next;
  and
- first/last-page boundary feedback without wrapping unexpectedly.

Do not take over keystrokes from a focused button, input, select, or link.
Space remains available to a future playback control rather than becoming the
only page-turn command. Respect reduced-motion preferences and keep the
transition short enough that rapid turns do not queue animations.

Manual page turning is the default. Automatic page following during playback
is outside this first slice. Tactical 018 may move the score cursor within the
visible page; a later explicit **Follow playback** mode may turn pages only
after subjective review confirms that it is not surprising while performing.

### Fullscreen and application navigation

Reader mode removes the session rail, metrics, piano roll, keyboard, exports,
and other workspace chrome. It uses `100dvh`, safe-area insets, and a
reader-owned overflow boundary.

Native fullscreen is progressive enhancement:

- call `requestFullscreen()` only from the reader's explicit fullscreen
  control;
- observe `fullscreenchange` instead of assuming the request succeeded;
- keep the CSS viewport-filling reader fully usable when the API is absent or
  rejected;
- let Escape leave native fullscreen according to browser behavior; and
- retain a visible **Workspace** action and ordinary browser Back behavior.

Do not require or force orientation lock.

## Implementation Slices

### 1. Prove OSMD pagination and isolate its adapter

- Use the pinned OSMD 1.9.9 APIs `setPageFormat("A4_P")`,
  `setCustomPageFormat(width, height)`, and `Zoom` against the golden musical
  fixture and representative real scores.
- Confirm how OSMD exposes rendered pages, measure positions, cursor state,
  and reflow without depending on incidental SVG class names.
- Encapsulate page discovery, page-to-measure mapping, zoom, render
  cancellation, and cursor restoration behind one React-facing score
  renderer adapter.
- Test MusicXML with and without `<print new-system>` and
  `<print new-page>` directives. Preserve explicit authored layout by default
  and make any responsive override an explicit view policy.
- Compare Verovio only if OSMD cannot provide stable paged output or reliable
  measure anchoring for the same MusicXML. Do not switch renderers merely to
  implement application chrome.

### 2. Exact retained-artifact addressing

- Make exact access to a known historical MusicXML artifact ID resolve within
  the named workspace and session after `score/current.json` advances.
- Keep path containment, artifact hash verification, media type, session
  identity, and recoverable-deletion behavior intact.
- Do not broaden ordinary artifact listing unless a separate score-history UI
  is designed.
- Add fixture-runtime evidence for two score snapshots in one session: the
  reader stays on the first while the second becomes current.

### 3. Shared renderer and reader route

- Refactor the current inline `MusicXmlScore` so preview and reader share
  loading, cancellation, errors, the retained OSMD instance, and Tactical
  018's cursor integration.
- Add a reader-mode URL that preserves the opaque session and artifact IDs.
- Add **Open score reader** to the inline score card without changing Render
  or Refresh behavior.
- Render only the dedicated reader layout while reader mode is active.
- Return to the same selected session and inline score when leaving.
- Fail soft to the inline workspace and MusicXML download when exact artifact
  access or OSMD rendering fails.

### 4. Responsive paging and position restoration

- Observe the reader viewport with `ResizeObserver` and debounce only enough
  to avoid redundant OSMD renders during a resize.
- Choose one-page, two-page, or phone-screen format from measured space and
  the active density profile.
- Capture the semantic anchor before reflow and restore the page containing
  it afterward.
- Rebind the score cursor after OSMD recreates graphical pages.
- Prevent stale asynchronous renders from publishing after a newer viewport,
  density, session, or artifact intent.
- Keep page controls and page count correct when the last spread has only one
  page.

### 5. Performance interactions and fullscreen

- Add buttons, edge taps, swipe navigation, and guarded keyboard handlers.
- Add the native fullscreen control and resilient non-native fallback.
- Auto-hide nonessential toolbar detail after inactivity while keeping a
  reliable way to reveal it with touch, pointer, or keyboard.
- Provide accessible labels, focus visibility, live page-position text, safe
  color contrast, reduced-motion behavior, and minimum touch targets.
- Do not place essential actions only in hover affordances.

### 6. Hardening and subjective validation

- Exercise resize, rotation, fullscreen entry/exit, session switching, score
  refresh, artifact deletion, render failure, and browser Back.
- Measure render and reflow duration on the current 19-measure fixture and a
  longer retained score. Page turning after render must not rerun score
  inference or reload MusicXML.
- Validate the reader at the piano, at realistic viewing distance, rather
  than accepting screenshots alone.
- Run the complete frontend, Python, contract, and migration regressions.

## Automated Acceptance

- The inline score preview and its current Render/Refresh behavior remain
  available.
- Opening reader mode pins one exact artifact ID and SHA-256.
- Publishing a newer snapshot does not change the open reader until the user
  accepts it.
- Reloading a reader URL resolves the same retained MusicXML snapshot while
  it exists.
- One pinned XML fixture produces different page counts at phone and desktop
  widths without changing its bytes or hash.
- Reflow after resize, rotation, density, or fullscreen preserves the same
  measure or aligned source anchor.
- A phone-width viewport has no application-level horizontal overflow and
  never requires an entire A4 page to shrink below the accepted readable
  size.
- One-page and two-page layouts select correctly from measured space.
- Buttons, edge taps, swipes, keyboard commands, and page boundaries behave
  deterministically.
- Interactive descendants do not trigger accidental page turns.
- Native-fullscreen rejection leaves a fully usable viewport-filling reader.
- OSMD load or render failure leaves the pinned MusicXML downloadable and the
  workspace recoverable.
- Tactical 018's cursor either restores after reflow or remains explicitly
  unavailable; it never points into a different snapshot.
- Focused tests, TypeScript checks, the production build, Python checks, and
  the migration regression pass.

## Manual Validation Matrix

Review at minimum:

| Viewport | Expected default |
|---|---|
| 360 × 800 phone portrait | one screen, large density, touch controls |
| 844 × 390 phone landscape | one screen, width-fitted systems |
| 768 × 1024 tablet portrait | one portrait page |
| 1024 × 768 tablet landscape | one page or readable two-page spread |
| 1440 × 900 laptop landscape | readable two-page spread |

For each target:

- sight read the same nontrivial grand-staff passage at realistic distance;
- turn forward and backward with touch or pointer;
- turn with keyboard commands and one representative Bluetooth pedal if
  available;
- rotate or resize while positioned in the middle of the score;
- enter and leave fullscreen;
- confirm that notation size, toolbar, safe areas, cursor, and page position
  remain usable; and
- generate a newer snapshot and confirm the visible score does not change
  silently.

The review records the selected density, system count, rendered page count,
minimum observed stave size, reflow duration, and any clipped or crowded
notation. The user accepts the default phone, tablet, and laptop profiles
before this tactical becomes complete.

## Explicit Exclusions

- No score-inference, quantization, meter, voice, spelling, or pedal change.
- No live or progressive engraving.
- No automatic page turning in the first slice.
- No score editor, drag-to-reflow authoring, or permanent system-break edit.
- No renderer replacement unless the OSMD feasibility evidence fails.
- No PDF generation or print-dialog redesign.
- No orientation lock, wake lock, remote control, gesture camera, or MIDI
  sustain-pedal repurposing.
- No score-history browser beyond exact access to an already known pinned
  artifact.
- No Phase 4 application-core extraction or hosted-service work.

## Rollback

Reader mode is additive. Removing its route, responsive layout, and exact
historical score lookup leaves the current inline MusicXML preview,
Render/Refresh workflow, score artifacts, alignment, piano roll, keyboard,
playback, and exports intact.

## Execution Record

No implementation commits yet.
