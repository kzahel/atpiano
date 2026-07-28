# 032 — Cross-Platform Artifact Export

Master phase: 5. Early Tauri skeleton, R5 revision

Topics: `multi-tenant-hybrid-service-architecture`,
`performance-to-notation`

Status: **in progress on 2026-07-28.**

## Entry Evidence

- The internal desktop score runtime passed its first human score-rendering
  review.
- That review found that **Download model baseline** did not produce a visible
  file in the Tauri application.
- The action reads the correct artifact, but finishes through a detached
  browser `download` link. The Tauri shell has no native artifact-save path.
- The baseline MusicXML is already an immutable session artifact and belongs
  with the other session exports rather than with engraving controls.

## User-Visible Outcome

List the original model MusicXML in the session **Exports** panel with a clear
label. Every export action should start an ordinary browser download on the
web and open a native Save As dialog in the desktop application.

## Invariants

- React product components remain platform-neutral.
- Web and desktop export the exact artifact bytes returned by the existing
  session-addressed access contract.
- Desktop exports authenticate to the existing loopback sidecar without
  placing its bearer token in a URL, log, destination file, or webview
  argument.
- Large audio artifacts stream from the sidecar to disk rather than crossing
  Tauri IPC as JSON or one in-memory byte array.
- A cancelled or failed export leaves no partial destination file.
- The desktop webview receives no general filesystem, shell, or HTTP-client
  permission.
- Score baselines remain immutable diagnostic evidence; moving the action does
  not change score selection or generation.

## Exact Implementation Scope

1. Add one runtime-level artifact export operation used by the workspace and
   pinned score reader.
2. Keep the local web adapter's normal browser download behavior.
3. Add a desktop adapter implementation that asks the thin Rust shell to:
   - show a Save As dialog with the artifact's supplied filename;
   - accept only the local sidecar's artifact-content route;
   - authenticate with native-held launch state;
   - stream the declared response length to a sibling temporary file; and
   - atomically publish the completed file at the chosen destination.
4. Remove the baseline download action from the score engraving controls.
5. Identify baseline and selected MusicXML artifacts in the shared Exports
   panel.
6. Update the R5 privilege and review records.

## Explicit Exclusions

- No general webview filesystem, directory, shell, or remote-download access.
- No export archive, batch export, share sheet, recent-destination setting, or
  cloud object-storage work.
- No model, score-generation, score-selection, artifact-schema, or retention
  change.
- No public distribution or change to the provisional score-runtime license
  boundary.
- No Phase 6 signing, updater, SQLite, model acquisition, or settings work.

## Migration And Compatibility

The artifact read and access operations remain unchanged. Existing local web,
fixture, and desktop runtime consumers gain one behavioral export operation.
Old session layouts remain readable.

The custom desktop command opens a user-mediated native dialog and can fetch
only an authenticated `/api/v1/.../artifacts/.../content` path from the
already validated loopback process. It does not accept arbitrary origins or
arbitrary bytes from the webview.

## Automated Validation

- Frontend tests cover baseline placement and dispatch through the shared
  runtime export operation.
- Local-runtime tests cover authenticated browser export bytes and filename.
- Rust tests cover artifact-path validation, response bounds, authenticated
  streaming, exact content length, and atomic publication.
- TypeScript typecheck, frontend tests/build, Rust format/test/Clippy, and the
  existing Python regression lane remain green.

## Manual Validation

- In a browser, export MIDI, event history, audio, current MusicXML, and the
  original model MusicXML and confirm normal downloads.
- In the internal desktop app, repeat those actions, choose destinations, and
  compare each saved SHA-256 with the artifact panel.
- Cancel a Save As dialog and confirm no error or partial file.
- Confirm the score card contains engraving actions only.

## Human Review Packet

Provide the rebuilt internal app, the new privilege delta, automated evidence,
and a short export checklist. Keep R5 open until the user explicitly accepts
the whole desktop boundary.

## Rollback Or Disable Path

Revert this tactical's implementation series. Artifact storage and access
remain unchanged, so rollback does not migrate or remove any session data.

## Execution Record

Implementation and validation evidence will be appended as the slice lands.
