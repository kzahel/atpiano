# 013 — Hybrid Product Migration Master Tracker

Topic: multi-tenant-hybrid-service-architecture

Status: accepted master plan on 2026-07-26; Phases 1 and 2 are complete, R2
is accepted, and Phase 3 implementation is complete pending mandatory R3
interaction review. This document tracks the staged migration program and
its human review gates. Each phase must create one or more smaller numbered
tacticals before implementation.

## Outcome

Build the accepted hosted-plus-Tauri product architecture without turning the
current v1 MVP or v2 corrected-note workbench into an in-place rewrite.

The new product will methodically establish:

- versioned domain and wire contracts;
- a shared React/TypeScript/Vite application;
- framework-independent Python application services;
- hosted and desktop implementations of one runtime-provider boundary;
- local-only, cloud, and later explicitly synced workspace modes;
- multi-user cloud accounts and workspaces;
- isolated model and score workers; and
- production-grade security, observability, artifacts, and recovery behavior.

The current applications are reference implementations and regression oracles.
Their frontend and HTTP composition can be superseded, but their proven
sample-clock rules, inference behavior, fixtures, score pipeline, artifacts,
and user-visible semantics must not be casually re-created from memory.

The first major hold is **before Phase 5**. At that point the user must be able
to run and review the basic application through the new shared frontend and
new Python application boundary, including deterministic replay and physical
microphone use. Tauri work does not begin until that review is accepted.

## Role Of This Tactical

This is a master tracker, not a single implementation slice. It owns:

- phase order and dependency boundaries;
- the definition of each phase's exit evidence;
- mandatory human-review and explicit-hold points;
- links to the bounded tactical and commit series for each phase;
- cross-phase compatibility requirements; and
- a compact current status.

It does not own detailed file lists, migrations, implementation tasks, or a
phase's execution record. Each bounded child tactical must state its exact
scope, entry conditions, acceptance tests, fallback behavior, and exclusions.
Completed child tacticals remain historical evidence; the accepted system
direction stays in
[`multi-tenant-hybrid-service-architecture.md`](../topics/multi-tenant-hybrid-service-architecture.md).

Update the status table when a child tactical opens or completes. Do not mark
a phase complete from code presence alone; attach its test evidence, review
result, and commit range.

## Program Status

| Phase | Status | Bounded tactical | Human gate |
| --- | --- | --- | --- |
| 1. Freeze and characterize | Complete (`3aabcda^..0bca270`) | [`014`](014-freeze-migration-baseline.md) | R1 accepted; no ambiguity |
| 2. Contracts and structure | Complete (`e2c2b9d^..9f8dd16`) | [`015`](015-contracts-and-structure.md) | R2 accepted 2026-07-26 |
| 3. Shared React application | In progress | [`016`](016-shared-react-application.md) | **Required interaction review** |
| 4. Python application core | Not started | Not created | **Required parity review; hold before Phase 5** |
| 5. Early Tauri skeleton | Blocked by Phase 4 approval | Not created | Required desktop-boundary review |
| 6. Complete local desktop | Blocked by Phase 5 | Not created | Required daily-use review |
| 7. Hosted service | Blocked by Phase 6 | Not created | Required hosted and tenancy review |
| 8. Collaboration, distribution, and limited sync | Blocked by Phase 7 | Not created | Separate release and sync reviews |

“Blocked” here describes planned sequencing, not a technical failure. The
master tracker itself does not authorize work past a required human gate.

## Migration Strategy

Use vertical walking skeletons, not a foundation-first rewrite.

Every phase should leave one narrow path executable from a real source or
deterministic fixture through the layers it introduces. Scaffolding without a
running consumer is temporary and must not spread across several phases.

The general replacement path is:

```text
existing v1 and v2
  reference behavior + regression evidence
               |
               v
versioned domain and runtime contracts
               |
               v
shared React application
               |
               v
framework-independent Python core
        /                     \
       v                       v
Tauri/local adapter       hosted adapter
       \                       /
        +---- same artifacts --+
```

Reuse code when it already has a coherent, tested responsibility. Wrap and
extract proven transcription behavior before changing it. Replace code whose
main purpose is proof-of-concept composition, implicit global state, or
framework coupling. Do not migrate the current frontend line by line merely
to preserve its file structure.

## Global Invariants

Every child tactical must preserve:

1. The v1 `workbench` and current v2 `workbench-v2` remain runnable until a
   separately approved retirement decision.
