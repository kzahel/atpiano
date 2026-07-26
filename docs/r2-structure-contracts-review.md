# R2 Structure And Contracts Review

Status: accepted by the user on 2026-07-26 after the terminology and layering
revision. Phase 3 may proceed.

This packet is the revised mandatory hold after Phase 2. Initial review found
the provider direction useful for a future Android client but the `product`
namespace too generic and the Python application ports premature. The
implementation now names concrete responsibilities and introduces no
framework-independent application layer before real Phase 4 services exist.

This review covers vocabulary, dependency direction, generated contracts,
and the provider boundary before the broad React migration. It does not ask
for approval of a visual design or claim that hosted, Android, Tauri, or
framework-independent application services already exist.

## Actual Repository Shape

```text
contracts/
  fixtures/v1/contract-examples.json   shared successful wire examples
  openapi/atpiano-api-v1.json          generated public HTTP contract

app/
  package.json                         pinned TypeScript tooling and checks
  src/generated/schema.ts              generated wire and HTTP path types
  src/http-client.ts                   typed openapi-fetch composition
  src/runtime/atpiano-runtime.ts       hand-owned behavioral provider boundary
  src/runtime/fixture-runtime.ts       deterministic executable provider
  tests/                               cross-language and provider tests

src/atpiano/contracts/
  schemas.py                           Pydantic source of shared vocabulary
  generation.py                        OpenAPI and TypeScript generation

src/atpiano/adapters/
  local_sessions.py                    existing-v2 compatibility adapter

src/atpiano/corrected_workbench.py     retained v2 composition and additive
                                      /api/v1 adapter routes
tests/
  test_contract_schemas.py             semantic Python contract checks
  test_contract_fixtures.py            shared-byte Python validation
  test_contract_generation.py          deterministic generation and drift
  test_local_session_adapter.py        catalog/path/trash/dependency checks
  test_api_routes.py                    explicit target and compatibility HTTP
```

The current `src/atpiano/web` and `src/atpiano/web_v2` applications are
unchanged. React does not exist yet.

## Dependency Direction

```text
Pydantic contract schemas
          ^
          |
local manifest / event / artifact adapter
          ^
          |
retained v2 HTTP composition

generated TypeScript wire types
          ^
          |
AtpianoRuntime interface
       ^                 ^
       |                 |
fixture provider     Phase 3 local provider
```

Python AST checks prevent contract schemas from importing:

- current corrected-session implementation modules;
- local adapter modules;
- HTTP server modules; or
- filesystem APIs.

The adapter may depend inward on contracts and outward on existing v2
artifacts. `corrected_workbench.py` remains an outer compatibility
composition. There is deliberately no `application` package yet.
Framework-independent capture, transcription, score, and persistence
services remain Phase 4 work and will establish that package from concrete
use cases.

This is a cross-client boundary, not a generic multi-product wrapper. Web and
a future Android application can depend on `AtpianoRuntime` and the same
contract vocabulary. A hosted HTTP/WebSocket provider or a local desktop
provider can fulfill that boundary without exposing transport choices
through UI components.

## Runtime Provider

The hand-owned interface is
[`atpiano-runtime.ts`](../app/src/runtime/atpiano-runtime.ts). It covers:

- capabilities and workspace/session pages;
- explicit session reads;
- microphone Start, versioned PCM, and Stop;
- deterministic fixture replay;
- event subscriptions with idempotent disposal;
- artifacts and access handles;
- score-job start and status;
- recoverable deletion; and
- request cancellation.

Every operation names its workspace, session, capture, stream, job, or
artifact target. Responses repeat their resource identities. Selection is not
a backend property.

Cancellation is cooperative: an `AbortSignal` prevents avoidable work, but a
consumer must still discard a result when its request ID or returned resource
IDs no longer match current intent. This handles responses already crossing a
process or network boundary. A subscription guarantees no callback after its
idempotent `close()` returns.

Capture transport is provider-owned. It is in `AtpianoRuntime` and the
versioned PCM contract, not falsely exposed as ordinary generated JSON HTTP.
The later hosted provider may use authenticated WebSockets; the local provider
may use a loopback sidecar or Tauri bridge. UI components see neither.

The deterministic
[`fixture-runtime.ts`](../app/src/runtime/fixture-runtime.ts) already
executes the boundary through replay, contiguous PCM, Stop, event delivery,
artifacts, score targeting, cancellation, and deletion guards. It gives Phase
3 an executable provider without a test-only transcription domain.

## Public Vocabulary

These names are candidates to survive into UI, APIs, artifacts, and
diagnostics:

| Name | Meaning |
| --- | --- |
| workspace | local-only, cloud, or later explicitly synced ownership scope |
| session | one durable replay, microphone, or uploaded performance |
| active session | a session currently accepting or settling source audio |
| selected session | client-local session being viewed; never server state |
| capture | one writer lifecycle and accepted source-sample horizon |
| transcription run | one versioned preview/commit interpretation |
| event revision | one lifecycle revision of a stable note or pedal identity |
| horizon | source audio head plus provisional and commit sample boundaries |
| artifact | immutable checksummed session product with provenance |
| score snapshot | versioned notation result frozen at one commit sample |
| job | explicit target, input horizon, status, artifacts, and failure |
| provenance | versions, adapter, backend, model/checkpoint, settings, inputs |
| recoverable delete | atomic move to local trash; not permanent purge |

