# SQLite Family Authentication

Topic: home-hosted-family-sharing

Status: **authorized on 2026-07-28; implementation in progress.**

## Outcome

Add a small, typed identity and authorization layer for the home-hosted
application:

- SQLite stores users, workspaces, memberships, and opaque web sessions;
- SQLAlchemy 2 owns the relational adapter and Alembic owns schema changes;
- administrators create or update basic username/password accounts through
  the CLI;
- a FastAPI composition serves the public/self-hosted application with cookie
  authentication;
- the React application provides a minimal login and logout flow;
- every workspace, session, artifact, score, replay, delete, and microphone
  WebSocket operation requires an authorized workspace member; and
- desktop retains its existing per-launch loopback authentication and receives
  one synthetic local owner rather than a web login or profile switcher.

Capture audio, manifests, event evidence, recordings, MIDI, JSONL, MusicXML,
and other large artifacts remain files below the configured workspace.
SQLite is not their replacement.

This is proportionate family access control. It does not reopen the managed
PostgreSQL, OIDC, object-storage, invitation, email, password-reset, sync, or
high-availability program deferred in Tactical 013.

## Current Evidence

The Python packages already use modern type annotations, typed `Protocol`
ports, Pydantic boundary contracts, and framework-independent application
services. The current HTTP adapter is a custom `ThreadingHTTPServer`.
`User`, `Workspace`, and `Membership` wire models already exist, but only the
single `local` workspace is materialized and no person is authenticated.

The per-session `event-index.sqlite3` databases are rebuildable indexes over
append-only event evidence. There is no workspace-level relational catalog,
password hash, browser session, login route, membership query, authorization
check, or login view.

The desktop sidecar already requires a random per-launch bearer token for
ordinary HTTP and a token-derived WebSocket subprotocol. That protects the
loopback process boundary and is retained independently from browser-user
authentication.

On 2026-07-28 the public homepage, capabilities route, and workspace route
were reachable without credentials. Session and artifact enumeration were
deliberately not attempted.

## Accepted Decisions

1. Use synchronous SQLAlchemy 2 with typed `Mapped[...]` models. The workload
   does not justify async database access.
2. Use Alembic migrations and SQLite WAL mode. Keep the schema compatible
   with a possible later PostgreSQL adapter without claiming that migration
   is automatic or currently required.
3. Store password hashes with Argon2id. Never store or log plaintext
   passwords.
4. Store only a SHA-256 digest of each high-entropy web-session token.
   Browser cookies contain the opaque token and receive `Secure`, `HttpOnly`,
   `SameSite=Lax`, `Path=/`, and host-only semantics.
5. Do not use JWT, public signup, email verification, password reset,
   invitations, MFA, or external identity.
6. Start with one seeded `local` workspace. CLI-created users become explicit
   members of it with owner, editor, or viewer role.
7. Owner and editor may capture, replay, generate score variants, and delete.
   Viewer is read-only. All three roles may review sessions and artifacts.
8. The public FastAPI composition is additive until the authenticated path
   passes automated validation and human login review. The existing local and
   desktop launch paths remain regression oracles.
9. A public-origin process fails closed if authentication is selected but no
   enabled owner exists.
10. Do not switch or restart the live service until a human creates the first
    account and reviews the local authenticated build.

## Numbered Implementation Plan

### 1. Dependencies and adapter boundary

- Add pinned-compatible FastAPI, Uvicorn, SQLAlchemy, Alembic, and Argon2
  dependencies.
- Keep imports from domain/application packages independent of FastAPI,
  SQLAlchemy, and Alembic.
- Add dependency tests for the boundary.

Commit checkpoint: dependency graph resolves and the existing regression lane
still imports.

### 2. Relational schema and migrations

- Add typed SQLAlchemy models for users, workspaces, memberships, and web
  sessions.
- Use stable opaque text IDs, normalized unique usernames, UTC timestamps,
  disabled flags, role constraints, token digests, absolute expiry, and last
  use.
