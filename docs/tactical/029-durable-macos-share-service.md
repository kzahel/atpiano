# 029 — Durable macOS Share Service

Topic: multi-tenant-hybrid-service-architecture

Status: **implemented on 2026-07-27.**

## Motivation

The foreground `scripts/share-atpiano` process disappeared between public
reviews. Caddy remained healthy, but its Mac upstream no longer listened on
port 8002 and the public hostname returned an empty 502. The foreground
launcher retained no file logs, restart state, exit status, or lifecycle
history, so the prior termination could not be reconstructed.

## Implementation

- Keep `scripts/share-atpiano` as the direct foreground diagnostic command.
- Add an on-demand, repository-managed macOS `launchd` service with
  `start`, `stop`, `restart`, `status`, and `logs` controls.
- Supervise the process with `KeepAlive` after manual registration, but keep
  the plist outside `~/Library/LaunchAgents` so reboot and login do not
  automatically publish the application.
- Retain UTC lifecycle events plus unbuffered stdout and stderr below
  `~/Library/Logs/atpiano/`; bound stdout and stderr with five-file, 5 MiB
  circular rotation by default.
- Launch from a generated runtime copy of the supervisor so editing the
  tracked shell source cannot change a running shell while it handles Stop.
- Preserve the existing `caffeinate` assertions, LAN-only bind, exact public
  origin, and v3 application command.
- Fail before side effects with a clear macOS requirement on Linux and other
  unsupported hosts.
- Tell repository agents to restart and publicly verify an already-active
  service after completed live-application changes, without starting a
  deliberately inactive service.

## Validation

- Parse the tracked plist template and assert on-demand supervision, log
  paths, and an interactive process classification.
- Validate every sharing script with `bash -n`.
- Execute every sharing entry point behind a fake Linux `uname` and require
  an explanatory exit status 69.
- Bootstrap the generated plist on the Mac, verify its listener and service
  state, force an unexpected child exit, and confirm `launchd` restarts it.
- Verify the public homepage, capability API, and workspace API through
  Caddy after migration from the foreground process.

## Execution Record

The foreground process was stopped and the generated job was bootstrapped in
the user's GUI launchd domain. `status` reported the listener ready at
`192.168.1.104:8002`. A deliberate SIGKILL of the exact managed
`uv run atpiano workbench-v3` child produced lifecycle exit status 137.
Launchd started a new runner and restored the listener in approximately one
second; its state then reported `Runs: 2` and `Last exit: 137`.

A normal `restart` recorded the requested stop, forwarded SIGTERM, recorded
child status 143, unregistered the old job, rendered a fresh runtime copy, and
started one clean replacement. The generated plist contains no `RunAtLoad`,
uses the ignored repository runtime directory, and sends application output
through the configured bounded rotators.

The public homepage, `/api/v1/capabilities`, and `/api/v1/workspaces` each
returned HTTP 200 after migration. The capability response retained local
runtime mode, microphone and replay capture, score availability, and the
`atpiano.contract.v1` schema.

`uv run atpiano migration-regression` passed with report
`results/migration-regression/20260727T065639Z/report.json`: 131 Python tests,
46 Vitest tests, five TypeScript node tests, contract drift, typecheck, Ruff,
npm audit, legacy JavaScript, and Git whitespace all passed. The separate
production Vite build passed with only the existing OSMD chunk-size advisory.
