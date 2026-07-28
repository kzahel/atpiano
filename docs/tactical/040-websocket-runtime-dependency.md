# 040 — WebSocket Runtime Dependency

Topic: live-acoustic-transcription

Topic: home-hosted-family-sharing

Status: **diagnosed and implementing on 2026-07-28.** A live microphone attempt
reached `/api/live`, but Uvicorn rejected the upgrade because neither
`websockets` nor `wsproto` was installed in the locked project environment.
The browser consequently received an ordinary 404 and reported `The local
capture WebSocket failed.`

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

Pending implementation.
