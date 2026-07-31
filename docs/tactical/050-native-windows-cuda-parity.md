# 050 — Native Windows CUDA Parity

Topic: nvidia-accelerated-low-latency-pipeline

Topic: windows-native-runtime-portability

Status: **complete on 2026-07-31.**

## Motivation

Tactical 049 established the native Windows CPU control and packaging-aligned
server path on this RTX 4090 host. The next decision is deliberately narrower:
select a reproducible CUDA-enabled Torch runtime, prove that it actually
executes Transkun on the Ada GPU, and compare its output and warm service time
with the unchanged CPU control before changing any scheduling parameter.

This tactical is the CUDA dependency and parity gate. It is not the scheduler
latency sweep or the Windows desktop package.

## Starting Control

The fixed 84-second source and released Transkun 2.0.1 checkpoint already pass
on native Windows with locked Torch 2.13.0+cpu. Under the unchanged 28-second
window, 4-second hop, and 4-second guard policy, ten measured CPU decodes
averaged 13.743 seconds and reached 14.575 seconds. The two repetitions emitted
151 and 157 notes, had pairwise onset F1 0.948 and offset F1 0.753, committed
all 4,032,000 source frames, and left no pending tail.

The host reports an NVIDIA GeForce RTX 4090 with 24,564 MiB VRAM, compute
capability 8.9, driver 610.88, and a CUDA 13.3 driver interface. This describes
the driver, not the user-space runtime bundled by a Torch wheel.

## Bounded Goal

Establish a native Windows CUDA result that:

1. resolves from an explicit official PyTorch wheel source and the repository
   lock rather than an untracked environment mutation;
2. records Torch, CUDA runtime, driver, GPU, compute-capability, precision,
   checkpoint, model, source, and backend-profile provenance;
3. proves a model operation and complete Transkun decode execute on the RTX
   4090, rather than accepting device discovery alone;
4. repeats the fixed 84-second profile with the same adapter and 28/4/4
   scheduler policy used by the CPU control;
5. compares notes, velocities, pedal/controller intervals, boundaries,
   coverage, settlement, and retained artifacts across CUDA repetitions and
   against the CPU control; and
6. exercises the accepted CUDA profile through the native unpackaged
   `workbench-v3` server if parity passes.

## Frozen Decisions

- Keep Transkun 2.0.1, its released checkpoint and configuration, source WAV,
  decoder policy, precision, and scheduler constants unchanged.
- Keep the ordinary and CPU corrected environments available; CUDA must be an
  explicit optional dependency selection suitable for a later NVIDIA model
  pack.
- Prefer wheel-bundled CUDA libraries. Do not make a developer-installed CUDA
  toolkit a runtime prerequisite unless the official wheel demonstrably
  requires it.
- Probe a candidate wheel in a disposable environment outside Git before
  changing the repository lock.
- Treat `torch.cuda.is_available()` as necessary but insufficient. Require an
  operation and model decode on device 0, and inspect the wheel's compiled
  architecture list for SM 8.9 support.
- Do not enable TF32, autocast, FP16, quantization, or a different model
  implementation during parity.
- Keep generated environments, fixture audio, profiles, telemetry, and
  benchmark output outside Git.
- Do not use WSL for any result labeled native Windows.

## Implementation Sequence

### 1. Select and prove the CUDA runtime

- Inspect current official PyTorch and uv guidance for a Windows CUDA source
  compatible with Python 3.10 and the locked Torch line.
- Install the candidate into a disposable uv environment outside the
  repository.
- Record wheel identity, installed native-library inventory, Torch CUDA build,
  device name, compute capability, compiled architecture list, and driver.
- Run allocation, arithmetic, synchronization, and a small deterministic
  comparison on the RTX 4090.
- Reject the candidate if it warns that SM 8.9 is unsupported, loads a CPU
  implementation, requires an undeclared system toolkit, or cannot execute.

### 2. Encode the dependency boundary

- Add one clearly named Windows NVIDIA extra and explicit official CUDA wheel
  index to `pyproject.toml` using uv's platform and extra-aware source
  selection.