2. Existing session directories and exports remain readable.
3. Golden WAV and MIDI fixtures exercise the same session engine as live
   capture, not a test-only transcription shortcut.
4. The source audio sample clock remains authoritative across all new
   adapters.
5. Session, capture, job, and artifact targets are explicit IDs rather than
   process-global current selections.
6. The new frontend depends on a runtime-provider interface, not directly on
   FastAPI endpoints, Tauri commands, or filesystem paths.
7. Python domain and application services do not depend on FastAPI, Tauri, a
   browser, or a specific database.
8. Hosted and local runtime implementations emit the same versioned domain
   products and errors.
9. Models do not load in the hosted stateless API or the Tauri Rust shell.
10. No phase distributes or publicly operates MIDI2ScoreTransformer while its
    license remains unresolved.
11. Each commit keeps relevant deterministic regression lanes green; manual
    microphone review supplements rather than replaces replay.
12. A human gate is resolved by an explicit accepted result or an explicit
    documented revision. Silence is not approval.

## Review Philosophy

Human review is most valuable at decisions that are expensive to reverse but
cannot be judged fully by tests.

There are three reviews before Phase 5:

- **Structure review after Phase 2:** checks names, dependency direction,
  repository organization, public types, and responsibility boundaries before
  substantial code moves.
- **Interaction review after Phase 3:** checks the new application's controls,
  session model, visual hierarchy, terminology, and overall feel while the
  frontend remains cheap to reshape.
- **Parity review after Phase 4:** checks that real basic application behavior
  survived the new frontend and backend boundaries before a desktop shell adds
  another layer.

These reviews should be small and concrete. Do not ask the user to review a
large abstract diff without a map, or an unfinished page without specifying
which behaviors are intentional.

## Phase 1 — Freeze And Characterize The Existing Baseline

### Purpose

Turn the current applications into reliable oracles before building their
replacement. This phase adds evidence and tests, not a new product shell.

### Work

- Record exact development commands, optional dependency groups, model
  manifests, ignored runtime requirements, and known platform constraints.
- Characterize v1 and v2 startup, replay, microphone, Stop, restart recovery,
  session creation, event reads, horizons, exports, and score snapshots.
- Pin the aligned musical WAV/MIDI fixture and retained recording manifests,
  including hashes and generation commands.
- Capture normalized outputs and bounded comparison tolerances rather than
  brittle screenshots or serialized implementation details.
- Add contract tests for current route payloads that will feed the first
  compatibility runtime.
- Record current UI terminology and the user-visible behavior that is meant to
  survive, separately from known proof-of-concept limitations.
- Establish one command or small command set that produces the migration
  regression report.

### Exit evidence

- v1 and v2 baseline commands pass from a documented clean environment;
- the golden musical replay produces recorded normalized event, horizon,
  export, and score evidence;
- session and route characterization tests fail on meaningful contract drift;
- microphone smoke instructions are short and reproducible;
- known flaky, machine-dependent, licensed, or manual lanes are named; and
- no baseline is described as ground truth beyond what its evidence supports.

### Review checkpoint R1

R1 is normally an evidence handoff rather than a hard stop. Present:

- a one-page behavior inventory;
- the exact regression command;
- meaningful mismatches or ambiguities discovered; and
- anything proposed for deliberate non-parity.

Pause for user resolution only if the characterization exposes an ambiguous
product behavior or something currently useful that the migration would drop.

## Phase 2 — Establish Contracts And Code Structure

### Purpose

Create the vocabulary and dependency seams that the shared frontend, local
runtime, Tauri sidecar, and hosted service will all use.

### Work

- Define versioned user, workspace, membership, session, capture,
  transcription-run, event-revision, horizon, artifact, score-snapshot, job,
  provenance, and error schemas at the detail required by the next phases.
- Define the sample-indexed PCM envelope and capture state vocabulary without
  changing existing inference behavior.
- Define the TypeScript `AtpianoRuntime` boundary, subscriptions, cancellation,
  late-response rules, and capability discovery.
- Establish Pydantic/OpenAPI generation of a checked TypeScript client.
- Introduce explicit local session catalog, selected-versus-active semantics,
  session-addressed backend reads, and capture-coordinator boundaries from
  [`session-workspace-management.md`](../topics/session-workspace-management.md).
- Propose and create the smallest useful repository/package structure with
  enforced dependency directions.
- Add contract fixtures usable by Python and TypeScript tests.
- Retain compatibility adapters so the current v2 application remains
  runnable while new consumers appear.

### Structural rules

