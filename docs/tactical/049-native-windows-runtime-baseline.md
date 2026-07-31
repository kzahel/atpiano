# 049 — Native Windows Runtime Baseline

Topic: windows-native-runtime-portability

Topic: nvidia-accelerated-low-latency-pipeline

Status: **complete on 2026-07-31.**

## Motivation

The RTX 4090 desktop should become the authoritative native Windows
development host for Atpiano's local server and later CUDA measurements. The
accepted desktop package is still macOS arm64 only, and the current Windows
checkout has no project environment. Proving the unpackaged application core
first will make later Windows sidecar and model-pack work an adaptation of a
known runtime rather than a simultaneous operating-system, model, and
packaging rewrite.

This tactical retires the native dependency and deterministic CPU risks. CUDA
scheduler tuning, Tauri packaging, installers, signing, and updates remain
later slices.

## Starting Host

The read-only host inspection recorded:

```text
OS architecture / build: 64-bit Windows / 26200
CPU:                     Intel Core i7-13700KF
CPU cores / threads:     16 / 24
RAM:                     102,906,769,408 bytes
GPU:                     NVIDIA GeForce RTX 4090
VRAM:                    24,564 MiB
VBIOS:                   95.02.20.00.03
NVIDIA driver:           610.88
GPU power limit:         450 W
Python on PATH:          3.13.14
Node / npm:              24.18.0 / 11.16.0
Rust / Cargo:            1.96.0 / 1.96.0
Git:                     2.54.0.windows.1
uv:                      not installed
repository environment: not present
```

The GPU was idle at P8 and 39 degrees Celsius during the record. The Windows
display was not active on this GPU according to `nvidia-smi`.

## Bounded Goal

Establish a reproducible native Windows development runtime that:

1. uses managed CPython 3.10 and the repository lock;
2. runs the repository's platform-applicable regression and frontend gates;
3. executes the fixed Basic Pitch and Transkun CPU controls with comparable
   normalized output;
4. exercises accelerated replay through the unpackaged `workbench-v3` server
   and a normal Windows browser or an equivalent retained client gate;
5. records the dependency, native-library, model, size, and startup inventory
   needed by a later packaging tactical; and
6. uses only native Windows processes and paths.

## Frozen Decisions

- Attempt the untouched lock before editing dependencies.
- Preserve Basic Pitch 0.4.0, the released model artifact, native frame/onset
  output, and the existing decoder policies.
- Treat full TensorFlow, if required, as a Windows parity oracle first rather
  than an automatic final packaging choice.
- Establish CPU validity before enabling or measuring CUDA.
- Keep device-specific behavior behind the existing model-adapter boundary.
- Keep checkpoints, generated fixtures, environments, profiles, and benchmark
  output outside Git.
- Do not use WSL for any result labeled native Windows.
- Do not modify scheduler buffer, hop, guard, context, or decoder thresholds.
- Do not adapt the current macOS Tauri bundle in this tactical.

## Implementation Sequence

### 1. Bootstrap and inspect

- Install `uv` using an official Windows distribution.
- Provision a managed CPython 3.10 without replacing the existing Python 3.13
  installation.
- Record `uv`, Python, package-lock, Git, OS, CPU, and GPU identities.
- Attempt `uv sync --frozen` and `uv sync --extra corrected --frozen` before
  modifying `pyproject.toml` or `uv.lock`.

### 2. Resolve Basic Pitch on Windows

- Record whether the ordinary environment resolves and which inference import
  fails when `BasicPitchLiveModel` loads.
- Evaluate the upstream-supported full-TensorFlow path as the first parity
  control if no Windows TFLite interpreter is present.
- Make any platform marker or optional-runtime decision explicit in the lock.
- Compare model-native frame, onset, and contour arrays or their stable
  summaries on the frozen fixture before accepting normalized note parity.
- Record cold load, warm inference, package size, and native DLL inventory.

### 3. Pass deterministic CPU controls

