# Native Windows Runtime Portability

Topic: windows-native-runtime-portability

Status: **native Windows CPU server and model-runtime baseline established on
2026-07-31.** The locked ordinary and corrected environments, Basic Pitch
ONNX preview, Transkun CPU correction, production frontend, migration gate,
one-hour storage control, and unpackaged `workbench-v3` replay all pass on the
user-controlled RTX 4090 desktop without WSL. CUDA, physical microphone, and
Windows desktop packaging have not passed. The accepted Tauri proof remains
macOS arm64 only.

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

## Validated Native Baseline

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
WSL2. Native Windows initially had Python 3.13 on `PATH` and no `uv` or
repository environment. Tactical 049 installed official `uv` 0.11.32 and a
managed CPython 3.10.20 without replacing Python 3.13. Both frozen syncs pass
without a lock change.

The anticipated TFLite blocker did not materialize. Basic Pitch 0.4.0 selects
its bundled 230,444-byte ONNX model on Windows and runs through ONNX Runtime
CPU. Full TensorFlow is unnecessary. Offline inference preserves the native
contour, frame, and onset arrays; rolling replay matches the established 161
windows, 32 retained windows, 129 evictions, 703 emissions, and identity
high-water of 196.

The locked Windows Torch 2.13.0 wheel is CPU-only. Native CPU Transkun passed
the two-repeat control with 151/157 notes, pairwise onset F1 0.948, offset F1
0.753, and no open tail. Its 13.743-second mean decode cannot sustain the
four-second scheduler and correctly selects after-Stop correction. This
answers the CPU portability question but deliberately leaves CUDA dependency
selection to the NVIDIA topic.

The unpackaged native server ingested and settled all 2,016,000 fixture
frames, reattached through the session catalog, and exposed complete audio,
event-history, MIDI, and manifest artifacts. Native FFmpeg 8.1.1 passed
compact publication and an accelerated 3,612-second storage validation. The
complete Windows-applicable migration gate and production frontend build pass.
The implementation corrections cover `PATHEXT` subprocess launch, Windows
peak-RSS accounting, media flushing, stable MIME types, deterministic LF JSON,
portable artifact separators, and Mach-O inspection without Unix `file`.

The development environment is 1.17 GiB and is explicitly not a packaging
proposal. The handoff identifies a 59.83 MiB managed interpreter, 1.55 MiB
production frontend, separate ONNX preview and Torch/Transkun corrected
components, and FFmpeg/FFprobe media tools. Tactical 049 owns the full
measurement table and retained command evidence.

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

### 1. Open a bounded native-runtime tactical — complete

Before changing dependencies or application behavior, create the next
zero-padded tactical. It should record the exact host, dependency decision,
commands, frozen fixtures, retained evidence, and rollback or fallback path.
Do not combine the native runtime, CUDA scheduler sweep, Tauri packaging,
installer, signing, and updater into one implementation slice.

### 2. Establish the native development environment — complete

Install or select a native Windows Python 3.10 and `uv`, then attempt the
frozen ordinary and corrected environments. Record every platform-specific
resolution gap rather than weakening the lock globally.

Prefer one explicit platform-aware dependency decision over manual edits in a
developer environment. Any Basic Pitch interpreter substitution must run the
frozen fixture and compare native activations or normalized output against an
existing validated result.

### 3. Pass deterministic CPU controls — complete

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

### 4. Establish native CUDA evidence — next

Continue with the controls and decision gates in the NVIDIA topic. Torch must
report the Windows device, CUDA build, device name, and compute capability.
CPU and CUDA runs must use the same source, checkpoint, adapter, precision,
and scheduler policy before hop or guard values change.

### 5. Exercise the unpackaged local server — CPU complete

The primary `workbench-v3` server now passes native accelerated CPU replay and
an equivalent retained loopback client gate. Repeat this path with the
matching CUDA profile, then validate wall-clock replay and only then a
consentful physical microphone session. Retain:

- continuous sample-indexed ingest;
- preview and correction horizons;
- worker queue and model timing;
- Stop acknowledgement and background settlement;
- reload reattachment and artifact recovery;
- server delivery and browser paint acknowledgement; and
- host, device, model, and backend-profile compatibility identity.

This is the first packaging-aligned Windows application baseline. It is still
an unpackaged development runtime.

### 6. Produce a packaging-readiness handoff — baseline complete

Tactical 049 records the first dependency, size, model, media, native-library,
and startup inventory. A Windows desktop tactical still needs to stage and
supervise:

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

The native Windows CPU server baseline is established because:

1. all model and server processes are native Windows processes with no WSL
   dependency;
2. the frozen fixture and its hashes identify every compared run;
3. Basic Pitch and CPU Transkun produce valid comparable normalized output;
4. accelerated CPU server replay preserves ingest, Stop, settlement,
   reattachment, and artifact behavior;
5. every result records platform, architecture, Python, package lock, model,
   checkpoint, precision, and device provenance;
6. benchmark and model artifacts remain outside Git; and
7. the packaging-readiness handoff identifies remaining Windows desktop work
   without claiming that work is complete.

CUDA Transkun must still pass its separate parity gate before any scheduler
sweep or CUDA server claim. Wall-clock replay, browser paint timing, and a
physical microphone remain extensions rather than evidence already obtained.

Microphone parity is a separate acceptance extension. A deterministic server
baseline must not be delayed merely because a physical capture review has not
yet occurred, but it also must not be described as microphone-validated.

## Open Questions

- Which explicit CUDA-enabled Windows Torch source and version should define
  the NVIDIA extra while preserving the CPU environment and lock discipline?
- Which native media and audio libraries are required for the server control,
  physical capture, and eventual relocatable sidecar?
- Which remaining process-signal and privileged-symlink behaviors need a
  Windows-specific implementation rather than an explicit platform exclusion?
- How much does the WSL2 reference differ from native Windows for warm Transkun
  decode, preprocessing, host-to-device transfer, and post-processing?
- Should the future Windows desktop ship separate CPU and NVIDIA model packs,
  or one manifest-selected pack with shared immutable assets?
- What is the smallest Windows Tauri development slice that proves the native
  server can be staged and supervised without prematurely implementing the
  installer, signing, or updater?
