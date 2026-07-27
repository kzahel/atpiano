# 030 — Early Tauri And Sidecar Boundary

Master phase: 5. Early Tauri skeleton

Topic: multi-tenant-hybrid-service-architecture

Status: **authorized and active on 2026-07-27 after accepted R4.** This
tactical ends at R5. It does not open the complete local-desktop Phase 6.

## Outcome

Produce one unsigned macOS arm64 development application that packages the
accepted React workspace, launches and authenticates a versioned Python
sidecar, lists local sessions, and runs the real golden musical replay through
the Phase 4 application core.

The R5 artifact must be self-contained for that bounded path. It cannot depend
on a system Python, the repository checkout, the development virtual
environment, CUDA, the internal score runtime, or hosted APIs. This proves
the desktop/process/security boundary; it is not the final signed installer
or daily-use desktop product.

## Entry Evidence

- Phases 1 through 4 are complete.
- R4 accepted the shared application, extracted Python core, and verified-MP3
  storage default on 2026-07-27.
- The React component tree depends on `AtpianoRuntime`; local HTTP details are
  contained in the runtime adapter.
- Replay and microphone already share the sample-indexed application capture
  service.
- The 42-second golden musical fixture, normalized event products, duration
  evidence, and migration regression are reproducible.
- The current machine is macOS arm64 with Xcode, Rust, Node, Python 3.10, and
  the real Basic Pitch and Transkun paths validated.

## Frozen Decisions

### Platform and scope

- Phase 5 targets **macOS arm64 only**.
- Use Tauri 2 and the existing Vite production build.
- Build an unsigned development `.app`; signing, notarization, DMG, updater,
  and public installation belong to Phase 6.
- Windows receives a separate later tactical. Linux packaging remains later.
- The frontend receives one desktop runtime adapter; product components do
  not branch on Tauri.

### Sidecar and IPC

- Rust is a thin lifecycle and security owner. Python retains sessions,
  replay, inference, reconciliation, artifacts, and storage.
- Rust generates at least 256 bits of random secret material per launch and
  supplies it to the child through inherited environment, never process
  arguments, URLs, frontend logs, or retained files.
- The sidecar binds an ephemeral loopback port and requires the secret on
  every API, artifact, and WebSocket operation.
- HTTP uses a bearer authorization header. WebSocket authentication uses one
  exact per-launch subprotocol value and the server echoes only that value.
- Only the bundled Tauri origin receives cross-origin access. Wildcard CORS
  and unauthenticated loopback access are forbidden.
- Before the frontend can use the runtime, Rust validates a versioned ready
  document and the frontend validates an authenticated handshake document.
- App close terminates the child. Unexpected sidecar exit becomes one visible
  bounded failure and preserves completed session artifacts.

### Runtime and models

- Bundle a relocatable CPython 3.10 arm64 runtime plus the locked runtime
  dependencies needed by application-core replay.
- Use the CPU execution backend for R5. Do not include CUDA, NVIDIA, ROCm,
  Windows, or Linux binaries.
- Keep model identity in a separate manifest. The R5 pack contains the pinned
  Basic Pitch and Transkun assets needed by the golden replay, with hashes,
  versions, adapter IDs, platform, architecture, and device compatibility.
- The internal MIDI2ScoreTransformer runtime and checkpoint are excluded
  because their distribution rights remain unresolved.
- Test and development dependencies are excluded from the staged runtime.
- Bundle the media tools required by verified MP3 finalization or fail the
  self-contained gate. Merely finding Homebrew tools during validation does
  not satisfy R5.

### Bundle-size policy

Smallness is measured, not asserted. Retain a machine-readable inventory with:

- compressed and installed bytes by frontend, Rust shell, Python runtime,
  Python packages, native libraries, media tools, and model pack;
- the largest files and packages;
- Mach-O architectures and external dynamic-library references;
- an explicit forbidden-dependency scan for CUDA, NVIDIA, ROCm, test, and
  score-runtime material; and