- Build and hash the fixed musical fixture.
- Run Basic Pitch offline and rolling preview controls.
- Run Transkun 2.0.1 on CPU with the existing checkpoint and two-thread
  setting.
- Compare note, velocity, pedal, boundary, coverage, and settlement artifacts
  with retained controls at declared tolerances.
- Preserve model-native output when practical so later thresholds remain
  re-evaluable.

### 4. Exercise the unpackaged application

- Run the applicable Python, TypeScript, frontend, generated-contract, lint,
  audit, and production-build gates.
- Exercise accelerated replay through the native `workbench-v3` server.
- Confirm continuous sample-indexed ingest, preview/correction horizons, Stop,
  settlement, reload, and artifact availability.
- Keep wall-clock, physical microphone, and CUDA end-to-end claims out of this
  tactical unless the bounded controls complete early and the evidence remains
  separable.

### 5. Record the packaging handoff

Measure separately:

- application and common Python runtime dependencies;
- Basic Pitch runtime and model assets;
- Torch, Transkun, and corrected dependencies;
- native DLL and media-tool requirements;
- installed size and expected compressible inputs;
- cold interpreter, server, and model load; and
- cache, workspace, model, and generated-output locations.

Document which assets appear common, CPU-only, NVIDIA-specific, development
only, or internal-score-only. Do not prune or redistribute them in this slice.

## Acceptance

This tactical completes only when:

- the commands and environment are reproducible from the tracked lock and
  documented platform decision;
- no model or server process depends on WSL;
- the frozen fixture hashes match the existing control;
- Basic Pitch native output and normalized events are comparable;
- Transkun CPU notes and pedal events are comparable;
- accelerated local-server replay completes with durable settlement;
- the applicable regression and production frontend gates pass;
- platform, package, model, checkpoint, precision, and device provenance are
  retained; and
- the packaging inventory and remaining native Windows gaps are recorded.

If a dependency cannot be resolved without changing model semantics, record
the exact blocker and stop before CUDA or desktop packaging. A failed native
baseline is useful evidence and may use WSL only as a separately labeled
diagnostic control.

## Explicit Exclusions

- No CUDA performance claim or hop/guard sweep.
- No MIDI2ScoreTransformer CUDA work.
- No Tauri Windows launcher, sidecar staging, WebView2 package, installer,
  signing, updater, or rollback channel.
- No claim of physical microphone or network-disabled desktop parity.
- No model conversion, quantization, retraining, or decoder-policy change.
- No public deployment or change to the active macOS sharing service.

## Execution Record

### Native environment and dependency decision

The host now has `uv` 0.11.32 from the official WinGet package and a
uv-managed CPython 3.10.20. The pre-existing Python 3.13 installation was not
replaced. Both untouched lock operations passed:

```text
winget install --id astral-sh.uv -e
uv python install 3.10
uv sync --frozen
uv sync --extra corrected --frozen

winget install --id Gyan.FFmpeg.Essentials -e
```

WinGet updates the user `PATH`; a new PowerShell process is required before
the newly installed `uv`, `ffmpeg`, and `ffprobe` aliases are visible.

The ordinary environment installed 77 packages. The corrected environment
installed 32 additional packages, including Transkun 2.0.1, Torch 2.13.0,
and torchaudio 2.11.0. The locked Torch wheel is CPU-only:

```text
torch:                   2.13.0+cpu
torch.version.cuda:      None
torch.cuda.is_available: false
```

No dependency or lock change was necessary. Basic Pitch 0.4.0 selected its
bundled ONNX artifact on Windows rather than TFLite, so full TensorFlow was
also unnecessary. ONNX Runtime exposed its CPU and Azure execution providers.
The selected model is 230,444 bytes with SHA-256:

```text
2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec
```

### Fixed input and Basic Pitch control

The generated fixture outside Git matched both established hashes:

```text
WAV:  0eab5d787cb482735dc840daaed2abfb6d00ad6ff7a7058fdd217522905aaa89
MIDI: d24635a3f75d83dd8ff40e9513475dc43064e1dbb29fd836345f2057da0ec7d9
```

The untouched offline adapter retained the unmodified model-native output as
`contour[3612,264]`, `note[3612,88]`, and `onset[3612,88]` float32 arrays. It
produced 280 estimated notes against 198 reference notes, onset F1 0.753 at
50 ms and 0.736 at 25 ms, and these stable artifact hashes:

```text
raw Basic Pitch NPZ:
deda53843446a8fb01153b9b66a07e87ab2c07bfa6ae84fae8c9909b547b78f5
prediction:
23da50a49afeca7e2b20fda30079caa4f51b4996b67dcf18296f47fbd9f61024
```

Adapter setup took 0.276 seconds and full-file inference took 9.402 seconds.
The rolling preview processed the established 161 windows, retained 32,
evicted 129, emitted 703 revisions, and reached an active-identity high-water
mark of 196. Those four counts match the retained control. Per-window
inference averaged 9.617 ms with a 13.610 ms maximum; preparation averaged
1.938 ms with a 3.123 ms maximum. This accelerated replay intentionally has
no capture-to-event latency claim.

### Transkun CPU control

The two-repeat, 84-second CPU profile used the unchanged 28/4/4-second
scheduler, two Torch threads, and the released checkpoint and configuration:

```text
checkpoint:
50a80010effc2a59ffcd068a95cd2b29bd7f23a27a3515bc3ccd209c89a3d44c
configuration:
d3d989214eb148230ee5df476d994dcde6af595904d3f968f1221d2e3bea5ac6
profile:
e550db54aedacbf364ca97dd9f78df8bc35a9edbd2ad327b5b53122ce415a37b
```

The 10 measured decodes averaged 13.743 seconds, reached 14.575 seconds, and
had a 1.636 service ratio. The measured recommendation is therefore
`after-stop`. Model load was 0.141 seconds and the unmeasured warm-up decode
took 12.184 seconds.

The two repetitions produced 151 and 157 notes plus 12 and 10 controller
intervals. They had pairwise onset F1 0.948 at both 25 and 50 ms,
note-with-offset F1 0.753, and velocity MAE 1.753. Against the aligned MIDI,
onset F1 was 0.865 and 0.873. This is comparable to the previously accepted
155/156-note repeated control, whose pairwise onset and offset F1 values were
0.939 and 0.682. All 4,032,000 source frames committed and no pending offset
tail remained.

### Windows portability corrections and regression

The first full migration report exposed bounded operating-system assumptions,
not model failures. The implementation now:

- resolves command names through `PATH` and `PATHEXT`, so Python subprocesses
  launch `npm.cmd` correctly;
- invokes the OpenAPI TypeScript generator through Node instead of a POSIX
  executable shim;
- records Windows peak working-set size with `GetProcessMemoryInfo`;
- opens published media with a Windows-compatible writable handle before
  flushing it and does not require POSIX directory descriptors;
- writes JSON and JSONL with deterministic LF endings and stores relative
  artifact paths with `/` separators;
- identifies Mach-O files from their binary magic without requiring the Unix
  `file` command;
- serves JavaScript with one stable MIME type; and
- explicitly skips the macOS desktop/service and privileged-symlink checks
  that are not executable on this Windows account.

The resulting retained migration report passed all six lanes:

```text
Python:           244 passed, 13 explicit skips, 2 warnings
JavaScript:       passed
API contracts:    generation, typecheck, tests, and audit passed
Ruff:             passed
JavaScript syntax: passed
Git whitespace:   passed
```

The skips are four accepted macOS-arm64 desktop gates, one privileged Windows
symlink creation check, one POSIX process-signal check, and seven macOS-only
sharing-service checks. The production Vite build also passed; its deployable
`app/dist` output is 1.55 MiB. The existing large-chunk warning remains and
is packaging optimization work, not a runtime failure.