The precise filenames belong to the child tactical, but the dependency
direction must be recognizable:

```text
domain schemas and value types
             ^
             |
application services and ports
             ^
             |
FastAPI / local persistence / worker adapters

shared React components
             ^
             |
AtpianoRuntime interface
       ^             ^
       |             |
hosted adapter   local/fixture adapter
```

Framework adapters may depend inward. Domain and application modules may not
depend outward. Generated types have one source schema and a reproducible
generation command.

Do not model every possible future billing, sharing, sync, or deployment
feature. Types become durable when the next executable slice consumes them.

### Exit evidence

- representative domain objects serialize and validate identically across
  Python and TypeScript;
- incompatible schema and protocol versions fail explicitly;
- the runtime interface supports fixture replay, session listing, event
  subscription, Stop, artifacts, and score-job state without platform tests
  inside UI components;
- session selection cannot retarget capture or a job;
- dependency checks prevent domain/application imports from reaching
  framework adapters; and
- a proposed repository tree and responsibility map match the actual code.

### Human review gate R2 — Structure and contracts

This is the first mandatory hold. The review packet includes:

- a compact directory tree;
- a dependency-direction diagram;
- the runtime interface;
- one workspace, session, capture, event revision, job, artifact, and error
  example;
- a list of public names likely to survive into UI or APIs;
- generated-client workflow and compatibility policy; and
- explicit code retained, wrapped, or expected to be replaced.

The user reviews whether the structure feels proportionate, the vocabulary
matches the product, and the abstraction boundaries reflect the intended
hosted-plus-desktop shape. Resolve this review before beginning the broad
React migration.

## Phase 3 — Build The Shared React Application

### Purpose

Create the new shared user application while reusing the current backend
behavior through a compatibility/local runtime. This makes product and
frontend decisions reviewable before the Python backend is substantially
rearranged.

### Work

- Scaffold a separate React, TypeScript, and Vite application.
- Add TanStack Query for runtime-owned state and a small Zustand store for
  client-owned capture and view state.
- Implement the explicit capture state machine.
- Port the useful v2 controls and independently toggleable timeline, keyboard,
  and score views without turning migration into an unrelated redesign.
- Add explicit New, session history, selected-versus-active identity, and
  recoverable Delete behavior over the Phase 2 local session contracts.
- Implement fixture and current-local-backend runtime adapters.
- Preserve deterministic replay, microphone capture, Stop, live revisions,
  committed results, downloads, and score snapshot behavior.
- Preserve accessibility, useful status/error reporting, and narrow-screen
  behavior at least at the current level.
- Keep the new application independently runnable from v1 and v2.

### Exit evidence

- unit and component tests cover capture transitions, selection changes, late
  responses, view toggles, and recoverable errors;
- the golden WAV runs through the new UI and existing local engine;
- displayed and exported normalized results match the Phase 1 baseline within
  declared tolerances;
- a failed score dependency does not break capture or session review;
- current v1 and v2 still pass and remain independently launchable; and
- the new frontend contains no direct Tauri dependency and no scattered
  direct endpoint calls outside its runtime adapter.

### Human review gate R3 — Interaction and frontend taste

This is a mandatory interactive review while visual and state choices remain
cheap to change. Supply:

- one command to launch the new application with deterministic replay;
- one command or obvious action for microphone use;
- a short intentional-differences list;
- the New/history/delete flow;
- the timeline, keyboard, and score views;
- visible capture, selected-session, job, and failure states; and
- screenshots only as orientation, not as a substitute for the live app.

The user reviews terminology, visual hierarchy, control grouping, session
mental model, visualization usefulness, and whether the new app still feels
like the useful proof of concept rather than a generic admin interface.
Resolve substantive UX feedback before moving the same assumptions into the
new Python application boundary.

Phase 3 reached this hold on 2026-07-26. The launch commands, interaction map,
intentional differences, golden evidence, screenshots, and decision request
are in
[`r3-interaction-review.md`](../r3-interaction-review.md). Do not open Phase 4
until the user explicitly accepts R3.

## Phase 4 — Extract The Framework-Independent Python Application Core

### Purpose

Replace proof-of-concept server composition with a clean Python application
boundary while keeping Phase 3 behavior and its frontend runtime contract
stable.

### Work

- Extract session catalog, capture coordination, historical reads,
  transcription-run coordination, score jobs, artifact publication, and
  provenance into framework-independent application services.
- Keep model adapters, source-clock scheduling, reconciliation, score
  selection, and persistence evidence reusable rather than reimplementing
  them.