- Preserve the ordinary environment and CPU `corrected` extra.
- Regenerate and inspect `uv.lock`, then prove frozen ordinary, CPU corrected,
  and Windows NVIDIA syncs independently.
- Add a focused regression check for the dependency-selection contract if it
  can be tested without installing GPU payloads in ordinary CI.

### 3. Run the unchanged parity profile

- Warm the model before measured repetitions.
- Reset and record Torch peak-memory statistics around measured work.
- Sample NVIDIA utilization, memory, clocks, temperature, power, and
  performance state independently of application timings.
- Run the same fixed 84-second `profile-backend` control with
  `--commit-device cuda` and retain the full profile and repetition artifacts.
- Compare the CUDA repetitions with each other and with Tactical 049's CPU
  result. Separate preparation, transfer, inference/decoding, and total warm
  service time where the existing execution boundary exposes them.

### 4. Exercise the native application

- Launch the native loopback `workbench-v3` server with the accepted CUDA
  profile.
- Replay the fixed source and verify ingest, preview, correction, Stop,
  settlement, reattachment, and artifact recovery.
- Confirm the session reports the expected profile and CUDA device provenance.
- Stop the exact launched process tree after validation.

### 5. Record the next decision

- Update the NVIDIA and Windows portability topics with the selected runtime,
  output comparison, service-time headroom, GPU footprint, application result,
  retained evidence, and unresolved gaps.
- Open hop/guard experimentation only if parity and native-server gates pass.
- Keep capture-to-event, delivery, browser paint, and human-perceived latency
  out of claims based solely on accelerated replay.

## Acceptance

This tactical completes only when:

- the CUDA runtime can be reproduced from tracked project metadata and an
  official wheel source;
- the ordinary and CPU corrected environments still resolve independently;
- the RTX 4090 executes the smoke operation and complete model decode without
  an unsupported-architecture warning;
- two CUDA repetitions are internally comparable and comparable to the CPU
  control under declared tolerances;
- every source frame settles, controller intervals remain valid, and no open
  tail remains;
- timing, peak device memory, and sampled GPU behavior are retained separately
  from output-quality evidence;
- native server replay passes with explicit CUDA profile and device
  provenance; and
- generated payloads and evidence remain outside Git.

An output-parity failure, unsupported wheel architecture, or native-DLL
failure closes the tactical as useful evidence. It does not authorize changing
model semantics or scheduler policy until the cause is isolated.

## Explicit Exclusions

- No scheduler hop, guard, context, buffer, or decoder-threshold sweep.
- No TF32, mixed precision, quantization, compilation, or model conversion.
- No MIDI2ScoreTransformer CUDA work.
- No WSL benchmark, cloud benchmark, multi-session contention test, or hosted
  cost claim.
- No physical microphone, browser-paint, or capture-to-event latency claim.
- No Tauri Windows launcher, sidecar staging, NVIDIA pack pruning, installer,
  signing, updater, or rollback channel.
- No public deployment or change to the active macOS sharing service.

## Execution Record

### Dependency and device gate

The official PyTorch CUDA 13.2 index publishes a CPython 3.10 Windows wheel
for Torch 2.13.0. The project now exposes two mutually exclusive corrected
extras:

```text
uv sync --extra corrected --frozen
uv sync --extra corrected-cu132 --frozen
```

The first retains PyPI's Windows CPU wheel. The second selects only Torch from
the explicit `https://download.pytorch.org/whl/cu132` index; unrelated
dependencies continue to resolve from PyPI. The untouched ordinary
environment contains neither Torch nor Transkun, the CPU extra reports
`2.13.0+cpu`, and the CUDA extra reports `2.13.0+cu132`. All three frozen
syncs passed in separate native Windows environments.

The CUDA wheel is self-contained for this application and did not require an
installed CUDA toolkit. Transkun also declares torchaudio even though its
2.0.1 source does not import it; the resolved torchaudio 2.11.0+cpu package
imports successfully beside CUDA Torch. This is retained dependency evidence,
not a claim that arbitrary torchaudio GPU operators have been validated.

