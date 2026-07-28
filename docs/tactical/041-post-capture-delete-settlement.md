# 041 — Post-Capture Delete Settlement

Topic: session-workspace-management

Status: **implementing on 2026-07-28.** A newly recorded session can finish
settling in the selected-session query while the session catalog remains
cached as `stopping`. The workspace currently derives Delete visibility from
that stale catalog entry, so the action does not appear until a full page
reload refreshes the catalog.

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

Pending.