- cold sidecar-ready, model-load, replay-settlement, and app-close timing.

Phase 5 may retain a large but explained CPU bundle. Optimization that changes
a model runtime, checkpoint, numerical path, or replay output requires a
separate parity result and cannot be hidden inside packaging cleanup.

## Exact Implementation Scope

### 1. Desktop sidecar surface

Add a dedicated Python launch surface that:

- validates its inherited token and expected desktop/protocol versions;
- resolves only declared workspace, fixture, model-pack, and media-tool
  roots;
- creates the existing corrected-workbench composition on `127.0.0.1:0`;
- emits exactly one bounded JSON ready record without the token or private
  workspace path;
- serves an authenticated desktop handshake;
- exposes the existing versioned local APIs and replay action;
- does not serve the React application or accept a public origin; and
- shuts down models, score jobs, and server resources on EOF, signal, or
  parent termination where the operating system permits.

The handshake records:

- schema and protocol versions;
- sidecar and application versions;
- platform and architecture;
- Python and execution backend;
- model-pack ID, manifest hash, model/checkpoint hashes, and adapter versions;
- storage policy;
- supported runtime capabilities; and
- compatibility with the shell's declared ranges.

### 2. Authenticated local transport

Extend the existing local HTTP composition only through optional desktop
configuration:

- ordinary `workbench-v2` and `workbench-v3` behavior remains unchanged;
- desktop mode rejects absent or wrong bearer credentials;
- desktop WebSocket upgrade rejects absent or wrong subprotocol credentials;
- desktop responses use exact-origin CORS and bounded preflight behavior;
- bearer values never appear in errors, ready records, logs, artifact URLs,
  manifests, or diagnostics; and
- authentication tests use a real ephemeral server.

### 3. Shared frontend desktop runtime

Add a desktop bootstrap and runtime adapter that:

- detects Tauri only at composition;
- invokes one narrow Rust bootstrap command;
- validates the desktop configuration and authenticated handshake;
- supplies the sidecar base URL and bearer material only to the runtime
  adapter;
- preserves the existing `AtpianoRuntime` interface;
- uses authenticated fetches and WebSocket subprotocols;
- materializes authenticated artifact responses as bounded blob URLs for the
  R5 review path; and
- renders one visible bootstrap or sidecar failure without loading remote
  content.

No React product component imports Tauri APIs.

### 4. Thin Tauri shell

Add a minimal Tauri 2 project that:

- packages `app/dist`;
- exposes one bootstrap command rather than a generic shell or filesystem
  command;
- generates the launch token with operating-system randomness;
- starts one packaged Python runtime and sidecar module;
- parses one size-bounded ready record with a startup timeout;
- rejects incompatible schema, protocol, platform, architecture, or model
  pack before returning configuration to JavaScript;
- monitors sidecar exit and emits a bounded failure event;
- terminates and reaps the child on app exit; and
- grants only the core window/event capability needed for this slice.

The production webview uses bundled assets and a restrictive content security
policy. It cannot navigate privileged content to a remote origin.

### 5. Self-contained staging

Add reproducible scripts that:

- copy the pinned standalone CPython distribution rather than the developer
  virtual environment;
- install the locked application runtime without dev or score extras;
- stage the separately manifested model files;
- stage and relocate the required arm64 media binaries and their non-system
  libraries;
- generate hashes, versions, licenses, architecture evidence, and byte
  accounting;
- reject symlinks or dynamic-library references that escape the bundle;
- build the Vite frontend, Rust shell, and `.app`; and
- validate the final artifact from a directory outside the repository with
  Python-related environment variables cleared.

Generated runtimes, model packs, inventories, and `.app` artifacts remain
ignored under `results/` or ignored Tauri resource staging. Manifests and
scripts are tracked.

## Automated Acceptance

### Python and transport

- Handshake and ready schemas reject unsupported versions and model hashes.
- Missing/wrong HTTP credentials return 401; correct credentials preserve the
  current versioned API products.
