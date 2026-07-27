# 030 — Idle Model Worker Eviction

Topics: live-acoustic-transcription,
multi-tenant-hybrid-service-architecture

Status: **implemented on 2026-07-27.**

## Motivation

The isolated Basic Pitch and Transkun workers were already created lazily on
the first capture, but remained alive until the application stopped. Three
settled-idle samples reported 0.0% CPU for both workers, so idle compute was
not the concern. Their reported resident sizes were 442,304 KiB and
1,721,520 KiB, approximately 2.06 GiB when summed. The full application
process group reported approximately 2.3 GiB, although process RSS can count
shared pages more than once.

The first cold public capture began at `2026-07-27T09:33:44.879Z`; its session
started at `2026-07-27T09:33:48.607220Z`, an observed cold-start interval of
approximately 3.73 seconds. Retaining workers briefly therefore helps repeat
captures, while indefinite retention is disproportionate for an on-demand
personal service.

## Implementation

- Preserve lazy model construction: reads and service startup do not load
  either worker.
- Schedule eviction only after capture settlement or failure has completely
  released the active session and pipeline.
- Keep both workers warm for ten idle minutes by default.
- Cancel pending eviction as soon as a new capture successfully claims
  ownership.
- Bind each callback to a generation so a canceled callback that was already
  dispatched cannot unload models used by a newer capture.
- Hold capture ownership while unloading so a claim and teardown cannot race.
- Close both workers at eviction and let the existing factories create fresh
  adapters on the next preview or commit request.
- Report load state, idle start, eviction deadline, timeout, and last unload
  time in the existing session diagnostic response.
- Treat a timeout of zero as explicit keep-warm behavior; reject negative
  values.

The v2 and v3 commands accept `--model-idle-timeout-seconds`. The macOS share
service defaults `ATPIANO_MODEL_IDLE_TIMEOUT_SECONDS` to 600, validates it,
records it in lifecycle and status output, and writes it into the generated
launchd environment.

## Validation

- Deterministic timer tests cover full-settlement scheduling, eviction,
  canceled and stale callbacks, zero keep-warm behavior, and negative input.
- A local-pool test proves unload closes both workers and that the next model
  request constructs fresh instances.
- CLI and share-service tests cover both command versions, the default and
  zero timeout, and launchd template propagation.
- The complete migration regression and production frontend build are
  recorded below.
- The active macOS service is restarted after validation. Its public homepage
  and capability API are checked through Caddy, and its diagnostic API is
  checked for an unloaded pool with no worker processes before first use.

## Execution Record

`uv run atpiano migration-regression` passed with report
`results/migration-regression/20260727T104428Z/report.json`: 153 Python
tests, 46 Vitest tests, five TypeScript node tests, contract drift, typecheck,
npm audit, Ruff, legacy JavaScript, and Git whitespace all passed. The
separate production Vite build passed with only the existing OSMD chunk-size
advisory.

The already-active macOS service was restarted. Its generated launchd plist
contains a 600-second timeout, and the persistent lifecycle log records the
same setting on the new `start_requested` event. The public homepage,
`/api/v1/capabilities`, and `/api/session` each returned HTTP 200. Capabilities
still advertise local runtime mode, microphone and replay capture, score
availability, and the `atpiano.contract.v1` schema. Before first use, the
diagnostic state reported `loaded: false`, no eviction deadline, and no worker
processes. The service remained ready at `192.168.1.104:8002`.
