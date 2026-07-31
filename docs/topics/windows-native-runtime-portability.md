# Native Windows Runtime Portability

Topic: windows-native-runtime-portability

Status: **proposed native Windows server and model-runtime baseline as of
2026-07-31.** The first intended host is the user-controlled 64-bit Windows
desktop with an NVIDIA RTX 4090. No native Windows Atpiano environment,
deterministic replay, local server, microphone, CUDA model result, or desktop
package has passed yet. The accepted Tauri proof remains macOS arm64 only.

## Intent

Make native Windows an authoritative Atpiano execution environment before
attempting Windows desktop distribution. The immediate target is the ordinary
unpackaged Python/React local server and its deterministic model commands, not
an installer or a finished Tauri application.

This sequencing should answer two questions with one coherent runtime:

1. Can the current application core, fixed fixtures, Basic Pitch preview, and
   Transkun correction run reproducibly on native Windows?
2. Can that same native runtime become the future Windows desktop sidecar and
   model-pack payload without rewriting model or application behavior during
   packaging?

WSL2 remains a useful Linux/CUDA reference and failure-isolation tool, but it
is not the authoritative Windows result and must not become a runtime
prerequisite for the desktop product.

## Scope And Relationship

This topic owns:

- a reproducible Python 3.10 and `uv` development environment on native
  Windows;
- Windows-compatible resolution of the locked application, Basic Pitch, and
  corrected-note dependencies;
- deterministic fixture and ordinary local-server execution from PowerShell;
- Windows path, process, subprocess, media-tool, loopback, and shutdown
  behavior needed by the application core;
- platform, architecture, model, checkpoint, precision, and execution-device
  provenance;
- native CPU parity before accelerator-specific optimization; and
- the boundary between a working development runtime and a later relocatable
  desktop sidecar/model pack.

