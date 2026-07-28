# 040 — WebSocket Runtime Dependency

Topic: live-acoustic-transcription

Topic: home-hosted-family-sharing

Status: **complete and live on 2026-07-28.** A live microphone attempt reached
`/api/live`, but Uvicorn rejected the upgrade because neither `websockets` nor
`wsproto` was installed in the locked project environment. The browser
consequently received an ordinary 404 and reported `The local capture
WebSocket failed.` The locked runtime now includes `websockets`, and the
authenticated public upgrade reaches the application.

## User-Visible Outcome

- An authenticated family browser can establish the existing `/api/live`
  WebSocket before microphone PCM capture begins.
- The ordinary locked install contains the WebSocket protocol implementation;
  operators do not repair a running virtualenv manually.
- A missing protocol implementation fails automated validation rather than
  appearing only during physical microphone use.
- Authentication, one-writer capture ownership, binary framing, source-sample
  timing, and model behavior remain unchanged.

## Implementation

1. Declare the smallest Uvicorn-compatible WebSocket protocol package as a
   core project dependency and regenerate the lock.
2. Add a server-runtime test proving Uvicorn resolves a WebSocket protocol
   class from the locked environment.
3. Run focused tests, the complete migration regression, and the production
   build.
4. Restart the already-active service, verify the public shell and protected
   capability boundary, and perform an authenticated WebSocket handshake that
   does not start or mutate a capture.
5. Record the result here and in the focused continuing topics.

Validated commits use:

```text
Topic: live-acoustic-transcription
Topic: home-hosted-family-sharing
```

## Invariants

- PCM transport remains a same-origin authenticated binary WebSocket.
- The WebSocket dependency is part of ordinary local, family, and packaged
  desktop environments rather than an operator-only extra.
- The handshake check sends no PCM and creates no session or artifact.
- No capture evidence or active writer lease is changed to validate packaging.
- v1 and v2 WebSocket implementations remain runnable.

## Acceptance

- Uvicorn's auto-selected WebSocket protocol class is non-null in the locked
  environment.
- Existing family WebSocket authorization and binary-framing tests pass.
- A real public `wss://.../api/live` request reaches the application instead
  of Uvicorn's unsupported-upgrade fallback.
- An anonymous handshake remains unauthorized.
- An authenticated handshake may open and close before capture without
  creating a session.
- The complete repository gates remain green.

## Execution Record

### Landed slices

- `36f693a` recorded the observed live failure, dependency boundary, and
  handshake-only acceptance contract.
- `9782061` added `websockets>=13,<17` to the ordinary project dependencies,
  locked version 16.1.1, and added a family-server regression that loads
  Uvicorn configuration and requires a non-null auto-selected WebSocket
  protocol class.

The focused family-server suite passed ten tests. In the corrected locked
environment, Uvicorn selects
`WebSocketsSansIOProtocol`; before the dependency change it selected `None`
and logged `No supported WebSocket library detected`.

The complete migration regression passed at
`results/migration-regression/20260728T124051Z/report.json`: 211 Python tests,
86 frontend tests, six TypeScript contract/runtime tests, generated-contract
drift, TypeScript, the high-severity npm audit, Ruff, retained JavaScript
syntax, and Git whitespace all passed. The production Vite build also passed
with only the existing OpenSheetMusicDisplay chunk-size advisory.

The already-active authenticated macOS service restarted as launchd PID
49586. The public homepage returned HTTP 200, and anonymous capabilities
remained protected with HTTP 401. A real anonymous `/api/live` WebSocket
upgrade reached the application and was rejected with HTTP 403. A temporary
local-operator session then opened the public authenticated WebSocket and
closed it before sending Start. The session catalog contained the same nine
IDs before and after, and the operator session was revoked. No PCM, capture
lease, session, artifact, or retained evidence was created or changed.
