# 036 — Musical Session Workspace Refresh

Topic: session-workspace-management

Topic: practice-companion-product-vision

Status: **active on 2026-07-28.** The user accepted the complete direction
before implementation and authorized end-to-end work with commits after each
validated slice. Pause only if a material product or safety decision requires
human review.

## Motivation

The shared React application exposes too much implementation state and gives
too little prominence to the musical objects a player returns to:

- steady-state `Schema v1` and `Local engine` labels do not help operate the
  workspace;
- the question-mark control has no useful action;
- one page-top notice receives unrelated capture, event, score, export,
  engraving, deletion, and download results;
- the selected-session hero and four summary cards consume too much space,
  while the artifact count and visible session diagnostics add noise;
- generated session labels cannot be replaced with human names;
- the detected-key keyboard cannot be auditioned; and
- the history rail is not a sufficient library for revisiting performances.

The accepted product direction is a musical notebook: a Sessions homepage,
compact performance identity, local feedback, editable human naming, and
immediate pitch audition.

## User-Visible Outcome

### Sessions homepage and navigation

- The root workspace is a dedicated newest-first Sessions library.
- Clicking the `atpiano` brand returns to that homepage.
- The single-workspace subtitle `On this device` is omitted.
- The desktop rail retains a bounded recent-session shortcut list and an
  explicit path to all sessions.
- Narrow-screen session navigation reaches the same library rather than
  becoming a separate product surface.
- The library shows title, local date, source, duration, meaningful status,
  compact playback, and a lazily loaded opening-phrase piano-roll preview.
- The opening preview begins at the first detected note and covers a short
  source-time range. It is not labeled as a measure because meter and
  engraving may not exist.
- At most one library recording plays at a time. Playback and preview loading
  do not select or mutate a session.

### Compact selected-session identity

- Replace the oversized hero and four-card metrics row with a compact session
  header.
- Preserve a live, session-wide recognized-note count and corrected-note
  progress.
- Keep duration, date, source, and meaningful lifecycle state.
- Remove the artifact-count summary, visible session ID, sample rate, schema
  version, steady-state runtime badge, and inert help control.
- Retain exports themselves and keep the session ID in the selected URL.

### Editable names

- A pencil affordance enters inline title editing for users with write
  authority.
- Changes autosave after a short pause; Enter or blur saves immediately and
  Escape restores the last persisted value.
- `Saving`, `Saved`, and retryable failure states appear beside the title.
- Empty or whitespace-only names are rejected without erasing the persisted
  name.
- Human names live in an application-owned annotation document. Capture
  manifests, event evidence, audio, and generated artifacts remain immutable.
- Existing sessions without annotations continue to receive the automatic
  local date-and-source label.

### Contextual feedback

- Remove the shared page-top notice state.
- Capture failures remain in capture controls.
- Event, score, playback, export, rename, and library-preview failures appear
  at the affected surface with an appropriate retry where useful.
- Short-lived, self-clearing toasts are reserved for non-blocking
  confirmations such as a completed download or recoverable deletion.
- A page-level blocking state remains appropriate when the workspace itself
  cannot load.
- Transport fallbacks retain operation context instead of exposing only `The
  local runtime request failed`.

### Keyboard audition

- Convert the passive 88-key image into a pointer-, touch-, and
  keyboard-accessible audition surface.
- Use a small Web Audio piano-like synthesizer with no network, sample-pack,
  or new licensing dependency.
- Start sound on press and release it on pointer release, cancellation, or
  loss of contact. Pointer movement across keys may audition a glissando.
- Auditioned and detected pitches have distinct visual states.
- Audition never changes transcript events, source-time inspection, playback,
  or capture state.

## Contract And Storage Shape

1. Add a versioned session-annotation patch/result contract and an explicit
   runtime mutation addressed by workspace and session ID.
2. Store annotation data atomically in the application-owned session
   document, never in `session.json`.
3. Expose aggregate recognized and corrected note counts in the bounded
   Session summary. Read them from the materialized event index without
   loading event payloads.
4. Add the mutation to fixture, local HTTP, authenticated family, and desktop
   runtime paths with existing role and target validation.
5. Preserve old session readability when `application.json` or its annotation
   fields are absent.

## Implementation Slices

1. Contract, application service, local adapter, HTTP/runtime providers,
   generated TypeScript, and tests for annotations and aggregate counts.
2. Compact workspace chrome, contextual feedback ownership, title editor,
   permissions, and responsive behavior.
3. Web Audio keyboard audition with focused synthesis and interaction tests.
4. Sessions homepage, brand navigation, bounded recent rail, lazy preview
   events, and on-demand row playback.
5. Full regression, production build, live-service refresh when active,
   focused browser review, and documentation evidence.

Each validated slice should be committed separately with:

```text
Topic: session-workspace-management
Topic: practice-companion-product-vision
```

## Invariants

- Selection remains browser-local and cannot redirect active capture, score
  jobs, exports, deletion, preview reads, or delayed responses.
- Musical time remains source-sample-derived.
- Session annotation writes do not alter completed performance evidence.
- Active capture remains reachable from both the Sessions homepage and a
  historical selected session.
- Library rows stay bounded; the page must not eagerly load every session's
  audio, artifacts, or complete event history.
- Fixture, local browser, authenticated family, and desktop compositions keep
  one shared React application and runtime contract.
- v1 and v2 prototype workbenches remain compatibility surfaces.

## Validation

- Python application and adapter tests cover annotation absence, update,
  validation, atomic persistence, target isolation, trash movement, and
  aggregate counts.
- Local and authenticated HTTP tests cover write authorization and explicit
  target validation.
- Contract fixtures and generated TypeScript remain in sync.
- React tests cover homepage navigation, bounded recent history, row
  selection, lazy preview/playback, inline rename save/error states,
  contextual errors, transient confirmations, compact summaries, and removal
  of diagnostic chrome.
- Keyboard tests cover note-on, note-off, cancellation, repeated pointers,
  distinct detected/auditioned presentation, and unavailable Web Audio.
- TypeScript, frontend tests, the production build, Python tests, Ruff,
  migration regression, and Git whitespace pass.
- If the shared macOS service is active, restart it and verify the public
  homepage, authenticated session selection, capability protection, rename,
  library playback/preview, selected performance, and keyboard audition.

## Human Review Boundary

Implementation may proceed without an intermediate review. Pause only if:

- human naming cannot remain separate from capture evidence;
- the homepage conflicts with active-capture safety;
- a licensed or materially larger audio asset becomes necessary;
- the opening preview would require unbounded list hydration; or
- a required behavior cannot be shared across browser, authenticated family,
  and packaged desktop runtimes.