- Seed the configured local workspace idempotently.
- Configure SQLite foreign keys, busy timeout, and WAL mode.
- Add Alembic configuration and the initial migration.
- Test migration from an empty database and repeated startup against an
  existing database.

Commit checkpoint: a fresh SQLite file reaches Alembic head and preserves
relational invariants.

### 3. Typed identity service and administrator CLI

- Add framework-independent principal, password, membership, and browser
  session operations behind a typed repository port.
- Add `atpiano users create`, `users set-password`, `users disable`,
  `users enable`, and `users list` commands.
- Prompt for passwords without echo; allow a test-only injected password path
  without exposing a plaintext command-line option.
- Revoke existing web sessions when a password changes or a user is disabled.
- Avoid username-enumerating authentication errors.

Commit checkpoint: CLI and service tests cover creation, duplicate usernames,
password verification, role membership, expiry, revocation, and disabled
users.

### 4. Authenticated FastAPI composition

- Extract the corrected-workbench runtime state from the custom HTTP server so
  both HTTP adapters can call the same application services.
- Add `/api/v1/auth/login`, `/api/v1/auth/logout`, and
  `/api/v1/auth/session`.
- Require a valid principal and workspace membership for every existing
  versioned API route and artifact body.
- Require editor or owner role for replay, capture, score, variant, and delete
  mutations.
- Enforce the configured Host and Origin boundary, request body limits,
  no-store responses, safe file ranges, and typed application-error mapping.
- Authenticate the microphone WebSocket before accepting Start and re-check
  authorization while the connection is active.
- Serve the built React application through the same authenticated
  composition while leaving login assets reachable.

Commit checkpoint: FastAPI integration tests prove unauthenticated denial,
cookie login, authorized reads, role denials, logout/revocation, artifact
protection, and WebSocket denial/acceptance.

### 5. Minimal React login boundary

- Add a small authentication client separate from `AtpianoRuntime`.
- Bootstrap with the current-session route before loading workspace queries.
- Present username/password login, generic failures, pending state, and
  accessible labels.
- Show the current username and Logout in the workspace.
- Clear query state on logout and never retain the password.
- Keep fixture and Tauri modes free of the web-login screen; Tauri exposes the
  synthetic local owner.

Commit checkpoint: TypeScript and component tests cover login bootstrap,
failure, logout, and desktop/fixture bypass.

### 6. Operational hardening and review build

- Add a bounded failed-login delay or limiter appropriate to one process.
- Expire idle and absolute sessions, rotate the token on login, prune expired
  rows, and record only low-sensitivity authentication events.
- Add explicit CLI/database options to the home-sharing launcher without
  enabling them on the live service yet.
- Disable the unresolved score runtime in the public authenticated
  composition unless a separately accepted runtime is supplied.
- Run Python, migration, generated-contract, TypeScript, frontend, build, Ruff,
  and whitespace gates.
- Exercise a temporary local database end to end with owner and viewer test
  accounts.

Human checkpoint: review the local login, authenticated history/artifacts,
viewer denial, logout, and desktop regression. Then create the real owner
interactively and explicitly authorize switching the live launchd service.

## Explicit Exclusions

- Public account creation, email, password reset, invitations, MFA, social
  login, OIDC, or account recovery.
- PostgreSQL deployment or migrations tested against PostgreSQL.
- Object storage, cloud workers, Redis, queues, quotas, billing, or audit
  infrastructure.
- Multi-profile desktop UI or shared browser cookies inside the desktop
  webview.
- Moving capture evidence or large artifacts into SQLite.
- Concurrent capture writers, workspace sync, off-site backup, or a general
  collaboration model.
- Resolving or publicly enabling the internal score runtime.

## Review Evidence

This section becomes the execution record as commits land. Record:

- exact migration head and schema;
- CLI commands and redacted output;
- authorization matrix covered by tests;
- FastAPI and desktop regression results;
- frontend build and login screenshots or manual observations;
- live-service status without switching it; and
- the exact commit range presented for human review.