### Native application and storage boundary

The native `workbench-v3` process built the production frontend, bound only
to `127.0.0.1`, and ran accelerated replay with explicit CPU after-Stop
correction. The loopback homepage and capability API returned HTTP 200. A
fresh API client reattached through the session catalog after settlement.

The session ingested all 2,016,000 source frames and completed both lanes. It
processed 161 preview windows, used five commit decodes, and materialized 151
notes plus 12 controller intervals with no open tail. The API returned 163
latest event rows and four artifacts: verified MP3 audio, complete event
history, MIDI, and an export manifest. Compact settlement retired the WAV
source. The exact launched server process tree was stopped after validation.

The Windows RSS implementation and native FFmpeg path also passed a separate
3,612-second accelerated storage run. It repeated all 42 fixture seconds 86
times in 28.395 wall seconds, retained no raw WAV or ordinary debug file,
verified every repetition boundary at a minimum correlation of 0.904307, and
reconciled every storage category. Peak process working set was 161.29 MiB.
The 55.12 MiB MP3 measured 57,600,810 bytes per source hour.

### Packaging-readiness inventory

The current development environment is evidence, not a proposed payload:

| Component | Installed size |
|---|---:|
| managed CPython 3.10.20 | 59.83 MiB |
| complete corrected `.venv` | 1,172.86 MiB |
| site-packages within that environment | 1,140.34 MiB |
| Torch package | 456.39 MiB |
| Transkun package, including checkpoint | 54.05 MiB |
| Basic Pitch package | 2.15 MiB |
| ONNX Runtime package | 37.35 MiB |
| NumPy / SciPy | 21.42 / 104.07 MiB |
| frontend development dependencies | 272.21 MiB |
| production frontend | 1.55 MiB |

The environment contains 109 Python distributions and 336 `.dll` or `.pyd`
files totaling 670.47 MiB. The largest is Torch's 290.95 MiB
`torch_cpu.dll`; the next largest is the development environment's 114.79
MiB `llvmlite.dll`. A later sidecar build must derive an inference-minimal
inventory instead of copying this environment wholesale.

Native FFmpeg 8.1.1 Essentials passed import, compact-publication, seek, and
alignment gates. Its static `ffmpeg.exe` and `ffprobe.exe` are 96.76 and
96.56 MiB. `ffplay.exe` is not used and should not be staged. The first
Windows packaging experiment should measure whether the two required static
binaries can share libraries or be replaced by a smaller reproducibly
licensed build without changing media acceptance.

The natural future split is:

- common sidecar: managed Python, application code, common packages, and the
  1.55 MiB frontend;
- preview pack: Basic Pitch, its 0.22 MiB ONNX model, and ONNX Runtime;
- corrected CPU pack: Torch CPU, Transkun, and its 53.80 MiB checkpoint;
- media pack: FFmpeg and FFprobe only;
- NVIDIA pack: not installed or measured yet; and
- development only: Node dependencies, pytest, Ruff, package tests, caches,
  and other build tooling.

The observed detached cold server launch, including a production frontend
rebuild, reached its capability endpoint within a conservative 13.8-second
upper bound. Basic Pitch and Transkun model-load/inference timings are
recorded separately above. A packaging tactical should add launcher-owned
start-to-ready instrumentation before treating startup as an optimization
baseline.

### Closure and next slice

Generated evidence is retained below ignored
`results/windows-native-baseline/`; the fixture remains outside the
repository at `../atpiano-artifacts/musical-loop-input/`. No model,
checkpoint, environment, media output, or benchmark result entered Git.

The native Windows CPU server baseline is established without WSL. The next
bounded tactical should install an explicit CUDA-enabled Windows Torch build,
rerun the same profile and parity gates, and only then open the scheduler
hop/guard sweep. Tauri adaptation, a relocatable sidecar, model-pack pruning,
WebView2, installer, signing, updates, and physical microphone review remain
separate future work.