The PyTorch release matrix does not list a separate Ada 8.9 build target for
2.13. Its wheel reports these compiled architectures:

```text
sm_75, sm_80, sm_86, sm_90, sm_100, sm_120
```

The real-device gate therefore remained decisive. Torch discovered compute
capability 8.9 and executed a synchronized 1024-by-1024 CUDA matrix product on
device 0 without an unsupported-architecture warning. The result was finite,
used the expected `cuda:0` device, and had a 0.000237 maximum absolute
difference from the CPU computation. A complete Transkun decode then passed
on the same device.

The locked CUDA development environment is 3,400.71 MiB, of which the Torch
package is 2,697.15 MiB. Its 363 DLL and PYD files total 2,909.38 MiB. This is
an upper-bound development inventory, not a proposed NVIDIA pack. It makes
model-pack pruning and compression a material later packaging task.

### Strict FP32 execution identity

Initial device inspection exposed that CUDA tensors were float32 while cuDNN
TF32 was enabled by Torch's default. The accepted control now explicitly sets
the highest float32 matmul precision and disables TF32 for both CUDA matmul and
cuDNN. No autocast, FP16, compilation, quantization, or model change was used.

Transkun and backend-profile provenance now retain:

- the local Torch build and declared float32 parameter precision;
- CUDA runtime, device index and name, compute capability, VRAM, and compiled
  architecture list; and
- the float32 matmul and two TF32 policy values.

Those fields participate in profile compatibility. A profile produced under a
different Torch, device, CUDA runtime, or precision policy falls back as stale
instead of silently selecting its old recommendation. CUDA operations are
synchronized before the model's load and inference timers stop.

### Fixed profile and output comparison

Two independent strict-FP32 CUDA profiles used the unchanged fixture,
checkpoint, adapter, two-thread worker boundary, and 28/4/4 scheduler policy.
Their results were:

| Measurement | CUDA run A | CUDA run B | Windows CPU control |
|---|---:|---:|---:|
| Warm-up wall time | 2.133 s | 2.126 s | 12.184 s |
| Measured decodes | 19 | 19 | 10 |
| Mean decode wall time | 1.005 s | 1.068 s | 13.743 s |
| Maximum decode wall time | 1.194 s | 1.228 s | 14.575 s |
| Service ratio | 0.227 | 0.242 | 1.636 |
| Recommendation | live | live | after-stop |

Run A's profile identity is
`ef40e1aabb8356f6b16eebcf0248e959b6855c663c665291c4aecc99f53eee33`;
run B's is
`56197d2912d90110d4b860be589a499b693622d0c8741c8bfeeb07f5a4745662`.
The profile identity intentionally includes timing and creation time, so the
two valid measurements have different IDs.

The first CUDA mean is 13.67 times faster than the CPU mean and the maximum is
12.21 times faster. This is warm service headroom under accelerated replay,
not capture-to-event latency. CUDA retained the four-second base hop rather
than entering the CPU run's degraded scheduling path, which is why it
performed 19 rather than 10 measured decodes.

Both independent CUDA profiles produced exactly the same normalized notes,
velocities, offsets, and controller intervals: 155/156 notes and 12/6
controller intervals across the two continuous repetitions. Their
corresponding-repetition onset and offset F1 values were 1.0 with velocity MAE
0.0. Within each continuous two-repeat profile, onset F1 was 0.939,
note-with-offset F1 was 0.682, and velocity MAE was 1.945.

Against the same-host CPU repetitions, strict CUDA produced:

| Repetition | Onset F1 at 25/50 ms | Note-with-offset F1 | Velocity MAE |
|---|---:|---:|---:|
| 1 | 0.954 | 0.876 | 0.500 |
| 2 | 0.978 | 0.920 | 0.575 |

