# 053 — Windows Desktop Release Lane

Topics: `public-desktop-release`, `windows-native-runtime-portability`,
`desktop-score-runtime-footprint`

Status: **implementation active as a prerequisite of the first binary
release.** The Python desktop identity/model-pack contracts now accept exactly
macOS arm64 and Windows x86_64 CPU pairings. The Tauri launcher and frontend
now carry exact resource, origin, package, and updater variants for both
targets. The native Windows x64 application core is established and the
universal score-support registry lock resolves for Windows x64. A complete
2.12 GB relocatable Windows x64 runtime, including the ordinary model pack,
pinned media payload, and publication-safe score support, now passes twice on
the testbed under x64-on-ARM64 emulation. No Tauri application package, signed
installer, packaged MIDI2Score result, or updater campaign exists.

## Goal

Add a signed, per-user Windows x86_64 CPU application to the same
`desktop-v0.1.0` proof-of-concept release as the notarized macOS arm64
application. Both packages must expose the same capture, import, review,
playback, export, user-acquired MIDI2Score, removal, and automatic-update
capabilities. Do not publish a macOS-only binary tag while this tactical is
incomplete.

The first Windows package uses an NSIS setup executable and Tauri's signed
updater artifact. It does not require an NVIDIA GPU, CUDA, WSL, a user-installed
Python, `uv`, Git, FFmpeg, or build toolchain. All model execution defaults to
CPU. CUDA and native Windows ARM64 are later optional lanes.

## Entry Evidence

- Native Windows x64 CPU execution already passes the locked ordinary and
  corrected environments, Basic Pitch ONNX inference, Transkun inference,
  production frontend, migration gate, storage validation, unpackaged replay,
  settlement, restart recovery, and artifact publication without WSL.
- Basic Pitch uses ONNX Runtime CPU on Windows. Transkun accepts CPU and already
  has a conservative after-Stop profile for slower hosts. MIDI2Score is
  explicitly CPU-only in Atpiano's adapter, but its Windows x64 support
  environment and retained score parity are not yet validated.
- The current desktop contract accepts only `macos`, `arm64`, and `cpu`.
  Resource discovery assumes an `.app`, staging includes macOS arm64 Python and
  media binaries, CI builds only `aarch64-apple-darwin`, and release validation
  intentionally rejects NSIS and `windows-x86_64`.
- The configured `~/code/machine-control` Windows target passed `target doctor`
  on 2026-08-23 with exact private identity, key-only PowerShell
  administration, an unlocked interactive desktop, resident control, UI
  Automation, capture, and input ready.
- That testbed is Windows 11 ARM64. The current lock has Windows x64 wheels for
  critical model packages such as Torch and ONNX Runtime but lacks a complete
  native Windows ARM64 stack. Windows 11 officially supports x64 user-mode app
  emulation, so the testbed can exercise the x64 installer and application.
  Every such result must be labeled x64-on-ARM64 emulation and must not be used
  as native x64 performance evidence.
- GitHub-hosted `windows-2025` runners are x64 and can own reproducible native
  x64 build, unit, staging, bundle, and signing checks. The existing physical
  x64 server result remains complementary runtime evidence; it is not the
  ordinary interactive desktop-control path for this tactical.

Relevant upstream contracts:

- [Tauri Windows installers](https://v2.tauri.app/distribute/windows-installer/)
  support NSIS setup executables and MSI packages. Use NSIS for the minimal
  first per-user lane.
- [Tauri Windows signing](https://v2.tauri.app/distribute/sign/windows/) supports
  importing an exportable PFX in GitHub Actions or a configured external
  signing provider.
- [Tauri updater](https://v2.tauri.app/plugin/updater/) supports signed Windows
  installers and `windows-x86_64` update metadata. Windows exits the
  application during installation, so sidecar shutdown must use the updater's
  before-exit boundary.
- [Microsoft's Windows-on-Arm documentation](https://learn.microsoft.com/windows/arm/apps-on-arm-x86-emulation)
  documents supported x86/x64 user-mode emulation and its limits.

## Frozen Product Boundaries

- Publish exactly `darwin-aarch64` and `windows-x86_64` for this proof of
  concept. Continue rejecting Linux, Intel macOS, and native Windows ARM64.
- Use the same app version, Tauri identifier, updater public key, product ID,
  endpoint, release tag, notice version, and acquisition-contract revision on
  both platforms.
- Keep CPU as the complete Windows feature baseline. Do not bundle CUDA or make
  an NVIDIA GPU a requirement.
- Use a per-user NSIS installation with no administrator requirement. Do not
  open an MSI, Microsoft Store, machine-wide install, or driver lane.
- Use Windows platform application-data/config directories for mutable sessions,
  acquisition receipts, model assets, caches, installation identity, and
  updater state. Never write them beside the installed executable.
- Ship no MIDI2ScoreTransformer repository or checkpoint. Tactical 052 owns
  the shared acknowledgement/acquisition behavior and exact upstream assets.
- Build the public Windows artifacts in GitHub Actions from tracked inputs.
  Local/testbed packages are development evidence, not publication artifacts.
- Do not publish either platform, activate production routing, or push the
  first tag until both platform jobs and the coordinated finalizer pass.

## Phase 1 — Generalize The Desktop Boundary

Replace macOS-only assumptions with explicit supported-platform variants while
keeping incompatible values fail-closed:

1. allow `windows` / `x86_64` / `cpu` in the model-pack, ready, and handshake
   schemas and retain exact platform matching;
2. resolve packaged resources through Tauri rather than a hard-coded `.app`
   layout;
3. express Python, sidecar, FFmpeg/FFprobe, model-pack, and score-support
   executables through one platform manifest with Windows `.exe` and DLL
   handling;
4. use platform application-data/config/cache paths and portable artifact
   separators;
5. supervise Windows process trees, readiness, bounded output, graceful stop,
   forced fallback, and orphan detection without POSIX signals or Bash;
6. keep the authenticated loopback address, bearer token, protocol versions,
   model hashes, and score capability contract unchanged; and
7. preserve the ordinary score-free startup when any optional score runtime is
   missing, incompatible, corrupt, or blocked.

Tests must inject platform/resource layouts rather than pretending to run a
Windows package on macOS. Existing macOS contract tests continue to pass.

## Phase 2 — Stage The Windows CPU Runtime

Construct a relocatable Windows x64 stage from exact tracked inputs:

- standalone CPython and locked production wheels;
- Basic Pitch's ONNX model and ONNX Runtime CPU;
- Transkun's CPU checkpoint/config and CPU Torch;
- the production React application;
- Windows x64 FFmpeg/FFprobe plus required shared libraries built under the
  accepted minimal LGPL media contract;
- the Windows x64 Python 3.11 MIDI2Score support layer from tactical 052, but
  no MIDI2ScoreTransformer source/checkpoint; and
- third-party notices, acquisition contract, component inventory, hashes, and
  corresponding media sources.

The stage must not depend on development-environment paths, registry-only
Python discovery, a checkout, user `PATH`, WSL, symlink privileges, CUDA DLLs,
or network access after optional model acquisition. Inventory every PE file,
DLL owner, package, model, and byte count. Scan for private paths, secrets,
debug payloads, caches, forbidden model bytes, and unexpected architectures.

Run deterministic packaged controls before opening UI work:

1. authenticated sidecar handshake and unauthenticated rejection;
2. Basic Pitch fixture inference;
3. CPU Transkun correction and complete settlement;
4. WAV/MP3 import, compact publication, playback, and export;
5. clean parent-EOF and explicit-shutdown process reaping;
6. external workspace persistence across package replacement; and
7. external acquired-score composition, MIDI2Score inference, MusicXML,
   alignment, and output parity with macOS retained evidence.

CPU throughput may select after-Stop correction. That is supported degradation,
not a feature failure, provided capture remains durable and completion is
truthfully reported.

## Phase 3 — Installer, WebView2, And Desktop Acceptance

Add a Windows-specific Tauri configuration that selects the NSIS target,
per-user install mode, updater artifacts, Windows icons/version metadata, and a
deliberate WebView2 strategy. The installer must either use an already
compatible WebView2 runtime or acquire Microsoft's bootstrapper visibly; the
Atpiano application itself must remain usable offline after installation and
optional score acquisition.

Use the common machine-control entry point for the Windows testbed:

```text
cd ~/code/machine-control
bin/machine-control inventory status
bin/machine-control --target windows target doctor
bin/machine-control --target windows workspace acquire --intent persistent
```

Use key-only PowerShell for files, processes, and deterministic commands. Use
target-resident application launch and UI Automation for the installed desktop
application; do not launch GUI applications through SSH session 0. Inspect UI
semantics before actions and use target-native capture/input only when WebView2
content is not exposed semantically.

The visible acceptance must cover:

- signed installer launch, install, Start-menu launch, ordinary quit, uninstall,
  and reinstall without unexpected elevation;
- loopback-only sidecar readiness, bounded startup failure, and zero orphan
  processes;
- deterministic import/replay, settlement, review, playback, and Save As
  export;
- one consentful WebView2 microphone capture when the testbed exposes an input
  device, including permission denial/retry; if the VM cannot expose input,
  retain deterministic fake/input-device evidence and label physical microphone
  parity as the one explicit Windows POC limitation;
- the complete tactical 052 disclosure, cancel-with-no-request, acquisition,
  relaunch, score generation, offline reuse, provenance, removal, and artifact
  preservation sequence; and
- package replacement with external sessions, installation identity, and
  compatible acquired runtime preserved.

Record Windows guest version, native architecture, process architecture,
emulation status, WebView2 version, package hashes, and timings. Do not compare
emulated timing to the physical x64 baseline as though they were the same host.

## Phase 4 — Signing And GitHub Release Matrix

Extend `.github/workflows/desktop.yml` with a `windows-2025` x64 job. Keep the
existing two updater-signing secrets shared by both operating systems. For the
minimal exportable-certificate path, add exactly:

| Secret | Purpose |
| --- | --- |
| `WINDOWS_CERTIFICATE_PFX_BASE64` | Base64-encoded Authenticode certificate and private key |
| `WINDOWS_CERTIFICATE_PASSWORD` | PFX import password |

Import the certificate into a temporary current-user certificate store from a
permission-bounded runner-temp file, verify only subject/thumbprint metadata,
sign and timestamp the executable/installer, and delete the decoded certificate
on every exit path. Never echo, pass secret values as command arguments, retain
base64 output, or upload the certificate. If the available certificate cannot
be exported, replace this mechanism with a reviewed external signing provider
and its minimum secret set; do not use a self-signed certificate for the public
release.

The Windows release job must fail before staging/signing when its credentials
are absent. A non-tagged `workflow_dispatch` rehearsal must prove certificate
import, executable/installer signing, updater signing, packaged smokes,
forbidden-model scans, cleanup, and that no GitHub Release is created.

Expand the release contract and finalizer from one to exactly two updater
targets:

```text
darwin-aarch64
windows-x86_64
```

The draft contains the signed/notarized DMG and macOS updater pair, signed NSIS
setup executable and Windows updater signature, required LGPL corresponding
sources/notices, checksums, and build attestations. The finalizer rejects a
missing platform, extra platform, mismatched version, unsigned installer,
missing updater signature, forbidden score asset, or incomplete source bundle.
Both platform jobs must complete before publication.

## Phase 5 — Coordinated Update Campaign

Run one release sequence, not separate platform versions:

1. build, validate, and publish `desktop-v0.1.0` with both platforms;
2. install `0.1.0` on macOS and the Windows testbed;
3. acquire and exercise the score runtime on both;
4. publish `desktop-v0.1.1` with one unmistakable visible change and a
   compatible acquisition contract;
5. use each installed application's production updater to discover, download,
   install, and relaunch into `0.1.1`;
6. on Windows, prove the updater's automatic exit stops the sidecar/process
   tree before NSIS replacement;
7. prove installation identity, sessions, acknowledgement, and acquired runtime
   persist without reacquisition on both; and
8. remove the optional model and uninstall the application without deleting
   retained user sessions or exported artifacts.

Retain redacted request destinations, update metadata, artifact hashes,
signing verification, version/component identities, external-runtime manifests,
and before/after process inventories for each operating system.

## Acceptance

- The first published tag contains both supported platform artifacts with one
  coherent version and feature contract.
- Windows x86_64 runs the complete ordinary application on CPU without WSL,
  CUDA, or a development toolchain.
- The signed per-user installer installs, launches, updates, and uninstalls
  without an unexpected administrator requirement.
- The Windows package contains no MIDI2ScoreTransformer repository/checkpoint,
  but the acknowledged direct acquisition produces a retained score matching
  macOS semantics.
- A real signed `0.1.0 -> 0.1.1` Windows update preserves external user data and
  the compatible acquired score runtime and leaves no process orphan.
- The ARM64 testbed result is labeled as x64 emulation; the release claims
  Windows x86_64 support, not native Windows ARM64 performance or packaging.
- Release validation fails closed unless both `darwin-aarch64` and
  `windows-x86_64` are complete, signed, checksummed, attested, and free of
  forbidden model content.

## Later Work

- Native Windows ARM64 packaging after the complete model/dependency stack has
  supported ARM64 wheels and passes parity without emulation.
- Optional NVIDIA/CUDA model pack, scheduler tuning, and native x64 performance
  work beyond the CPU feature baseline.
- MSI, Microsoft Store, machine-wide installation, or enterprise deployment.

## Execution Record

Implementation began on 2026-08-23 with the fail-closed Python contract slice.
`ModelPack`, `DesktopReady`, and `DesktopHandshake` accept the two exact release
identities, reject cross-platform pairs, and require the handshake's model pack
to match its platform, architecture, and CPU backend. Host normalization maps
Darwin arm64/aarch64 to `macos/arm64` and Windows AMD64/x86_64 to
`windows/x86_64`; Windows ARM64 remains rejected because it is not a published
native target. Focused Ruff and `tests/test_desktop.py` validation pass with 16
tests. This is contract evidence only and does not yet make the Rust launcher
or package Windows-compatible.

The next boundary slice replaced the Rust launcher's compile-time macOS gate
with an exact target descriptor. macOS arm64 uses `bin/python3`, `.app`, and
`tauri://localhost`; Windows x86_64 uses `python.exe`, NSIS, and Tauri's
default `http://tauri.localhost` origin. Ready records remain target-bound,
resource fallback handles `.app` resources or an executable-adjacent Windows
resource directory, the child `PATH` uses platform-native separators, and the
same exact origin is passed to the sidecar, handshake, and artifact export.
The Python server accepts only those two bundled origins. The frontend accepts
only the corresponding identity/package triples and permits Tauri's updater
to install both `.app` and NSIS packages in-app.

Focused validation on macOS passes 17 Python desktop tests, 15 Rust tests,
TypeScript compilation, and 17 Node contract/updater tests. These injected
Windows cases establish portable contracts; they are not Windows compilation,
staging, installation, or UI evidence. Phase 2 runtime staging is next.

The exact `b250cac` archive then compiled for
`x86_64-pc-windows-msvc` on the Windows 11 ARM64 testbed after building the
production frontend. Running the x64 Rust tests under Windows emulation found
two harness-only POSIX assumptions: a literal `sh` helper and expected cache
paths with POSIX separators. The helper now uses `cmd.exe` on Windows and the
cache assertions compare native `Path` values. All 15 Rust tests subsequently
pass on both macOS arm64 and Windows x64-on-ARM64 emulation; macOS Clippy also
passes with warnings denied. This is the first native Windows shell compile
and execution evidence, but remains deliberately labeled emulated and does not
include the staged Python/model/media runtime.

The score-support slice now freezes standalone CPython 3.11.14, 61 exact
hash-pinned registry packages, and three exact VCS commits in shared tracked
inputs. A universal `uv` dry run for Windows x64 selects 25 Windows artifacts
and resolves the full 61-package registry inventory without an unsupported
dependency. This is a package-resolution preflight only. The Windows x64
standalone interpreter, PE/DLL audit, imports, external model composition,
retained score output, and installed package remain the next work.

A Windows-only score-support builder now stages the same inputs into a
relocatable `.venv/python.exe` layout without requiring Python, uv, Git, or a
compiler on the user's machine. It accepts either an AMD64 build host or the
ARM64 testbed, but selects and executes exact x64 CPython 3.11.14. Staging is
transactional and audits package/VCS identities, canonical payload hashes,
symbolic links, forbidden model and accelerator content, x64 PE headers, and
both retained import groups. Unit tests cover relative managed-Python paths,
cross-platform hash ordering, PE rejection, and acquisition-input identity.
The upstream MUSTER package unconditionally invokes Unix `sh` and `g++` to
compile evaluation executables during wheel construction. The Windows builder
records a narrow packaging override: it checks out the exact pinned commit and
installs its importable Python wrapper without `compile.sh`, C++ sources,
evaluation programs, or demo data. Atpiano does not call the omitted evaluation
path; removing this eager dependency remains tactical 052's later cleanup.
Pruning deliberately skips `*.dist-info`/`*.egg-info` license trees even when
an upstream notice directory is named `testing`. All transactional cleanup uses
Windows extended-length paths so deeply nested Torch notices and read-only
standalone-Python files cannot strand a failed stage.
Build-only `venv`/`ensurepip` content and Setuptools launcher templates are
removed before PE validation; those templates include intentional 32-bit and
ARM64 executables and are not used to run the signed application.
The live build result follows below; it is support-layer evidence, not a
successful Windows application package.

Exact commit `264905bb92312e1fe5c0a2cdbf3e2700956280d7` was transferred to
the claimed Windows 11 ARM64 testbed with the builder and input hashes matched
before execution. An ARM64 `uv` process selected standalone x64 CPython
3.11.14 build `20260114`; the interpreter reported `AMD64` and all package
imports therefore ran under Windows x64 emulation.

The completed support package records:

| Evidence | Value |
| --- | ---: |
| Distributions | 64 |
| x64 PE files | 196 |
| Files | 20,621 |
| Payload bytes, excluding manifest | 920,227,529 |
| Total installed bytes | 920,228,180 |
| Payload SHA-256 | `4b9c41b350978164a97070bad4d894982b2d454b7ea1d628cabffef4c6461bd1` |
| Manifest SHA-256 | `115da3b8287a84fc1c8204335fc3a16b109a6d811b3cdff4606ddf2358f05479` |
| Package-inventory SHA-256 | `5449e41ab60a41e6f5cfa3ef2d7a798a63fe95146e387a02d6ad417b476ce43d` |

The build ran both retained import groups, validated every remaining
`.exe`/`.dll`/`.pyd` as x86_64, rejected symbolic links and accelerator/model
content, published transactionally, and left zero staging directories. A
second independent audit of the published directory passed. These results do
not establish native x64 timing, ordinary desktop runtime staging, actual
MIDI2Score inference, MusicXML parity, Tauri packaging, or installed UI
acceptance.

The Phase 2 ordinary-runtime builder now selects standalone x64 CPython
3.10.19 build `20260114`, installs the 101 locked production dependencies plus
Atpiano, extracts the Windows ONNX Basic Pitch asset and Transkun CPU assets
into the platform-bound model pack, and bundles the exact BtbN
`n8.1.2-44-g7c533d0f86` shared-LGPL FFmpeg/FFprobe payload. The media archive
SHA-256 is
`d311c8c7b86e06b54588e442652f963bae165bd4d8393e73cc9ebb445b025547`;
an encode/probe control passes without a user-installed media tool.

Windows traversal found that Torch's retained `*.dist-info` third-party
license files were too deeply nested for a real Tauri resource path. The
builder now preserves those files under a flat, hashed
`share/licenses/python` inventory with their distribution, original path, and
digest. The final score-support layer retains 165 such files, has 20,577 total
files and 920,111,485 installed bytes, and its 920,110,834-byte canonical
payload hashes to
`1f5ba6c1987e48781b115593c1e92940fff9074a02d34e22c9dc15dbb4008c4b`.

Exact commit `c753038` then produced the complete resource tree at the path
Tauri will consume. The builder's acceptance audit and a second independent
in-place audit both passed on the Windows 11 ARM64 testbed as x64 processes:

| Evidence | Value |
| --- | ---: |
| Ordinary distributions | 102 |
| x64 PE files, complete tree | 583 |
| Files, complete tree | 35,364 |
| Installed bytes | 2,123,359,429 |
| Canonical payload SHA-256 | `c07b13bac776fcb51fda4389d3be3470ce1a0aa589bb5bf64670f46b9103544d` |
| Bundle-manifest SHA-256 | `e16526415e23367f64da41cd872177be469b5c0522bb327a5b3a4212ff40a771` |
| Model-pack SHA-256 | `9d1dfeaa8de67145e8fb0866e578228092afe6ced55e280e434c7841de95227f` |

The packaged-layout sidecar smoke returned the Windows x86_64 identity,
rejected the unauthenticated handshake with HTTP 401, accepted the exact Tauri
Windows origin and bearer token, reported score unavailable before user
acquisition, and stopped cleanly on parent EOF. The complete stage contains no
MIDI2ScoreTransformer source or checkpoint. This completes the deterministic
runtime-staging portion of Phase 2; Basic Pitch/Transkun fixture replay,
external acquired-score inference, Tauri/NSIS packaging, installation, UI,
signing, and update acceptance remain.

## Rollback

Before publication, a Windows packaging/signing failure keeps the entire binary
release on hold; it does not silently revert the product decision to macOS-only.
After publication, an urgent Windows defect may remove the affected Windows
asset/update target and issue a signed forward fix while leaving the macOS
artifact available, but the public release notes and supported-target metadata
must immediately describe the reduced state. Never direct an incompatible
Windows build to a macOS update or silently delete external user/model data.
