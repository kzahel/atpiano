# Home-Hosted Family Sharing

Topic: home-hosted-family-sharing

Status: **accepted near-term deployment direction as of 2026-07-28; family
identity and performer profiles are implemented and live under Tacticals 033
and 042.** The v3 application is shared on demand from the Mac through the
home Pi and Caddy. The live launchd service uses the authenticated FastAPI
composition backed by SQLite accounts, memberships, groups, profiles, and
cookie sessions. Its configured local score runtime is enabled by default
under Tactical 034 because committed scores are a core requirement of the
private application. The managed PostgreSQL, object-storage, OIDC, broad
tenancy, and sync program remains deferred with no active implementation
schedule.

## Scope And Relationship

This topic owns the current small sharing deployment intended for family use:

- the Mac-hosted React, Python, model, session, and artifact runtime;
- the home Pi/Caddy reverse-proxy boundary;
- on-demand availability and its deliberately modest operational promise;
- the single local workspace and its SQLite identity/catalog layer;
- lightweight access, backup, and recovery requirements appropriate for
  family use; and
- the evidence that would justify revisiting a managed hosted service.

[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
retains the earlier PostgreSQL, object-storage, managed-identity, worker, and
sync design as a deferred option. It is not the current implementation
sequence or a prerequisite for local work.
[`session-workspace-management.md`](session-workspace-management.md) owns the
session identities, selected-versus-active behavior, and local catalog
contract. [`long-session-storage-retention.md`](long-session-storage-retention.md)
owns recording and artifact disk growth.
[`family-workspaces-and-attribution.md`](family-workspaces-and-attribution.md)
owns the implemented account-versus-performer profile boundary, fast
shared-piano selection, creator-versus-performer attribution, and the deferred
shareable multi-space extension.

This is not a production multi-tenant service, a high-availability promise,
or a public score-runtime distribution artifact. The installed internal score
runtime is accepted for this authenticated private home deployment.

## Current Topology

```text
intended family browser
        |
        | HTTPS: https://atpiano.graehlarts.com
        v
home Pi / Caddy
(pi.graehlarts.com)
        |
        | LAN reverse proxy
        v
MacBook on-demand launchd service
        |
        v
v3 React + Python/model runtime
        |
        +---- current filesystem session manifests and artifacts
        |
        `---- SQLite users, memberships, and browser sessions
```

The Pi terminates the public HTTPS connection and proxies the application,
API, artifact, and microphone WebSocket traffic. It does not run inference,
own session state, or store application artifacts. Those remain on the Mac.

Tactical 040 completed a live packaging correction after Uvicorn reported no
installed WebSocket protocol implementation and reduced `/api/live` upgrades
to ordinary HTTP 404 responses. The WebSocket runtime now belongs to the
ordinary locked project environment because microphone capture is a core
family capability, not an optional operator feature. The public authenticated
handshake is accepted while anonymous access remains rejected.

The service is intentionally available only while the Mac is online and the
repository-managed service has been started. A stopped or offline Mac makes
the public application unavailable; that is expected behavior, not an
incident requiring failover. A reboot leaves the service stopped until an
explicit `start`; it must not be silently converted into an always-on login
service.

An open tab may outlive a service restart and its production frontend rebuild.
The retained-score review exposed that Vite removed an old lazy score-renderer
chunk while FastAPI incorrectly returned the new `index.html` for its missing
JavaScript URL. Tactical 045 owns a layered correction: exact asset 404s,
explicit update-and-reload recovery, a small polled client build identity, and
bounded retention of the newest three hashed-asset generations. Retention is
a grace period, not an old-client API compatibility promise.

## Persistence Direction

The current local filesystem session manifests and checksummed artifacts are
authoritative. Corrected sessions already use `event-index.sqlite3` as a
rebuildable range/history index over append-only JSONL evidence, so the
bundled Python runtime already exercises SQLite. What R5 did not implement is
a workspace-level SQLite catalog.

Tactical 033 adds a transactional SQLite identity catalog on the Mac. Its
identity and authorization rows are authoritative relational data. The
capture-session catalog still scans authoritative filesystem manifests; if a
relational session index is added later, it must remain rebuildable from that
filesystem evidence:

- session and artifact manifests remain sufficient to repair or re-index it;
- recordings, MIDI, JSONL, MusicXML, and other large artifacts remain files;
- paths remain validated and rooted below the configured workspace;
- completed evidence remains immutable;
- deletion remains recoverable before permanent purge; and
- SQLAlchemy isolates relational persistence cleanly without making a future
  PostgreSQL deployment part of this tactical.

This gives the family deployment useful restart and query behavior without
introducing cloud accounts, object storage, distributed jobs, or database
operations.

## Sharing And Security Boundary

Exact Host and Origin checks already constrain the configured public origin,
and Caddy supplies HTTPS. They do not authenticate a person. Anyone who can
reach an unauthenticated public hostname is not made trusted merely because
the intended audience is family.

The bounded SQLite account and cookie-session system in
[`033-sqlite-family-authentication.md`](../tactical/033-sqlite-family-authentication.md)
is now the live service boundary. Ordinary HTTP, artifacts, and microphone
WebSockets require an authenticated workspace member. This authorization does
not include public signup, invitations, email, password reset, OIDC, or
managed multi-tenant infrastructure.

### Verified pre-cutover exposure

On 2026-07-28, unauthenticated HTTPS requests to the live hostname returned:

- HTTP 200 for the application homepage;
- HTTP 200 for `/api/v1/capabilities`, reporting the local runtime with
  microphone and replay capture; and
- HTTP 200 for `/api/v1/workspaces`, reporting the single `local` workspace
  with no owner.

No session or artifact enumeration was performed during this check. The
capability response also reported `score_available=true`. That is a separate
release-boundary gap: the unresolved internal score runtime must not remain
available through the public service merely because the local process can
load it.

Before the authenticated cutover:

- treat the endpoint as a limited public trial;
- keep the service off when it is not intentionally being shared;
- avoid relying on it as the only copy of irreplaceable recordings; and
- do not publicly expose the unresolved internal score runtime.

The first authenticated review build also suppressed the score capability,
mutations, and private score artifacts. That was a temporary release hold,
not a satisfactory product default, and was superseded by the authenticated
score decision below. The legacy public launcher still points at a
deliberately absent score runtime if an operator explicitly rolls back to the
unauthenticated composition.

### Authenticated cutover

On 2026-07-28, after an enabled owner was created in the live workspace, the
active launchd service was restarted with persistent family authentication
enabled. Public verification returned:

- HTTP 200 for the application shell, allowing the login UI to load;
- HTTP 401 for `/api/v1/auth/session` without a session cookie; and
- HTTP 401 for `/api/v1/capabilities` without a session cookie.

The service remained active and reported `Family authentication: true`.
Password credentials were not exposed to or exercised by the automated
operator during cutover; the owner retains the human login and artifact
review checkpoint.

The first Safari review exposed a client bootstrap defect: the authentication
client stored `window.fetch` and invoked it with the client instance as its
receiver, producing `TypeError: Illegal invocation` before the login view
could render. Commit `1534b2c` binds the browser function to `globalThis` and
adds a receiver-sensitive regression test. All 55 frontend tests, TypeScript,
and the production build passed. The active authenticated service was
restarted and the public origin served the corrected production asset while
retaining the expected 200 app-shell and 401 anonymous API responses.

The subsequent retained-session review exposed the same receiver defect in
`LocalRuntime`'s direct artifact download path. The session's compact MP3 was
present, verified, and advertised through the protected access route, but
Safari failed before requesting its content and the UI reduced that failure
to `Recorded audio unavailable`. Commit `3ecc5e4` binds the shared runtime
fetch path and adds receiver-sensitive artifact coverage.

That commit also adds a passwordless local-operator check. A caller who
already has filesystem authority over the SQLite catalog may issue a
five-minute session for an enabled workspace member, exercise the protected
application/session/artifact routes, and revoke the session without printing
the token or learning a human password. The check can use an in-process
FastAPI adapter or a running HTTPS origin. Against the reported retained
session and the real public origin, it authenticated as the enabled owner,
read a 1,024-byte range from the protected `audio/mpeg` artifact through
Caddy and launchd, logged out, and verified revocation.

### Authenticated score default

On 2026-07-28 the owner explicitly rejected the score-suppressed family
application as unusable. Tactical 034 makes the configured pinned score
runtime available by default in authenticated family mode. Missing or invalid
runtime assets still degrade cleanly to `score_available=false`; valid assets
enable role-protected score jobs, variants, MusicXML, score-input MIDI, and
alignment artifacts.

The live launchd service restarted with
`Score runtime: results/midi2score-runtime`. A bounded operator check through
the real HTTPS origin reported `score_available=true` and read the selected
701,346-byte partwise MusicXML for retained session
`20260727T185541-a2298f1afaaf`. Anonymous capability requests remained
unauthorized.

This accepts private authenticated home use of the existing internal runtime.
It does not authorize an ordinary desktop archive, public model download, or
general hosted score service while the upstream license remains unresolved.

## Operating Contract

The established commands remain:

```text
scripts/share-atpiano-service start
scripts/share-atpiano-service status
scripts/share-atpiano-service logs
scripts/share-atpiano-service restart
scripts/share-atpiano-service stop
```

An operator can check a specific retained session without a human password:

```text
uv run atpiano family-check \
  --workspace results/workbench-v3 \
  --session SESSION_ID \
  --base-url https://atpiano.graehlarts.com \
  --require-score
```

Omitting `--base-url` exercises an in-process authenticated adapter over the
same real workspace. The operator session expires after five minutes and is
always revoked by the command. This is local catalog authority, not a public
or remotely selectable authentication bypass.

The launchd service supervises unexpected process exits and retains bounded
logs, but it does not provide machine failover or an uptime objective. After
a code change affecting the shared application, restart only when the service
is already active, then verify the public homepage and capability API.

The local coordinator currently permits one active capture at a time.
Multiple family members may review retained sessions, but simultaneous
independent capture writers are not a current product requirement.

## Near-Term Priorities

Work may proceed as small independent tacticals rather than reopening the
eight-phase hosted migration:

1. preserve and improve the working local application;
2. reduce the desktop score/runtime footprint behind exact parity gates;
3. monitor and refine the live SQLite family identity boundary;
4. exercise authenticated history, artifacts, and microphone capture through
   ordinary family use; and
5. add backup, restore, or health checks only from an observed operational
   need.

Signing, notarization, automatic updates, other desktop platforms, and a
full installer are optional product-distribution projects, not prerequisites
for this home-hosted service.

## Deferred Hosted Direction

The following have no active implementation schedule:

- managed OIDC accounts, invitations, memberships, and roles;
- PostgreSQL and row-level tenant policies;
- S3-compatible object storage;
- separately deployed ingest coordinators and worker pools;
- Redis, durable cloud queues, quotas, billing, and audit infrastructure;
- cloud/local synchronization; and
- production multi-tenant availability and operations.

Revisit that architecture only if concrete needs exceed the home deployment,
for example:

- mutually untrusted users need separate authorization domains;
- more than one capture must run concurrently;
- availability while the Mac is offline becomes important;
- off-site durable storage becomes a product requirement;
- family access cannot be secured proportionately at the proxy boundary; or
- measured load no longer fits one machine and one local workspace.

## Recommended Direction

Treat the Mac/Pi path as the product deployment for now. Keep local contracts,
sample-clock timing, explicit session identities, checksummed artifacts, and
model isolation intact because they are useful at any scale. Do not implement
cloud abstractions merely to preserve the option of a future hosted service.
If one of the revisit conditions becomes real, start with a new bounded
architecture review rather than resuming Phase 7 automatically.