- Missing/wrong WebSocket credentials fail before capture ownership changes.
- Exact desktop-origin preflight passes; wildcard or foreign origins fail.
- Token values are absent from captured logs, errors, manifests, ready
  records, and artifact URLs.
- Sidecar SIGTERM and parent EOF close the server and model workers.

### Rust and frontend

- Rust unit tests cover compatibility, size bounds, ready parsing, duplicate
  bootstrap, unexpected exit, and cleanup state.
- TypeScript tests cover Tauri detection, handshake validation, authenticated
  HTTP, authenticated WebSocket construction, and visible bootstrap failure.
- Dependency checks reject Tauri imports outside desktop composition/runtime
  files.
- `cargo fmt`, `cargo test`, `cargo clippy -- -D warnings`, app typecheck,
  frontend tests, production build, contracts, Ruff, and Python tests pass.

### Bundle and replay

- The final `.app` launches without system Python, repository access,
  `.venv`, `uv`, Homebrew media binaries, or network access.
- The sidecar reports macOS arm64 and CPU; every packaged Mach-O is arm64 or
  universal with arm64 support.
- No CUDA, NVIDIA, ROCm, internal score runtime, checkpoint, dev package, or
  anonymous cache appears in the bundle.
- The packaged model manifest hashes match the files used at inference.
- The golden replay completes through the packaged sidecar with monotonic
  source, provisional, and commit horizons.
- Normalized replay products and retained artifacts match the direct local
  path within the existing Phase 1/3 tolerances.
- Verified MP3 publication succeeds and raw WAV retires.
- Killing the sidecar leaves completed sessions readable; a new app launch
  lists them.
- The inventory reconciles every bundled byte and records the ten largest
  contributors.

## Human Review Gate R5

Provide:

- one `.app` launch action and one terminal fallback command;
- a startup view that reaches the existing workspace without hosted login;
- the bundled golden replay, visible progress, final timeline, keyboard,
  artifacts, and synchronized audio;
- local history surviving app restart;
- one incompatible-handshake demonstration;
- one sidecar-crash and visible-recovery demonstration;
- the exact privilege/capability map;
- the bundle inventory and size explanation;
- known gaps and the exact test/commit report; and
- a code map showing React, desktop runtime, Rust shell, sidecar, application
  core, local adapters, and models.

The user decides whether the launch experience, same-product behavior,
process/security boundary, and bundle direction are sound. Do not open the
complete local desktop Phase 6 until R5 is explicitly accepted.

## Explicit Exclusions

- No final signing, notarization, DMG, updater, rollback channel, or public
  distribution.
- No Windows, Linux, Intel Mac, iOS, or Android packaging.
- No microphone parity, capture-device packaging, settings UI, model-pack
  download manager, or daily-use offline promise.
- No account, cloud workspace, hosted API, collaboration, upload, or sync.
- No SQLite catalog migration beyond the current local session adapter.
- No MIDI2ScoreTransformer or unresolved score checkpoint.
- No CUDA, NVIDIA, ROCm, or speculative accelerator bundle.
- No transcription, decoder, reconciliation, score-quality, or React visual
  redesign.
- No permanent packaging abstraction for every future platform.

## Rollback

The Tauri project, desktop runtime, sidecar launch surface, and staging scripts
are additive. The existing `workbench-v3`, public service, local workspace,
contracts, and historical sessions remain independently runnable.

Desktop authentication is optional server composition used only by the
sidecar. Removing the Tauri slice requires no session migration. Generated
bundles and staging directories can be discarded without touching user
workspaces.

## Planned Commit Slices

1. Open Phase 5 with this bounded tactical.
2. Add the authenticated sidecar handshake and real transport tests.
3. Add the desktop runtime adapter and bootstrap failure surface.
4. Add the thin Tauri lifecycle/security shell.
5. Add standalone runtime, model-pack, and media-tool staging.
6. Build the `.app` and run packaged real replay, failure, security, and size
   validation.
7. Prepare R5, update living docs, and stop for explicit review.

## Execution Record

No implementation commits yet.
