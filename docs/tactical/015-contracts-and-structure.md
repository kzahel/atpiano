# 015 — Contracts And Structure

Master phase: 2. Contracts and structure

Topic: multi-tenant-hybrid-service-architecture

Topic: session-workspace-management

Status: implementation revised after initial R2 feedback on 2026-07-26;
awaiting mandatory R2 review. Phase 3 has not started.

## Entry Evidence

- Phase 1 completed in
  [`014-freeze-migration-baseline.md`](014-freeze-migration-baseline.md).
- `uv run atpiano migration-regression` passes 57 Python tests plus the
  JavaScript, lint, syntax, and whitespace lanes.
- Stable legacy route products and aligned fixture hashes are tracked in
  `tests/fixtures/migration/legacy-contracts.json`.
- R1 found no ambiguous useful behavior requiring a product decision.

## User-Visible Outcome

The current v1 and v2 applications remain independently runnable. In
addition, the repository exposes a small, versioned atpiano vocabulary and
explicit session-addressed local compatibility API that the Phase 3 shared
frontend can consume without depending on global current-session selection.

The Phase 2 review packet makes names, repository shape, dependency direction,
runtime behavior, examples, generation, and compatibility concrete before
broad React migration begins.

## Invariants

- Source event time, horizons, and PCM continuity use absolute source samples.
- Every read, job, artifact, and mutation target has explicit workspace and
  session identity.
- Selection is client-local and cannot retarget capture, replay, or a score
  job.
- Existing v1 and v2 artifacts remain readable without migration.
- Existing unqualified v2 routes remain temporary compatibility aliases.
- Pydantic is the source for public contract schemas; generated TypeScript is
  checked and not hand-maintained.
- Contract schemas do not import HTTP, browser, Tauri, persistence adapters,
  or existing corrected-session implementations.
- Concrete adapters depend on contracts; no framework-independent
  application layer is introduced before Phase 4 has real services to place
  in it.
- Types cover the next executable slices rather than speculative billing,
  deployment, or general-sync behavior.

## Exact Implementation Scope

### 1. Versioned contract schemas

Add a dedicated inward-facing Python contract package with checked schemas
for:

- user, workspace, membership, session, capture, and transcription run;
- event revision and sample-clock horizons;
- artifact, score snapshot, job, provenance, capability, and structured
  error;
- bounded cursor pages and operation results; and
- the versioned sample-indexed PCM envelope.

Use opaque validated IDs rather than selecting a permanent UUID format.
Reject incompatible schema and protocol versions explicitly. Preserve
existing corrected-event semantics through compatibility conversion rather
than renaming old evidence in place.

### 2. OpenAPI, generated client, and runtime provider

Add one reproducible command that:

- exports the atpiano OpenAPI document from Pydantic;
- generates checked TypeScript schema types;
- verifies generated files have no drift; and
- runs cross-language fixtures through runtime validation.

Establish the initial TypeScript application workspace containing:

- generated wire types and a typed HTTP client;
- a hand-owned `AtpianoRuntime` behavioral interface;
- request cancellation and late-result identity rules;
- event subscriptions with explicit disposal;
- fixture replay, session listing and reads, capture Start/Stop, artifacts,
  score-job state, recoverable deletion, and capability discovery; and
- no React, Vite, Tauri, or platform-specific component code.

### 3. Local session compatibility seams

Introduce focused adapter modules for:

- a read-only local session catalog over existing v2 manifests;
- validated explicit session resolution;
- session-addressed state, event range, score state, and artifact reads;
- an explicit one-active-capture coordinator view;
- score jobs frozen to their target session and commit horizon; and
- recoverable trash movement with active and score-job guards.

Expose bounded `/api/v1/...` routes for these behaviors. Retain
`/api/session`, `/api/events`, `/api/score`, `/api/replay`, `/api/live`, and
their current artifact aliases for the framework-free v2 client.

### 4. Structure and dependency enforcement

Add:

- shared JSON fixtures for representative successful and failed values;
- Python and TypeScript serialization/validation tests over the same bytes;
- dependency tests that prevent contract-schema imports from reaching HTTP,
  filesystem-adapter, Tauri, React, or generated-client code;
- path, traversal, pagination, selected-versus-active, late-target, score-job,
  and recoverable-delete tests; and
- an actual directory/responsibility map matching the implemented tree.

## Explicit Exclusions

- No React components, visual migration, interaction redesign, or Zustand.
- No Tauri shell, sidecar protocol, desktop packaging, or model packs.
- No hosted authentication, PostgreSQL, object storage, Redis, worker service,
  tenancy enforcement, collaboration, or sync.
