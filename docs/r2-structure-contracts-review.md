# R2 Structure And Contracts Review

Status: awaiting required human review on 2026-07-26.

This packet is the mandatory hold after Phase 2. It reviews vocabulary,
dependency direction, generated contracts, and the provider boundary before
the broad React migration. It does not ask for approval of a visual design or
claim that hosted, Tauri, or framework-independent application services
already exist.

## Actual Repository Shape

```text
contracts/
  fixtures/v1/product-examples.json    shared successful wire examples
  openapi/atpiano-product-v1.json      generated public HTTP contract

product/
  package.json                         pinned TypeScript tooling and checks
  src/generated/schema.ts              generated wire and HTTP path types
  src/http-client.ts                   typed openapi-fetch composition
  src/runtime/atpiano-runtime.ts       hand-owned behavioral provider boundary
  src/runtime/fixture-runtime.ts       deterministic executable provider
  tests/                               cross-language and provider tests

src/atpiano/product/
  domain/schemas.py                    Pydantic source of product vocabulary
  application/ports.py                 inward use-case port protocols
  adapters/local_sessions.py           existing-v2 compatibility adapter
  contract_generation.py               OpenAPI and TypeScript generation

src/atpiano/corrected_workbench.py     retained v2 composition and additive
                                      /api/product/v1 adapter routes
tests/
  test_product_schemas.py              semantic Python contract checks
  test_product_fixtures.py             shared-byte Python validation
  test_contract_generation.py          deterministic generation and drift
  test_local_product_sessions.py       catalog/path/trash/dependency checks
  test_product_routes.py               explicit target and compatibility HTTP
```

The current `src/atpiano/web` and `src/atpiano/web_v2` applications are
unchanged. React does not exist yet.

## Dependency Direction

```text
Pydantic product domain
          ^
          |
application port protocols
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

Python AST checks prevent domain and application modules from importing:

- current corrected-session implementation modules;
- local adapter modules;
- HTTP server modules; or
- filesystem APIs.

The adapter may depend inward on product contracts and outward on existing v2
artifacts. `corrected_workbench.py` remains an outer compatibility
composition. Framework-independent capture, transcription, score, and
persistence services remain Phase 4 work.

## Runtime Provider

The hand-owned interface is
[`atpiano-runtime.ts`](../product/src/runtime/atpiano-runtime.ts). It covers:

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
[`fixture-runtime.ts`](../product/src/runtime/fixture-runtime.ts) already
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

## Representative Products

The exact shared bytes are
[`product-examples.json`](../contracts/fixtures/v1/product-examples.json).
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
reject `atpiano.product.v2` where `atpiano.product.v1` is required. Pydantic
also enforces semantic relationships that JSON Schema cannot compare
directly, including offset-after-onset, horizon-before-audio-head,
immediately-prior revision ownership, lifecycle completion, and PCM byte
counts.

## Generation And Compatibility

Install the pinned TypeScript tools, generate, and check drift with:

```text
npm ci --prefix product
uv run atpiano generate-contracts
uv run atpiano generate-contracts --check
npm run typecheck --prefix product
npm test --prefix product
```

Pydantic is the source. The OpenAPI document and
`product/src/generated/schema.ts` are machine-owned. The runtime interface and
typed HTTP composition are hand-owned because they define behavior rather
than serialization.

`atpiano.product.v1` and `atpiano.pcm.v1` fail closed on incompatible
versions. Strict product objects reject unknown fields. Additive changes may
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
`/api/product/v1` and always name the target. Tests score and download an
older session while proving the legacy current session remains the newer one.

## Retained, Wrapped, Generated, And Replaced Later

Retained:

- v1 and v2 commands and frontends;
- source-clock capture, inference, reconciliation, horizons, fixtures,
  segmented storage, exports, and score snapshots;
- existing sessions and compatibility routes.

Wrapped:

- v2 manifests as a bounded newest-first local catalog;
- event indexes as explicit product event pages;
- current exports and score files as checksummed artifact products;
- the existing score runner as a job frozen to session and commit horizon.

Generated:

- OpenAPI components and implemented ordinary HTTP paths;
- TypeScript wire and path types.

Expected to be replaced or thinned:

- server-global current-session composition;
- direct `ThreadingHTTPServer` use for the new product;
- framework-free product UI composition;
- compatibility aliases after retained clients no longer need them.

The transcription and score algorithms are retained behind later
application/worker boundaries, not re-created from these contracts.

## Validation Evidence

The implementation range is `e2c2b9d^..7fdc3d1`.

The final unattended report is ignored evidence at
`results/migration-regression/20260726T100824Z/report.json` and records:

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
3. Is the product/domain/application/adapter direction proportionate, or is a
   boundary premature or missing?
4. Are opaque IDs and strict `v1` failures appropriate before choosing the
   offline/cloud ID format?
5. Is the retained/wrapped/replaced split sound enough to begin the shared
   React application?

Phase 3 remains blocked until this packet receives explicit acceptance or a
documented revision.
