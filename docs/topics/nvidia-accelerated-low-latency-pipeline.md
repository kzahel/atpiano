# NVIDIA-Accelerated Low-Latency Pipeline

Topic: nvidia-accelerated-low-latency-pipeline

Status: **proposed reproducible native Windows RTX 4090 experiment as of
2026-07-31.** No Atpiano CUDA result has been recorded yet. The first intended
host is the user-controlled Windows desktop with an NVIDIA RTX 4090. Native
Windows is now the authoritative result so the measured server and model
runtime can feed future Windows desktop packaging. WSL2 remains a labeled
Linux reference and fallback, not the product runtime. Transkun already
exposes a CUDA-compatible adapter boundary in Atpiano. The internal score
converter's upstream code appears CUDA-aware, but Atpiano deliberately forces
that subprocess to CPU and has not validated NVIDIA output. The existing
Linux Basic Pitch preview remains a CPU TFLite path. This topic authorizes
research and documentation, not a public hosted product or general
distribution of the internal score model.

## Intent

Use the 4090 host to establish the performance ceiling of the current
Transkun-to-score pipeline before optimizing around the slower CPU machines or
choosing rented infrastructure.

The experiment should answer:

- how quickly current Transkun windows execute on CUDA, cold and warm;
- how much of corrected-note latency remains after inference becomes cheap;
- whether shorter scheduling hops and right-edge guards preserve the ordinary
  Transkun result;
- whether MIDI2ScoreTransformer produces a valid, equivalent score on CUDA;
- whether transcription and score generation can safely share one GPU;
- what the full capture-to-visible and score-request-to-render latency is; and
- what one active or continuously warm hosted GPU would cost before other
  service expenses.

This is a ceiling experiment, not a claim that the current offline models
become causal when given faster hardware. Algorithmic context, commit policy,
score stability, transport, process startup, and rendering remain separate
latency stages.

## Scope And Relationship

This topic owns the cross-stage execution experiment:

- reproducible CPU-versus-CUDA profiles on one fixed host and input;
- CUDA device selection and provenance at model-adapter boundaries;
- Transkun buffer, hop, and right-edge-guard sweeps after baseline parity;
- cold start, warm inference, GPU memory, utilization, and contention evidence;
- simultaneous Transkun and score-job scheduling on one NVIDIA device;
- local, LAN, and eventual hosted end-to-end latency comparisons; and
- raw accelerator rental-cost scenarios and concurrency assumptions.