- No framework-independent extraction of capture and transcription
  orchestration; that belongs to Phase 4.
- No permanent purge, restore UI, session rename, continuation, or resumption.
- No public operation or distribution of MIDI2ScoreTransformer.
- No model, decoder, reconciliation, latency-policy, or score-quality tuning.
- No removal or semantic change of v1/v2 commands or compatibility routes.

## Migration And Compatibility

The atpiano contract has its own explicit `v1` version and adapters from
existing v2 manifests and events. It does not rewrite existing session files.
Catalog scanning treats manifests as authoritative and `.trash` as excluded.

The current v2 page continues to use global aliases until Phase 3. New API
routes always name their target. A compatibility route may call a local
adapter, but contract types cannot import the HTTP server.

Generated output changes only through the documented generation command.
Breaking changes require a new schema/protocol version; additive compatible
changes retain fixtures and tests for older supported readers.

## Automated Validation

- generated OpenAPI and TypeScript drift check
- Python schema and compatibility-adapter tests
- TypeScript typecheck and runtime fixture tests
- explicit session/catalog/score/artifact/delete HTTP tests
- dependency-direction tests
- `uv run atpiano migration-regression`

The aligned fixture remains unchanged and current v1/v2 regression lanes stay
green after each implementation commit.

## Manual Validation

No microphone is required to bring up Phase 2. The R2 packet includes one
optional compatibility smoke:

1. run `uv run atpiano workbench-v2` over an existing workspace;
2. verify the existing page still opens its latest session;
3. query the API catalog and one explicit historical session;
4. confirm browsing that history does not alter the active capture identity;
   and
5. confirm an artifact and score target still name the requested session.

## Human Review Packet

R2 receives:

- a compact actual directory tree and responsibility map;
- a dependency-direction diagram and enforcement evidence;
- the hand-owned `AtpianoRuntime` interface;
- one workspace, session, capture, event revision, job, artifact, provenance,
  and error example;
- PCM envelope, capability, cancellation, subscription, and compatibility
  policy;
- the exact OpenAPI/TypeScript generation workflow;
- explicit retained, wrapped, generated, and expected-to-be-replaced code;
- test results and the Phase 2 commit range; and
- any names or boundaries whose review is especially costly to defer.

This is a mandatory hold. Do not begin Phase 3 until the user explicitly
accepts or revises the packet.

## Rollback Or Disable Path

Contract schemas, generated clients, adapter modules, routes, and fixtures are
additive. Reverting this series restores the Phase 1 baseline. Recoverable
delete moves data only after explicit confirmation and retains it under the
workspace `.trash`; no permanent purge exists.

## Execution Record

The bounded implementation landed as:

- `e2c2b9d` opened this tactical after the accepted R1 handoff;
- `751f425` defined strict Pydantic product and PCM schemas;
- `2ecca9e` added deterministic OpenAPI generation, generated TypeScript,
  typed HTTP composition, and the runtime interface;
- `d5bfc01` validated shared representative bytes in Python and TypeScript;
- `f308366` added inward ports plus the local catalog, reader, artifact, and
  recoverable-trash adapter;
- `3ccb70f` exposed explicit local product routes and target-frozen score jobs;
- `3441dcd` added an executable deterministic runtime provider; and
- `7fdc3d1` kept capture transport provider-owned and limited generated HTTP
  paths to actually implemented ordinary operations; and
- `3b53285` applied R2 terminology feedback: moved Python responsibilities to
  `contracts` and `adapters`, renamed the TypeScript workspace to `app`,
  published `/api/v1` and `atpiano.contract.v1`, and removed unused
  application ports.

The reviewed implementation range is `e2c2b9d^..3b53285`.

Pydantic 2.13.4 is the direct Python schema dependency. The application
workspace pins TypeScript 5.9.3, openapi-typescript 7.13.0, openapi-fetch
0.17.0, tsx 4.23.1, AJV 8.20.0, and transitive security overrides captured
in `app/package-lock.json`. `npm audit --audit-level high` reports zero
vulnerabilities.

The final unattended report is
`results/migration-regression/20260726T103639Z/report.json`. It passed 77
Python tests, both retained JavaScript suites, generated-contract drift,
TypeScript typecheck, five TypeScript runtime tests, npm audit, Ruff,
JavaScript syntax, and Git whitespace checks.

The mandatory review packet is
[`r2-structure-contracts-review.md`](../r2-structure-contracts-review.md).
No Phase 3 tactical has been created.
