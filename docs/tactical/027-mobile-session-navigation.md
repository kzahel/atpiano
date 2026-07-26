# 027 — Mobile Session Navigation

Topic: session-workspace-management

Status: **complete on 2026-07-26.**

## Motivation

The accepted narrow-screen layout hid the session-history heading and every
session row. Mobile users could create a new session but had no path back to a
previous performance.

## Implementation

- Add a persistent **Sessions** control to the mobile workspace top bar.
- Present the existing New action and complete session list in an off-canvas
  drawer instead of duplicating session state or navigation.
- Close the drawer through its close button, the page backdrop, Escape, New,
  or a historical-session selection.
- Preserve the sticky desktop rail and explicit selected-session URL behavior.
- Keep drawer controls at touch-friendly sizes and respect device safe areas.

## Validation

- Component tests cover opening the drawer, selecting history, automatic
  closing, and Escape dismissal.
- `npm run typecheck --prefix app` passes.
- `npm test --prefix app` passes 44 tests across 11 Vitest files and five
  Node contract/runtime tests.
- `npm run build --prefix app` passes.

## Exclusions

- No session-catalog, capture, deletion, runtime, or URL-contract changes.
- No changes to the dedicated score reader.