- Put filesystem/SQLite, FastAPI, replay CLI, microphone transport, and model
  process details behind explicit ports and adapters.
- Replace server-global current-session targeting with explicit IDs.
- Make local persistence restartable, recoverable, and session-addressed.
- Preserve bounded capture and job concurrency, cancellation, timeouts, and
  error reason codes.
- Have the shared React application's local runtime use this new boundary.
- Keep compatibility shims only where v1 or v2 still requires them, and name
  their removal condition.

### Exit evidence

- the same application services run from tests, replay CLI, and the local
  FastAPI adapter;
- domain and application tests do not start an HTTP server;
- the golden fixture matches Phase 1 normalized outputs and artifacts;
- long-loop replay preserves bounded memory and monotonic horizons;
- restart, stale capture, failed worker, partial artifact, and busy-score
  recovery tests pass;
- new frontend replay, microphone, Stop, history, deletion, export, and score
  behavior pass against the extracted core; and
- the current v1 and v2 applications still pass their regression lanes.

### Human review gate R4 — Basic application parity

This is the required hold before Phase 5. Provide a compact review build and:

- one launch command;
- deterministic musical replay on demand;
- physical microphone Start and Stop;
- explicit New and session history;
- timeline, keyboard, and score review;
- MIDI, JSONL, WAV where applicable, and score artifact access;
- a comparison report against the frozen baseline;
- known differences and deferred polish;
- a code map showing the React/runtime/application/adapter boundaries; and
- the exact tests and commit series for Phases 1–4.

The user decides whether basic functionality is intact and whether the new
application and code structure are a sound foundation. Do not create or begin
the Phase 5 Tauri tactical until this review receives explicit approval.

## Phase 5 — Prove The Tauri And Sidecar Boundary Early

### Purpose

Validate that the shared application and Python core are genuinely
platform-neutral before cloud-specific infrastructure expands.

This is a walking skeleton, not the polished desktop product.

### Work

- Package the Phase 3 frontend in a minimal Tauri 2 shell.
- Bundle or locate a versioned Python sidecar without embedding Python logic
  in Rust.
- Add per-launch local IPC authentication and a compatibility handshake.
- Start, monitor, and stop the sidecar from the thin Rust shell.
- List local sessions and run the golden WAV through the same application core.
- Stream progress, event revisions, horizons, and failure states to the shared
  frontend through the local runtime adapter.
- Establish capability-scoped filesystem and process access.
- Prove that no privileged webview loads remote application content.
- Record app, schema, sidecar, model adapter, checkpoint, and device versions.

Auto-update, a final installer, account login, cloud sync, Windows support,
and every score dependency are excluded unless required for the boundary
proof.

### Exit evidence

- a development Tauri build launches and authenticates the sidecar;
- incompatible protocol or model-pack metadata fails before capture;
- replay results match the direct local path;
- sidecar crash and app close have explicit cleanup and recovery behavior;
- the application can run without a hosted API; and
- the React component tree contains no platform fork for ordinary product
  behavior.

### Human review gate R5

Review launch behavior, replay, local-session access, visible failure handling,
and the proposed privilege boundary. Confirm that the desktop application
feels like the same product rather than a separate port.

## Phase 6 — Complete The Local Desktop Vertical Slice

### Purpose

Make the desktop application useful as the first complete new-world local
product.

### Work

- Complete microphone capture, replay, Stop, history, deletion, artifacts,
  score jobs where licensed, and local settings.
- Add SQLite catalog and durable local artifact layout with repair/re-indexing.
- Add model-pack acquisition, signed manifests, compatibility policy, and
  visible storage requirements.
- Add signed application/sidecar update infrastructure and rollback behavior.
- Add local diagnostic bundles and privacy-aware telemetry controls.
- Validate network-disabled operation after installation and model acquisition.
- Package macOS arm64 first; open separate platform tacticals later.

### Exit evidence and review R6

The user can install or launch the desktop build, disconnect the network,
record or replay, stop, review history, render available scores, export
artifacts, restart, and recover prior sessions. R6 is a daily-use product
review before hosted product complexity becomes the main focus.

## Phase 7 — Build The Hosted Service Vertical Slice

### Purpose

Implement the zero-install, collaborative service using the same frontend and
domain products proven locally.

### Work

- Add managed OIDC integration, users, cloud workspaces, memberships, and
  roles.
- Add FastAPI service modules, PostgreSQL, row-level-security defense, object
  storage, audit events, and signed artifact access.
