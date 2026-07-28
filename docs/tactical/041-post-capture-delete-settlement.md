# 041 — Post-Capture Delete Settlement

Topic: session-workspace-management

Status: **complete and live on 2026-07-28.** A newly recorded session could
finish settling in the selected-session query while the session catalog
remained cached as `stopping`. The workspace derived Delete visibility from
that stale catalog entry, so the action did not appear until a full page
reload refreshed the catalog. Detail and catalog lifecycle state now converge
independently, and the selected detail controls immediate deletion safety.

## User-Visible Outcome

- A user can create a session, record, stop, and delete the completed session
  without reloading the page.
- Delete appears as soon as the selected session's authoritative detail has
  reached a deletable status.
- Active and stopping sessions remain protected from deletion.
- Sidebar and Sessions-home lifecycle state converges automatically after
  capture settlement instead of retaining a stale live indicator.

## Implementation

1. Add an application regression with a selected detail that has settled
   while the first catalog snapshot still reports `stopping`.
2. Derive the selected session's active/deletable state from its current
   detail and the browser-owned capture, not only catalog identity.
3. Keep the catalog polling while any returned item is `active` or
   `stopping`, including the post-Stop interval after client capture state
   becomes idle.
4. Run the focused application tests, complete frontend suite, TypeScript,
   production build, repository regression, and Git whitespace validation.
5. Restart and verify the shared application only if its service is active.

Implementation commits use:

```text
Topic: session-workspace-management
```

## Invariants

- The backend remains authoritative about whether deletion is allowed.
- The UI never offers Delete for a selected `active` or `stopping` session.
- Browser capture ownership continues to protect its session while a local
  capture lifecycle remains attached.
- Selection stays client-local and does not redirect the capture writer.
- Polling stops after the catalog no longer contains an unsettled session.
- No session, recording, event, score, or artifact evidence changes merely
  because lifecycle state is refreshed.

## Acceptance

- A selected `complete` detail exposes Delete even when the immediately prior
  catalog snapshot said `stopping`.
- A stale `active` or `stopping` catalog causes a follow-up catalog request
  while the browser capture state is otherwise idle.
- The refreshed catalog removes stale live state without a document reload.
- Existing active-session deletion protection and explicit historical
  deletion tests remain green.

## Execution Record

### Landed slices

- `8985983` recorded the stale catalog/detail split, immediate-deletion
  outcome, independent polling contract, and safety invariants.
- `c31c26e` made both the selected detail and session catalog poll their own
  `active` or `stopping` result until settlement. The selected workspace now
  derives active/deletable state from current detail status plus browser
  capture ownership rather than a stale matching catalog ID.

The focused regression starts with a `complete` selected-session detail and a
first catalog snapshot that still says `stopping`. It proves Delete appears,
the catalog requests a settling follow-up, and the user can move the session
to recoverable trash without reloading. The complete frontend suite passed 89
Vitest tests and six TypeScript runtime/contract tests; TypeScript also passed
independently.

The production Vite build passed with only the existing
OpenSheetMusicDisplay chunk-size advisory. The complete migration regression
passed at
`results/migration-regression/20260728T125317Z/report.json`: 218 Python tests,
89 frontend tests, six TypeScript runtime/contract tests, generated-contract
drift, TypeScript, the high-severity npm audit, Ruff, retained JavaScript
syntax, and Git whitespace all passed.

The already-active authenticated macOS service restarted as launchd PID
48549. The public homepage returned HTTP 200, and anonymous capabilities
remained protected with HTTP 401.