[`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md)
continues to own model quality, native output, window reconciliation, and the
general capture-to-event measurement contract.
[`live-acoustic-transcription.md`](live-acoustic-transcription.md) continues
to own browser capture, the audio sample clock, event lifecycle, delivery, and
paint acknowledgement.
[`performance-to-notation.md`](performance-to-notation.md) continues to own
score semantics, MusicXML, source alignment, and converter quality.
[`multi-tenant-hybrid-service-architecture.md`](multi-tenant-hybrid-service-architecture.md)
continues to own any eventual hosted worker, tenant, persistence, security,
and deployment design.
[`linux-development-portability.md`](linux-development-portability.md) owns
ordinary Linux compatibility and retains the existing CPU evidence.
[`windows-native-runtime-portability.md`](windows-native-runtime-portability.md)
owns the native Windows dependency environment, unpackaged local-server
baseline, operating-system behavior, and handoff to later desktop packaging.

This topic does not select a permanent model, authorize a cloud launch, relax
the audio sample-clock contract, or change the private-use-only status of
MIDI2ScoreTransformer.

## Known Starting Point

### Native Windows host and runtime boundary

The intended host reports an Intel Core i7-13700KF, approximately 96 GiB RAM,
an RTX 4090 with 24,564 MiB VRAM, NVIDIA driver 610.88, and a 450 W GPU power
limit. Windows and the installed Ubuntu WSL2 distro both see the GPU, but no
native Windows Atpiano CUDA result exists.

The experiment now starts with native Windows Python and model processes. The
first application target is the unpackaged `workbench-v3` local server and a
normal Windows browser, not the currently macOS-only Tauri bundle. This keeps
the server, model adapters, model/device provenance, workspace, and frontend
contracts aligned with a future native Windows sidecar without making desktop
packaging a prerequisite for CUDA measurement.

The native environment is not ready yet. The project requires Python 3.10,
while inspection found Python 3.13, no `uv`, and no repository environment on
the Windows path. The current lock also has no Windows wheel for
`tflite-runtime` 2.14.0. Resolve that Basic Pitch runtime gap through the
bounded Windows portability work before claiming an ordinary application
baseline. Do not substitute a different model or decoder silently. The
Windows portability topic owns that bring-up and its parity evidence.

### Basic Pitch preview

On x86_64 Linux, Basic Pitch 0.4.0 currently uses its packaged TFLite artifact
on CPU. In the isolated Linux browser rerun, 236 preview jobs had an 87.5 ms
maximum execution time and the provisional horizon ended 1.064 seconds behind
the audio head. The earlier Apple target-take replay measured
source-onset-to-first-server-emission at 0.428 seconds p50 and 1.649 seconds
p95.

This lane is already fast enough to remain the provisional control for the
first NVIDIA experiment. Moving it to ONNX Runtime CUDA is a separate model
conversion and parity question and should not be mixed into Transkun
bring-up. Its roughly two-second model window, decoder, edge guards, and
commit horizon also mean that faster inference would not remove all preview
latency.

### Transkun corrected-note lane

The current lane uses:

```text
outer buffer:       28 seconds
base source hop:     4 seconds
maximum source hop:  8 seconds
right-edge guard:    4 seconds
minimum context:    16 seconds
```

The fixed 42-second musical fixture produced eight M4 Pro CPU decodes with
2.807 seconds mean and 3.105 seconds maximum inference. The isolated
two-thread Linux CPU profile used 84 seconds of source and produced ten
decodes with 18.024 seconds mean and 19.491 seconds maximum wall time. The
former could sustain the four-second scheduler; the latter correctly selected
after-Stop correction.

Atpiano's `TranskunCommitModel` already accepts a device string, loads the
checkpoint with that device, moves the model and input tensor to it, and
records it in model provenance. The CLI already exposes
`--commit-device`. Transkun upstream also documents `--device cuda`. The
first CUDA result should therefore require environment validation and
measurement, not a model rewrite.

Faster inference does not by itself eliminate the current latency floor. A
four-second hop plus a four-second right-edge guard can leave an onset several
seconds behind the capture head before the next decode publishes it. CUDA
first establishes spare compute capacity; a later controlled scheduler sweep
tests whether that capacity can buy lower event latency without losing model
quality.

### MIDI2ScoreTransformer

The current internal score path freezes a complete committed prefix and starts
an isolated Python 3.11 subprocess for each request. On CPU, an 84-second,
311-note snapshot produced valid 19-measure MusicXML in 4.058 seconds. The
released checkpoint is 389,829,880 bytes.

Upstream inference:

- declares CUDA when `torch.cuda.is_available()`;
- transfers token inputs to `model.device`;
- uses autocast on overlapping chunks; and
- returns generated tokens to CPU for post-processing.

Atpiano intentionally overrides that behavior:

- checkpoint loading uses `map_location="cpu"`;
- the model is moved to `cpu`;
- the adapter reports `device: cpu`; and
- the score subprocess receives an empty `CUDA_VISIBLE_DEVICES`.

CUDA score generation is therefore plausible but unproved. It needs an
explicit, default-CPU device option and validation, not removal of the CPU
guard without evidence. The first comparison must distinguish full FP32 CUDA
from upstream CUDA autocast because greedy autoregressive generation can turn
small numeric differences into different score tokens. Exact XML bytes are a
useful observation, but semantic score and source-alignment validation remain
the acceptance boundary.

The current per-request subprocess also reloads the checkpoint. Separately
measure interpreter and model load, tokenization, model generation,
post-processing, MusicXML serialization, and browser rendering. A persistent
warm score worker may matter as much as raw GPU inference, but it would change
the current failure-isolation and lifecycle contract and is not part of the
first device-enablement step.

### One GPU For Both Models

The packaged Transkun checkpoint is about 56 MB and the score checkpoint is
about 390 MB, so stored parameter size alone does not suggest that a 24 GB
4090 is too small. That is not a VRAM claim: activations, attention state,
CUDA context, allocator caching, and concurrent processes must be measured.

Start with the models separately. After both have independent warm CUDA
results, run them concurrently and record:

- peak and steady GPU memory per process;
- Transkun p50, p95, and maximum decode time with and without a score job;
- score generation time with and without live correction;
- capture ingest, preview scheduling, and commit queue progress;
- CUDA out-of-memory or allocator behavior; and
- whether output changes under contention.

Correction owns the fresher user-facing deadline. A future resource
coordinator should prioritize capture and correction over opportunistic score
refresh. Do not assume that two independent CUDA processes will schedule with
acceptable tail latency merely because both fit in memory.

## Latency Hypotheses, Not Promises

The existing project bands remain useful:

- **responsive:** usually visible within 250 ms;
- **live feedback:** usually visible within 1 second; and
- **delayed live:** usually visible within 3 seconds.

For this experiment:

- Basic Pitch remains the immediate provisional onset lane;
- corrected Transkun output should be measured against all three bands after
  the scheduler sweep;
- readable score refresh is measured separately from corrected-note delivery;
  and
- a result must not be called responsive merely because inference is below
  250 ms.

The strongest plausible outcome for the current models is a fast provisional
display, corrected notes trailing by a small number of seconds, and a score
refresh that completes quickly after a musically stable prefix is available.
Sub-250-ms stable Transkun output is not an experiment assumption because the
model is non-causal and decodes whole note intervals.

Continuous engraving is also not created by a fast GPU. The current score
model recomputes a bounded complete prefix. Stable progressive notation still
needs musical chunks, overlap, reconciliation, barline ownership, and a
monotonic engraving horizon. Until that contract exists, score generation
should remain explicit or phrase-oriented rather than refreshing after every
note.

## Reproducible Experiment Sequence

### 1. Record the host

Use native 64-bit Windows for the authoritative result. This is a deliberate
change from the earlier Linux-first proposal: the immediate product-facing
goal is a packaging-aligned Windows local-server runtime, even though the
current accepted Tauri artifact remains macOS arm64 only. Establish native
dependency and CPU parity before measuring CUDA.

Use Ubuntu under WSL2 only as a separately labeled reference or when isolating
a native Windows failure. A WSL result does not satisfy the Windows runtime or
packaging-alignment gate. If a WSL comparison is needed, keep its checkout and
benchmark outputs in the Linux filesystem rather than `/mnt/c`, and validate
browser microphone and host-network behavior separately.

Record at least:

- Windows edition/build and filesystem location, or the kernel, distro, and
  filesystem location for a labeled WSL control;
- CPU model, physical/logical core count, RAM, and power policy;
- exact RTX model, VRAM, VBIOS if available, and power limit;
- NVIDIA driver, reported CUDA runtime, and `nvidia-smi` output;
- Python, `uv`, Torch, Transkun, and Atpiano revisions;
- `torch.version.cuda`, `torch.cuda.is_available()`, device name, and compute
  capability;
- whether the display also loads the same GPU; and
- background load and temperature before each measured lane.

For any WSL control, do not install a Linux display driver inside WSL. Use the
Windows NVIDIA driver exposed to WSL, following NVIDIA's CUDA-on-WSL guidance.

### 2. Generate the fixed input

From the repository revision being tested:

```text
uv sync --extra corrected --frozen
uv run atpiano musical-fixture `
  ..\atpiano-artifacts\musical-loop-input
```

Verify the fixture hashes already recorded by the acoustic-transcription
topic:

```text
WAV:
0eab5d787cb482735dc840daaed2abfb6d00ad6ff7a7058fdd217522905aaa89

MIDI:
d24635a3f75d83dd8ff40e9513475dc43064e1dbb29fd836345f2057da0ec7d9
```

Use deterministic replay before microphone capture. Do not use an unrelated
audio file for the first CPU/CUDA comparison.

### 3. Establish CPU And CUDA Transkun Controls

Run separate, initially empty output directories:

```text
uv run atpiano profile-backend `
  ..\atpiano-artifacts\musical-loop-input\input.json `
  results\backend-profile-rtx4090-windows-cpu `
  --commit-device cpu --commit-threads 2

uv run atpiano profile-backend `
  ..\atpiano-artifacts\musical-loop-input\input.json `
  results\backend-profile-rtx4090-windows-cuda `
  --commit-device cuda --commit-threads 2
```

Retain both `backend-profile.json`, `measurement.json`, session manifests,
decode rows, model provenance, events, MIDI, and pedal artifacts. Report
model load separately from the unmeasured warm-up and measured decodes.

Compare:

- source and fixture identity;
- native and normalized note/pedal counts;
- onset and offset agreement at existing project tolerances;
- final commit coverage and pending tails;
- cold load, warm-up, per-decode distribution, service ratio, and mode
  recommendation;
- CPU load and resampling time;
- GPU utilization, clock, power, temperature, and peak VRAM; and
- repeated-run variance.

A faster CUDA run with unexplained output loss is a failed baseline, not a
scheduler-optimization opportunity.

### 4. Validate The Existing Scheduler End To End

Use the measured native Windows CUDA profile with the existing 28/4/4 policy
before changing any window parameters. Exercise accelerated replay,
wall-clock replay, and the unpackaged native Windows `workbench-v3` server
through a normal Windows browser. Confirm:

- continuous PCM ingest;
- prompt Stop acknowledgement and durable settlement;
- Basic Pitch responsiveness during Transkun work;
- correction-mode selection from the matching CUDA profile;
- complete commit-to-audio-head coverage;
- browser delivery and paint acknowledgements; and
- reload recovery.

This separates device enablement from scheduling research and preserves a
direct comparison with the CPU evidence.

### 5. Sweep Hop And Guard Without Shortening Context First

Only after the ordinary CUDA lane passes, retain the 28-second outer buffer
and 16-second minimum context while testing a bounded matrix such as:

```text
base hop:         4, 2, 1, 0.5 seconds
right-edge guard: 4, 2, 1 seconds
```

Reject combinations whose decode service ratio cannot retain headroom or whose
quality falls outside a declared tolerance against the ordinary full-context
control. Record compute duty, redundant recomputation, revision/retraction
rate, commit latency, and edge-specific errors. The existing single-take
simulation suggested that a two-second guard may be viable, but it is not a
selection and must be repeated through the real CUDA lane.

Do not shorten Transkun's trained internal context merely to obtain an
attractive latency number. Existing evidence shows severe recall loss under
naive short-context execution.

### 6. Add An Opt-In CUDA Score Device

Open a bounded tactical before changing the score runtime. Preserve CPU as the
default and carry the selected device through:

- CLI or application configuration;
- runtime manifest and producer provenance;
- subprocess environment;
- checkpoint loading and model transfer;
- success and failure artifacts; and
- score-job compatibility fingerprints if device affects semantics.

Run CPU, CUDA FP32, and any upstream-style CUDA-autocast candidate against the
same frozen score inputs. Validate:

- nonempty baseline and automatic MusicXML;
- structural score summary;
- source-to-score monotonic exact-pitch alignment;
- mapped, unmatched, and inserted note counts;
- score token and MusicXML differences;
- cold and warm stage timing;
- repeatability;
- peak VRAM; and
- failure isolation when CUDA is unavailable or exhausted.

Do not generalize the earlier MPS empty-score result to CUDA, and do not treat
upstream CUDA-aware code as proof that the pinned checkpoint produces an
acceptable Atpiano artifact on NVIDIA.

### 7. Measure Concurrent And Human Paths

After the isolated lanes pass:

1. run Transkun alone;
2. run score generation alone;
3. trigger a score job during live Transkun correction;
4. repeat with GPU correction prioritized or score work serialized;
5. replay at wall-clock cadence through the browser;
6. perform a consentful target-piano microphone session; and
7. compare local browser, LAN browser, and any later remote-host path.

The audio sample clock remains the source timeline throughout. Report
capture-to-event separately from score-request-to-artifact and
artifact-to-browser-render time.

## Required Timing And Quality Record

For corrected notes, retain at least:

1. device/replay buffering;
2. browser-to-host transport and receive buffering;
3. resampling and feature preparation;
4. future audio and right-edge-guard wait;
5. hop and worker-queue wait;
6. host-to-device transfer;
7. model inference;
8. semi-CRF decoding and event normalization;
9. overlap reconciliation and commit;
10. server delivery; and
11. browser paint acknowledgement.

For score jobs, retain at least:

1. committed-prefix freeze and MIDI/token input generation;
2. queue wait behind correction;
3. interpreter and process startup;
4. checkpoint load and device transfer;
5. tokenization;
6. autoregressive generation;
7. score post-processing and alignment;
8. MusicXML serialization and validation;
9. artifact delivery; and
10. browser parsing, layout, and paint.

Every summary needs cold and warmed distributions, p50, p95, maximum, source
duration, note count, checkpoint and code identity, numeric precision, and
device provenance. Throughput or real-time factor alone is insufficient.

## Hosted Cost Starting Point

As of 2026-07-29, RunPod's public RTX 4090 page advertises approximately:

```text
Community Cloud: USD 0.34 per GPU-hour
Secure Cloud:    USD 0.69 per GPU-hour
```

These are discovery prices, not an Atpiano vendor selection or durable quote.
At those rates, raw dedicated GPU time is approximately:

| Allocation | USD 0.34/hour | USD 0.69/hour |
|---|---:|---:|
| 10 active minutes | 0.06 | 0.12 |
| 30 active minutes | 0.17 | 0.35 |
| 1 active hour | 0.34 | 0.69 |
| 30 days continuously warm | 244.80 | 496.80 |

The useful product formula is:

```text
raw GPU cost per session =
  hourly GPU rate
  * allocated GPU-seconds / 3600
  / safely multiplexed concurrent sessions
```

Concurrency is unknown until the contention experiment. A low-latency tier
may also pay for idle warm capacity rather than only active inference.

Raw GPU time excludes CPU and RAM, persistent storage, artifact backups,
network egress, TLS and ingress infrastructure, monitoring, support, taxes,
regional capacity, failed work, and any minimum or stopped-volume charges.
Community marketplace availability and security posture also must not be
treated as equivalent to a managed production host. Recheck vendor prices and
terms when a hosted tactical begins.

Atpiano's 48 kHz mono PCM16 capture is about 96,000 bytes per second before
protocol overhead. Bandwidth is modest, but network round-trip time, jitter,
buffering, reconnects, regional placement, and warm-worker acquisition all
belong in end-to-end latency and reliability measurements.

Official starting references:

- [Transkun repository and CUDA CLI](https://github.com/yujia-yan/transkun)
- [Pinned MIDI2ScoreTransformer repository](https://github.com/TimFelixBeyer/MIDI2ScoreTransformer)
- [Pinned upstream inference utilities](https://raw.githubusercontent.com/TimFelixBeyer/MIDI2ScoreTransformer/115432bda16ca16e0fec2e9465788f2ba369971f/midi2scoretransformer/utils.py)
- [PyTorch local CUDA installation](https://pytorch.org/get-started/locally/)
- [NVIDIA CUDA on WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/)
- [RunPod RTX 4090 pricing page](https://www.runpod.io/gpu-models/rtx-4090)

## Product And License Gates

Transkun is MIT-licensed and is the technically and legally credible first
hosted-model candidate, subject to the normal checkpoint, dependency, privacy,
and service review.

The pinned MIDI2ScoreTransformer repository and released checkpoint still
lack confirmed notices that authorize general hosted or commercial use.
Current Atpiano policy permits private internal experimentation only. CUDA
research may proceed on the user's machine, but no cost result or successful
benchmark authorizes offering that converter in a paid or public service.
Resolve rights or replace the converter before such a tier.

Recorded piano audio, especially child and family sessions, remains private by
default. Any remote experiment must state what audio leaves the device, the
host and region that receive it, retention and deletion behavior, operator
access, and whether a marketplace provider can access the workload.

## Decision Gates

Advance in this order:

1. **CUDA environment:** Torch sees the 4090 and the frozen fixture runs.
2. **Transkun parity:** CUDA produces a valid comparable note and pedal result.
3. **Existing-policy operation:** the current scheduler preserves live ingest,
   preview, Stop, settlement, and recovery.
4. **Latency frontier:** hop/guard sweeps publish quality and end-to-end latency
   together.
5. **Score CUDA parity:** opt-in GPU score output passes semantic and alignment
   validation.
6. **Concurrency:** simultaneous correction and scoring have measured memory,
   queue, and tail-latency behavior.
7. **Human review:** a real target-piano browser session feels usefully more
   interactive.
8. **Hosted replication:** a rented device reproduces the local result with
   transport, cold-start, privacy, reliability, and full cost included.

Failure at one gate is useful evidence. It should update this topic and the
owning model or notation topic rather than being hidden by proceeding to a
more complicated deployment.

## First 4090 Session Handoff

A new development session on the 4090 machine should:

1. read this topic plus the linked Windows portability, acoustic, live,
   notation, Linux, and architecture topics;
2. inspect the native Windows dependency and CUDA environment without changing
   model behavior;
3. create the next available bounded tactical for the native Windows runtime
   and device profile;
4. establish the native Python 3.10 environment and resolve the Basic Pitch
   runtime gap with parity evidence;
5. generate and hash the fixed musical fixture;
6. run native CPU controls before the two CPU/CUDA `profile-backend` controls
   above;
7. compare artifacts and timing before changing any scheduler constant;
8. validate the unpackaged native Windows local server before opening desktop
   packaging work;
9. update this topic and the Windows portability topic with the host identity,
   commands, retained evidence, result, gaps, and recommended next step; and
10. keep model checkpoints, generated audio, profiles, and benchmark outputs
    outside Git.

The first session should not begin with Tauri packaging or by converting every
stage to CUDA. Its smallest useful outcome is a reproducible answer to: **Does
current Transkun 2.0.1 in the native Windows server runtime on this RTX 4090
preserve the baseline result, and how much warm decode headroom does it create
under the existing 28/4/4 policy?**

## Open Questions

- What fraction of Transkun's warm wall time is GPU work versus resampling,
  device transfer, semi-CRF decoding, and Python post-processing?
- How closely do native Windows and the optional WSL2 reference agree on model
  output and stage timing when source, model, device, and scheduler are fixed?
- Does CUDA change note, velocity, pedal, or boundary output under the current
  FP32 path?
- How low can hop and guard go before window-edge quality or compute duty
  becomes unacceptable?
- Does a persistent warm Transkun worker stay loaded without affecting the
  desktop display or other applications using the 4090?
- Does MIDI2ScoreTransformer require FP32 for semantic parity, or is CUDA
  autocast stable on the retained score corpus?
- Is persistent score-worker startup reduction more valuable than CUDA
  generation?
- Can one 4090 serve multiple live sessions while retaining p95 correction
  and score latency, or is one active premium session per device the honest
  starting capacity?
- For remote users, when do regional transport and warm-capacity acquisition
  dominate the locally measured compute improvement?