[`nvidia-accelerated-low-latency-pipeline.md`](nvidia-accelerated-low-latency-pipeline.md)
owns the RTX 4090 CPU/CUDA parity profiles, scheduler sweeps, GPU contention,
and latency conclusions after this topic establishes the native runtime.
[`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md)
continues to own model-output and quality comparison.

[`live-acoustic-transcription.md`](live-acoustic-transcription.md) continues to
own capture, the source sample clock, delivery, and browser paint timing.

[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
continues to own the durable desktop sidecar, model-pack, compatibility,
security, update, and distribution shape.

[`linux-development-portability.md`](linux-development-portability.md) retains
the validated x86_64 Linux control and may help distinguish a Windows defect
from a general model or dependency defect.

This topic does not open the full desktop Phase 6, authorize an installer,
select signing or updater infrastructure, or claim Windows microphone or
packaged-app parity before those paths are measured.

## Direction

### Native Windows is authoritative

Run the model processes and local server as native Windows executables. Do not
publish a Windows result when Python or model inference actually ran inside
WSL. WSL comparisons must identify the distro, kernel, filesystem, and driver
boundary and remain labeled as Linux/WSL evidence.

PowerShell is the expected development shell, but the shell itself is not the
product contract. Commands, configuration, and application code should avoid
depending on interactive PowerShell state so that the same runtime can later
be launched by the thin Rust shell.

### Establish the server before packaging it

The first useful Windows result is a working local application reached through
the ordinary browser, plus deterministic CLI evidence. It should use the same:

- application-core services;
- session and artifact contracts;
- sample-indexed capture and replay path;
- model adapters and normalized event schemas;
- model/device provenance;
- workspace layout; and
- frontend build consumed by the desktop runtime.

The future packaged sidecar should primarily replace how Python, dependencies,
models, media tools, workspace roots, and lifecycle are located and launched.
It should not introduce a second transcription server or a Windows-only model
contract.

### Keep packaging constraints visible

Server bring-up must not take shortcuts that make later packaging harder:

- do not require WSL paths, Linux binaries, Bash, symlinks, or a user-installed
  CUDA toolkit at application runtime unless a measured dependency truly
  requires one;
- keep models and device selection behind the existing adapter boundary;
- pass workspace, model-pack, checkpoint, backend-profile, and device choices
  explicitly rather than deriving them from the checkout;
- exercise child-process startup, bounded stdout/stderr, failure propagation,
  and clean shutdown with Windows semantics;
- retain a loopback-only, authenticated desktop protocol rather than trusting
  a port merely because it is local; and
- distinguish development dependencies from the inference-minimal runtime and
  separately versioned model packs.

### Preserve evidence for packaging optimization

Packaging size and startup optimization follow runtime parity; they are not a
reason to change models during bring-up. The native environment should still
produce the inventory needed for that later work: package and DLL ownership,
checkpoint and media-tool sizes, duplicated assets, installed size, expected
compressed size, cold process/model load, and warmed steady state.

Measure the application shell, common sidecar runtime, CPU model pack, NVIDIA
model pack, and internal-only score runtime separately. A later packaging
tactical may prune development packages, split accelerator packs, deduplicate
immutable assets, or choose a smaller compatible runtime only when the frozen
fixture and application parity gates can prove the optimization did not change
behavior.

## Known Starting Point

The inspected host reported:

```text
Windows architecture: x86_64
OS build:             26200
CPU:                  Intel Core i7-13700KF, 16 cores / 24 threads
RAM:                  approximately 96 GiB
GPU:                  NVIDIA GeForce RTX 4090, 24,564 MiB
NVIDIA driver:        610.88
GPU power limit:      450 W
```

The Windows driver and GPU are visible both to Windows `nvidia-smi` and Ubuntu
WSL2. Native Windows currently has Python 3.13 on `PATH`, but the project
requires Python 3.10; `uv` and a repository virtual environment were not
present during inspection.

The current lock contains a Windows x86_64 Torch wheel and Transkun is a pure
Python wheel, but native CUDA execution has not been proved. The more immediate
ordinary-environment gap is `tflite-runtime` 2.14.0: the current lock contains
Linux wheels and no Windows wheel. Basic Pitch preview parity therefore needs
a bounded Windows interpreter/runtime decision. Do not silently replace the
model, decoder, or output contract merely to make dependency installation
succeed.

The existing desktop proof is not a Windows starting artifact:

- the Tauri launcher accepts only `macos` / `arm64` / `cpu` sidecar identity;
- runtime resource discovery assumes a macOS `.app` layout;
- the staged Python runtime, model pack, and media tools are macOS arm64;
- the build helper targets `aarch64-apple-darwin` and produces an `.app`; and
- the accepted review explicitly excludes Windows packaging and microphone
  parity.

Those are known future adaptation points, not reasons to pull desktop
packaging into the first native-server slice.

## Reproducible Implementation Sequence

### 1. Open a bounded native-runtime tactical

Before changing dependencies or application behavior, create the next
zero-padded tactical. It should record the exact host, dependency decision,
commands, frozen fixtures, retained evidence, and rollback or fallback path.
Do not combine the native runtime, CUDA scheduler sweep, Tauri packaging,
installer, signing, and updater into one implementation slice.

### 2. Establish the native development environment

Install or select a native Windows Python 3.10 and `uv`, then attempt the
frozen ordinary and corrected environments. Record every platform-specific
resolution gap rather than weakening the lock globally.

Prefer one explicit platform-aware dependency decision over manual edits in a
developer environment. Any Basic Pitch interpreter substitution must run the
frozen fixture and compare native activations or normalized output against an
existing validated result.

### 3. Pass deterministic CPU controls

Before CUDA, require native Windows to:

- run the repository regression gates applicable to the platform;
- build the shared React frontend;
- generate and hash the fixed musical fixture;
- execute Basic Pitch preview and offline controls;
- execute Transkun with `--commit-device cpu`;
- retain complete event, pedal, provenance, timing, and settlement artifacts;
  and
- compare normalized output with the existing finite controls at declared
  tolerances.

Platform-specific timing may differ. Unexplained note, pedal, boundary,
coverage, or artifact differences are parity failures.

### 4. Establish native CUDA evidence

Continue with the controls and decision gates in the NVIDIA topic. Torch must
report the Windows device, CUDA build, device name, and compute capability.
CPU and CUDA runs must use the same source, checkpoint, adapter, precision,
and scheduler policy before hop or guard values change.

### 5. Exercise the unpackaged local server

Run the primary `workbench-v3` server natively and connect from a normal
Windows browser. Validate accelerated replay first, then wall-clock replay,
and only then a consentful physical microphone session. Retain:

- continuous sample-indexed ingest;
- preview and correction horizons;
- worker queue and model timing;
- Stop acknowledgement and background settlement;
- reload reattachment and artifact recovery;
- server delivery and browser paint acknowledgement; and
- host, device, model, and backend-profile compatibility identity.

This is the first packaging-aligned Windows application baseline. It is still
an unpackaged development runtime.

### 6. Produce a packaging-readiness handoff

After the server passes, record exactly what a Windows desktop tactical would
need to stage and supervise:

- inference-minimal Python runtime and wheels;
- CPU and CUDA model-pack variants and compatibility ranges;
- checkpoint and media-tool inventories;
- installed and expected compressed size by application, common runtime, and
  model pack;
- cold sidecar/model startup and warmed steady-state timing;
- Windows executable and resource layout;
- workspace and cache roots outside the installed application;
- child-process startup, authentication, readiness, monitoring, and shutdown;
- WebView2, microphone, offline, and artifact-export validation; and
- installer, signing, update, and rollback work that remains deliberately
  unimplemented.

Only then decide the bounded scope of the first Windows Tauri development
build.

## Baseline Acceptance

The native Windows server baseline is established only when:

1. all model and server processes are native Windows processes with no WSL
   dependency;
2. the frozen fixture and its hashes identify every compared run;
3. Basic Pitch and CPU Transkun produce valid comparable normalized output;
4. CUDA Transkun passes its separate parity gate before any scheduler sweep;
5. accelerated and wall-clock server replay preserve ingest, Stop,
   settlement, reload, and artifact behavior;
6. every result records platform, architecture, Python, package lock, model,
   checkpoint, precision, and device provenance;
7. benchmark and model artifacts remain outside Git; and
8. the packaging-readiness handoff identifies remaining Windows desktop work
   without claiming that work is complete.

Microphone parity is a separate acceptance extension. A deterministic server
baseline must not be delayed merely because a physical capture review has not
yet occurred, but it also must not be described as microphone-validated.

## Open Questions

- Which Windows-supported interpreter should execute the existing Basic Pitch
  TFLite artifact without changing model semantics?
- Does the locked Torch Windows wheel expose the required CUDA runtime on this
  driver, or does the project need an explicit accelerator-specific source?
- Which native media and audio libraries are required for the server control,
  physical capture, and eventual relocatable sidecar?
- Are any process, signal, path, file-locking, or atomic-replacement assumptions
  still POSIX-specific?
- How closely does native Windows CPU output match the validated Linux and
  macOS controls?
- How much does the WSL2 reference differ from native Windows for warm Transkun
  decode, preprocessing, host-to-device transfer, and post-processing?
- Should the future Windows desktop ship separate CPU and NVIDIA model packs,
  or one manifest-selected pack with shared immutable assets?
- What is the smallest Windows Tauri development slice that proves the native
  server can be staged and supervised without prematurely implementing the
  installer, signing, or updater?