- Extract preview, commit, and score execution into versioned worker processes.
- Add authenticated capture leases and binary PCM WebSocket ingest.
- Add bounded routing, backpressure, durable audio segmentation, revisions,
  horizons, and full stage-level latency instrumentation.
- Deliver one browser microphone-to-cloud-session path.
- Prove concurrent sessions in one workspace and one writer per session.

### Exit evidence and review R7

R7 reviews a hosted account, workspace invitation or test membership, separate
simultaneous sessions, historical review, artifacts, failures, authorization,
and latency evidence. It also compares hosted normalized products with the
same direct and desktop fixture.

## Phase 8 — Collaboration, Distribution, And Limited Sync

### Purpose

Harden the two independently useful products, then add carefully bounded
interoperation.

### Work

- Complete hosted invitation, role-management, retention, quota, and
  operational controls.
- Complete supported desktop distribution, signed updates, and selected
  additional platform lanes.
- Add explicit, privacy-labelled local-session upload to a chosen cloud
  workspace.
- Use stable IDs, hashes, idempotency keys, resumable transfer, and atomic
  publication.
- Reconcile only a declared set of mutable metadata.
- Add tombstones and explicit local/cloud identity mapping.
- Consider cloud-to-local offline review only after upload is reliable.

General bidirectional database sync, live cross-device capture continuation,
and silent audio upload remain outside the first sync slice.

Release and sync receive separate tacticals and human review gates. A public
release cannot include an unresolved third-party dependency.

## Phase Tactical Template

Every child tactical should include:

```text
Master phase:
Topic:
Status:
Entry evidence:
User-visible outcome:
Invariants:
Exact implementation scope:
Explicit exclusions:
Migration and compatibility:
Automated validation:
Manual validation:
Human review packet:
Rollback or disable path:
Execution record:
```

Commits use the relevant topic trailer and keep the master phase visible in
the tactical and pull-request or commit-series summary. The master tracker
links the child tactical and final commit range when complete.

## Cross-Phase Test Matrix

The matrix grows with the program:

| Behavior | Existing v1/v2 | New local web | Tauri | Hosted |
| --- | --- | --- | --- | --- |
| Golden musical WAV replay | Required | Phase 3 | Phase 5 | Phase 7 |
| Golden MIDI/reference comparison | Required | Phase 3 | Phase 5 | Phase 7 |
| Physical microphone | Required smoke | Phase 3/4 | Phase 6 | Phase 7 |
| Source-clock and horizon evidence | Required | Phase 3/4 | Phase 5 | Phase 7 |
| Session New/history/delete | Reference gap | Phase 3/4 | Phase 6 | Phase 7 |
| Committed MIDI/JSONL | Required | Phase 3/4 | Phase 6 | Phase 7 |
| Score snapshot | Required internal | Phase 3/4 internal | Licensed path only | Licensed path only |
| Restart recovery | Required | Phase 4 | Phase 6 | Phase 7 |
| Network-disabled operation | Not a claim | Not a claim | Phase 6 | Not applicable |
| Multiple users and sessions | Not a claim | Not a claim | Cloud mode later | Phase 7 |
| Full latency-stage report | Partial | Phase 4 | Phase 6 | Phase 7 |

“Required” means the existing lane remains green; it does not imply that all
current proof-of-concept behavior becomes a permanent product requirement.

## Drift And Stop Conditions

Stop the active child tactical and update the relevant topic before:

- deleting, renaming, or replacing the supported v1 or v2 commands;
- changing sample-clock, horizon, revision, or commit semantics;
- adding platform checks throughout React components instead of the runtime
  boundary;
- making FastAPI, PostgreSQL, Tauri, or SQLite a dependency of domain logic;
- changing a public domain term after it passes R2;
- adding a TypeScript backend or additional service boundary;
- moving raw PCM through PostgreSQL or a general job queue;
- beginning Tauri work without R4 approval;
- beginning general sync before local and cloud products work independently;
- uploading local audio implicitly;
- publicly operating or distributing a dependency without resolved rights; or
- combining a framework migration with model-quality retuning.

The appropriate response is a small topic or tactical revision with the new
evidence and tradeoff, not an undocumented exception.

## Immediate Next Action

Do not scaffold the new product from this master document alone. When
implementation is authorized, create the Phase 1 bounded tactical for baseline
characterization. Its final handoff proposes the exact Phase 2 tactical and
identifies any current behavior that needs a product decision before it is
encoded as a durable contract.
