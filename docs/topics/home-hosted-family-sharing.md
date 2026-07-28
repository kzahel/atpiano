# Home-Hosted Family Sharing

Topic: home-hosted-family-sharing

Status: **accepted near-term deployment direction as of 2026-07-28; basic
family identity implementation is authorized under Tactical 033.** The v3
application is shared on demand from the Mac through the home Pi and Caddy.
SQLite users, memberships, and cookie sessions are now active implementation
scope. The managed PostgreSQL, object-storage, OIDC, broad tenancy, and sync
program remains deferred with no active implementation schedule.

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

This is not a production multi-tenant service, a high-availability promise,
or a public score-runtime distribution decision.

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

The service is intentionally available only while the Mac is online and the
repository-managed service has been started. A stopped or offline Mac makes
the public application unavailable; that is expected behavior, not an
incident requiring failover. A reboot leaves the service stopped until an
explicit `start`; it must not be silently converted into an always-on login
service.

## Persistence Direction

The current local filesystem session manifests and checksummed artifacts are
authoritative. Corrected sessions already use `event-index.sqlite3` as a
rebuildable range/history index over append-only JSONL evidence, so the
bundled Python runtime already exercises SQLite. What R5 did not implement is
a workspace-level SQLite catalog.

Tactical 033 adds a transactional SQLite catalog on the Mac. Its identity and
authorization rows are authoritative relational data; its references to
capture sessions remain a rebuildable index over filesystem evidence:

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

Before the service is treated as private durable family storage or its URL is
shared more broadly, complete the bounded SQLite account and cookie-session
system in
[`033-sqlite-family-authentication.md`](../tactical/033-sqlite-family-authentication.md).
Validate ordinary HTTP, artifacts, and microphone WebSockets through it.
This authorization does not include public signup, invitations, email,
password reset, OIDC, or managed multi-tenant infrastructure.

### Verified current exposure

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

Until then:

- treat the endpoint as a limited public trial;
- keep the service off when it is not intentionally being shared;
- avoid relying on it as the only copy of irreplaceable recordings; and
- do not publicly expose the unresolved internal score runtime.

## Operating Contract

The established commands remain:

```text
scripts/share-atpiano-service start
scripts/share-atpiano-service status
scripts/share-atpiano-service logs
scripts/share-atpiano-service restart
scripts/share-atpiano-service stop
```

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
3. complete the SQLite family identity and session catalog;
4. enforce proportionate family access control before broader sharing; and
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