The accepted role names are `owner`, `editor`, and `viewer`. The accepted
workspace modes are `local`, `cloud`, and `synced`; only local behavior is
implemented here. IDs are opaque validated strings. This intentionally does
not freeze a UUID representation before offline/cloud identity requirements
need one.

## Representative Contract Values

The exact shared bytes are
[`contract-examples.json`](../contracts/fixtures/v1/contract-examples.json).
They include:

- a local workspace, user, and membership;
- a complete replay session and an active microphone capture;
- a transcription run, committed C4 revision, and three source horizons;
- a MIDI artifact with nested provenance;
- a score snapshot and running score job;
- a capture-busy structured error;
- local runtime capabilities; and
- a mono PCM16 envelope beginning at absolute source sample 4,096.

Both Pydantic and TypeScript JSON Schema validation accept every example and
reject `atpiano.contract.v2` where `atpiano.contract.v1` is required.
Pydantic also enforces semantic relationships that JSON Schema cannot compare
directly, including offset-after-onset, horizon-before-audio-head,
immediately-prior revision ownership, lifecycle completion, and PCM byte
counts.

## Generation And Compatibility

Install the pinned TypeScript tools, generate, and check drift with:

```text
npm ci --prefix app
uv run atpiano generate-contracts
uv run atpiano generate-contracts --check
npm run typecheck --prefix app
npm test --prefix app
```

Pydantic is the source. The OpenAPI document and
`app/src/generated/schema.ts` are machine-owned. The runtime interface and
typed HTTP composition are hand-owned because they define behavior rather
than serialization.

`atpiano.contract.v1` and `atpiano.pcm.v1` fail closed on incompatible
versions. Strict contract objects reject unknown fields. Additive changes may
extend v1 only when old readers remain valid; a breaking rename, semantic
change, or required field uses a new contract version and compatibility
window.

Existing `atpiano.corrected-*` files are not rewritten. The local adapter
converts them on read and uses deterministic compatibility transcription-run
IDs. Existing:

```text
/api/session
/api/events
/api/score
/api/replay
/api/live
/api/artifacts/...
```

remain for the framework-free v2 client. New catalog, session, horizon, event,
artifact, score-job, and recoverable-delete paths live under
`/api/v1` and always name the target. Tests score and download an
older session while proving the legacy current session remains the newer one.

## Retained, Wrapped, Generated, And Replaced Later

Retained:

- v1 and v2 commands and frontends;
- source-clock capture, inference, reconciliation, horizons, fixtures,
  segmented storage, exports, and score snapshots;
- existing sessions and compatibility routes.

Wrapped:

- v2 manifests as a bounded newest-first local catalog;
- event indexes as explicit contract event pages;
- current exports and score files as checksummed artifacts;
- the existing score runner as a job frozen to session and commit horizon.

Generated:

- OpenAPI components and implemented ordinary HTTP paths;
- TypeScript wire and path types.

Expected to be replaced or thinned:

- server-global current-session composition;
- direct `ThreadingHTTPServer` use for the new application;
- framework-free UI composition;
- compatibility aliases after retained clients no longer need them.

The transcription and score algorithms are retained behind later
application/worker boundaries, not re-created from these contracts.

## Validation Evidence

The initial implementation range was `e2c2b9d^..7fdc3d1`. The terminology and
layering revision is `3b53285`; the reviewed range is
`e2c2b9d^..3b53285`.

The final unattended report is ignored evidence at
`results/migration-regression/20260726T103639Z/report.json` and records:

```text
Python tests:               77 passed, one upstream deprecation warning
v1/v2 JavaScript tests:     pass
OpenAPI/TypeScript drift:   pass
TypeScript typecheck:       pass
TypeScript runtime tests:   5 passed
npm high vulnerability:    0
Ruff:                       pass
JavaScript syntax:          pass
Git whitespace:             pass
```

No microphone, real model, licensed score runtime, or long soak was silently
counted as part of this structure review.

## Review Decision

Please review:

1. Are `workspace`, `session`, `capture`, `transcription run`, `event
   revision`, `horizon`, `artifact`, `score snapshot`, and `job` the right
   durable nouns?
2. Is provider-owned capture transport behind `AtpianoRuntime` preferable to
   pretending every platform uses one HTTP mechanism?
3. Is the concrete `contracts` → `adapters` direction, with the application
   layer deferred until Phase 4, proportionate for web, future Android, and
   desktop clients?
4. Are opaque IDs and strict `v1` failures appropriate before choosing the
   offline/cloud ID format?
5. Is the retained/wrapped/replaced split sound enough to begin the shared
   React application?

Decision: accepted. The user confirmed the revised direction and authorized
Phase 3.
