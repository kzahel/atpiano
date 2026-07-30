# 047 — Live Settling And Auto-Score Recovery

Topic: live-acoustic-transcription

Topic: performance-to-notation

Topic: home-hosted-family-sharing

Status: **complete and live on 2026-07-30.**

## Motivation

Public session `20260730T171231-934e654037fc` showed two regressions after
Stop:

- Transkun correction began only after Stop and then advanced through the
  whole 173.8-second recording; and
- automatic score generation made no score, although a later manual request
  succeeded.

The Transkun timing did not show an incapable host. Seven public sessions
since automatic correction became the default had all selected after-Stop
because the launchd service still pointed at the absent canonical profile
`results/backend-profile/backend-profile.json`. The affected session's 43
post-Stop decodes averaged 3.858 seconds and peaked at 4.074 seconds. The
retained 2.10-hour M4 Pro profile contains 950 decodes, recommends delayed
background correction, and identifies this model, two-thread execution,
scheduler, and host.

The score failure was a separate browser race. React observed the completed
session before its cached horizon query observed the final commit sample. It
submitted that older sample, the server correctly rejected the non-current
snapshot with HTTP 400, and the one-shot automatic trigger was cleared.

## Implemented Contract

The share service now passes and persistently records
`ATPIANO_BACKEND_PROFILE`. `status` reports the configured path, whether the
file is present and readable enough to identify, its recommendation, and a
short profile ID. A service restart can therefore bind a measured profile
without copying host-specific evidence into Git:

```text
ATPIANO_BACKEND_PROFILE=results/backend-profile-phase4-soak-20260727/backend-profile.json \
  scripts/share-atpiano-service restart
```

The runtime capability response now includes the configured correction mode,
conservative default, profile path/status/identity/recommendation, and reason.
The capture card gives a prominent warning when automatic mode lacks a valid
profile. A valid profile recommendation remains advisory: session start still
loads the commit adapter and verifies exact model, checkpoint, execution,
scheduler, and host identity before selecting it.

Automatic and manual score generation now fetch the authoritative horizon
immediately before starting a score job. The server's exact-horizon check is
unchanged. If the request receives the explicit stale-horizon error, the
client refetches and retries once; other errors are not retried. Artifact
invalidation is scoped to the affected session.

This tactical does not move score-job ownership to the server. That would
require a durable policy for observing or retrying server-created jobs and is
larger than the observed race.

## Validation

- backend-profile tests cover missing automatic configuration and a readable
  measured recommendation;
- service tests cover shell syntax and launchd propagation;
- capability fixtures and generated OpenAPI/TypeScript contracts carry the
  new correction record;
- the capture-card test covers the missing-profile warning; and
- the application regression makes the first automatic score request stale,
  advances the authoritative commit horizon, and proves the one bounded retry
  succeeds at the final sample.

The full migration regression passed with 251 Python tests, 12 TypeScript
Node tests, 105 frontend tests, generated-contract drift, TypeScript, npm
audit, Ruff, JavaScript syntax, and Git whitespace. Its retained report is
`results/migration-regression/20260730T174830Z/report.json`. The production
Vite build also passed.

The already-active authenticated macOS service restarted with profile
`89bd5d3d77a0bbd3ebbc8ed597cbc02f84616f0480bb71fe2f9c90313dd09da0`.
Service status reports the persistent path, `delayed` recommendation, and
short ID. Loading the real Transkun 2.0.1 CPU adapter with two threads and
running the exact profile selector also selected delayed; this proves the
file is not merely present but matches the current model, scheduler,
execution, and host.

The public homepage returned HTTP 200 with `index-BMPwelBe.js`, while the
anonymous capability route remained HTTP 401. A passwordless operator check
through the public origin returned the new correction capability with
`configured_mode=auto`, `backend_profile_status=available`, and
`default_mode=delayed`; it also observed `score_available=true`, read a
1,024-byte MP3 range and the session's 188,103-byte MusicXML, and verified
operator-session revocation. No microphone was activated.