The note path therefore passes the established 0.90 onset, 0.85 offset, and
5.0 velocity thresholds. Device output is comparable, not byte-identical.
The CPU control had 12/10 controller intervals while CUDA had 12/6; disabling
TF32 did not remove that deterministic difference. Every CUDA controller
interval was closed and both independent CUDA runs agreed exactly. This is
accepted as an isolated execution-backend sensitivity, but the missing second
repetition intervals remain explicit quality evidence. The scheduler sweep
must publish pedal/controller retention with note metrics and may not claim
CPU-identical output.

Both runs committed all 4,032,000 source frames and retained no pending offset
tail.

### GPU telemetry

The first strict-FP32 profile retained 226 `nvidia-smi` samples at 100 ms
cadence. Across model load, warm-up, and measured work:

| Signal | Minimum | Mean | Maximum |
|---|---:|---:|---:|
| GPU utilization | 0% | 27.94% | 66% |
| Used device memory | 539 MiB | 1,808.64 MiB | 2,011 MiB |
| Board power | 6.96 W | 82.64 W | 132.40 W |
| Temperature | 39 C | 43.22 C | 48 C |
| SM clock | 210 MHz | 2,043 MHz | 2,760 MHz |
| Memory clock | 405 MHz | 8,482 MHz | 10,251 MHz |

The observed used-memory increase from the 539 MiB starting sample to the
2,011 MiB peak was 1,472 MiB. This is sampled whole-device WDDM usage, not an
allocator-exact per-process peak. No out-of-memory, thermal, power, or device
reset event occurred.

### Native server gate

The native CUDA environment launched `workbench-v3` on `127.0.0.1`, selected
strict profile `ef40e1aabb83` through automatic correction, and completed the
42-second fixture replay with live correction. The homepage and capability
API returned HTTP 200.

The session accepted all 2,016,000 frames, processed 161 preview windows and
eight commit decodes, settled both horizons, and retained no pending tail or
stage error. Its CUDA commit decodes averaged 1.122 seconds and reached 2.667
seconds including the cold application path. The catalog reported 152 latest
notes; the ranged event API returned 164 latest rows. Verified MP3 audio,
complete event history, MIDI, and export-manifest artifacts were available,
and MP3 content returned 200 with the declared hash and byte count.

After stopping the exact native process tree, a second server process opened
the same workspace without replay. It recovered the completed 152-note
session and its audio, history, and MIDI catalog entries while selecting the
same CUDA profile. The restarted process tree was then stopped, and port 8016
had no remaining listener.

### Windows state publication and regression

The full media-enabled gate exposed a Windows-only state-publication race:
concurrent writers reused `.session.json.tmp`, and `os.replace` could also
briefly lose while a reader held the destination. Atomic JSON and JSONL
publication now uses unique same-directory temporary files, serializes
in-process replacement, removes abandoned temporary files, and retries a
transient Windows access denial for up to 500 ms. A concurrency test rejects
the former shared temporary-file shape, and a focused Windows storage test
passed three consecutive times.

With the installed FFmpeg directory included in the process environment, the
final migration report passed all lanes:

```text
Python:            247 passed, 13 explicit skips, 2 warnings
JavaScript:        passed
API contracts:     generation, typecheck, tests, and audit passed
Ruff:              passed
JavaScript syntax: passed
Git whitespace:    passed
```

The independent production Vite build also passed with its existing large
chunk warning. The 13 skips remain the accepted macOS desktop/service,
privileged Windows symlink, and POSIX process-signal boundaries.

Generated evidence is retained below ignored
`results/windows-native-cuda-baseline/`; the two locked probe environments and
fixture remain in `../atpiano-artifacts/`. No wheel, environment, checkpoint,
fixture, session, or telemetry output entered Git.

### Closure and next slice

The native Windows CUDA dependency, strict-FP32 note parity, warm service, and
unpackaged-server gates are established without WSL or a system CUDA toolkit.
The next bounded tactical may sweep scheduler hop and guard values while
publishing note, offset, velocity, and pedal/controller quality beside
sample-clock event latency. Wall-clock replay should precede a consentful
physical-microphone review. Windows sidecar staging and NVIDIA-pack pruning
remain separate packaging work.
