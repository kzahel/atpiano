# Atpiano Development Guide

This guide owns source setup, primary application commands, validation, and
retained research entry points. Product-oriented installation and use belong
in the [root README](../README.md). Continuing decisions and evidence belong
in [topic documents](topics/README.md), while bounded implementation history
belongs in [tactical documents](tactical/README.md).

## Current Implementation

The shared React `workbench-v3` application is the authoritative user-facing
workspace. The v1 and v2 workbenches remain runnable as compatibility
surfaces, regression oracles, and implementation evidence. New product work
should target v3 unless it explicitly concerns an earlier prototype.

Model selection, streaming adaptation, correction scheduling, notation, and
platform acceleration remain research concerns rather than permanent
technology choices. Their current status is split across focused topics:

- [acoustic transcription latency and quality](topics/acoustic-transcription-latency-quality.md)
- [live acoustic transcription](topics/live-acoustic-transcription.md)
- [performance to notation](topics/performance-to-notation.md)
- [Linux development portability](topics/linux-development-portability.md)
- [Windows native runtime portability](topics/windows-native-runtime-portability.md)
- [NVIDIA acceleration](topics/nvidia-accelerated-low-latency-pipeline.md)
- [public desktop releases](topics/public-desktop-release.md)

## Prerequisites

Source development uses:

- Python 3.10;
- [`uv`](https://docs.astral.sh/uv/) for the locked Python environment; and
- Node.js and npm for the React application.

Rust and the platform-specific Tauri prerequisites are needed only for desktop
shell development and packaging. The
[desktop release operator runbook](desktop-release-operator-runbook.md) owns
the signed release procedure.

## Run The Primary Workspace

Install the corrected-note Python dependencies and pinned frontend
dependencies, then launch v3:

```text
uv sync --extra corrected
npm ci --prefix app
uv run atpiano workbench-v3
```

The command builds and opens the React application and uses
`results/workbench-v3/` as its local workspace by default. Select **New
session**, start the microphone, and use **Stop & settle** when finished.

The workspace keeps active capture separate from the selected historical
session. It provides synchronized recorded-audio playback, provisional and
corrected notes, piano-roll and keyboard inspection, session history,
artifacts, and recoverable deletion.

After successful settlement, new sessions retain a verified 128 kbps MP3 and
retire their temporary WAV source by default. Launch with `--retain-wav` when
lossless source should remain available for diagnosis or future
retranscription. Existing session directories are not migrated by this
policy.

## Optional Score Runtime

Engraved score snapshots are isolated from capture and are not required for
the roll, keyboard, playback, or exports. For private development experiments,
install the pinned runtime once:

```text
uv run atpiano setup-midi2score
```

This developer command downloads immediately without the acknowledgement
shown by public desktop applications. The upstream repository and checkpoint
have no confirmed license, so they must remain outside Git and must not be
bundled in a public release. See
[desktop score runtime footprint](topics/desktop-score-runtime-footprint.md)
for the full boundary.

## Native Windows CUDA Development

On a compatible native Windows NVIDIA host, install the explicit CUDA 13.2
variant, measure the host, and retain the selected backend profile:

```text
uv sync --extra corrected-cu132 --frozen
uv run --extra corrected-cu132 atpiano profile-backend `
  ..\atpiano-artifacts\musical-loop-input\input.json `
  results\backend-profile-cu132 `
  --commit-device cuda --commit-threads 2
uv run --extra corrected-cu132 atpiano workbench-v3 `
  --commit-device cuda `
  --backend-profile results\backend-profile-cu132\backend-profile.json
```

`corrected` and `corrected-cu132` are intentionally mutually exclusive. The
CUDA wheel carries its user-space runtime; the validated server does not
require a separately installed CUDA toolkit. A profile is trusted only while
its Torch build, device and runtime, precision policy, checkpoint, scheduler,
and host still match. Generate a new profile for a different host or runtime.

## Development Validation

From a fresh clone, install the locked dependencies and run the unattended
gate:

```text
uv sync --frozen
npm ci --prefix app
uv run atpiano migration-regression
npm run build --prefix app
```

`migration-regression` writes a machine-readable report below the ignored
`results/migration-regression/` directory. It covers the Python and JavaScript
tests, generated-contract drift, TypeScript, frontend tests, dependency audit,
Ruff, JavaScript syntax, and Git whitespace. The production frontend build is
a separate acceptance gate.

Retained-score rendering has a slower browser validation lane. Install the
development-only Playwright engines once:

```text
npm exec --prefix app playwright -- install chromium webkit
```

Then exercise complete, non-trashed recordings against a running authenticated
service:

```text
uv run atpiano validate-scores \
  --workspace results/workbench-v3 \
  --base-url https://atpiano.graehlarts.com \
  --browser chromium \
  --browser webkit \
  --headed
```

Use `--headless` for unattended browser execution or `--structural-only` for
the fast read-only artifact lane. Reports and failure screenshots are written
below ignored `results/score-validation/` paths. Playwright WebKit is a WebKit
compatibility engine, not automation of the installed Safari application.

Machine-dependent microphone, real Transkun, internal score-runtime, and
long-soak lanes remain explicit rather than being counted as unattended
passes.

## Retained Prototype Workbenches

### Browser Workbench v1

The first browser workbench remains available for compatibility and
transcription research:

```text
uv sync
uv run atpiano workbench
```

It binds to `127.0.0.1`, captures through the browser, runs rolling and
full-file Basic Pitch paths, and stores evidence under the ignored
`results/workbench/` directory. Its interface and constraints are recorded in
[Tactical 009](tactical/009-three-phase-unbounded-sessions.md).

### Corrected-note Workbench v2

V2 remains the corrected-note prototype and provides the local engine composed
by v3. It keeps Basic Pitch results provisional, replaces settled spans with
bounded trailing Transkun output, and stores indefinite sessions as segmented
audio plus indexed events.

```text
uv sync --extra corrected
uv run atpiano musical-fixture \
  ../atpiano-artifacts/musical-loop-input
uv run atpiano workbench-v2 \
  --replay ../atpiano-artifacts/musical-loop-input/input.json
```

Start without `--replay` to use microphone capture. The detailed interaction
and artifact contract is recorded in
[Tactical 010](tactical/010-corrected-note-workbench-v2.md).

## Benchmark And Research Commands

Generate a deterministic MIDI-derived WAV and aligned reference:

```text
uv run atpiano fixture ../atpiano-artifacts/smoke-input
```

Generate the longer musical loop used by v2 integration:

```text
uv run atpiano musical-fixture \
  ../atpiano-artifacts/musical-loop-input
```

Exercise the v2 source and segmented-storage foundation without model
inference or microphone input:

```text
uv run atpiano replay-v2 \
  ../atpiano-artifacts/musical-loop-input/input.json \
  ../atpiano-artifacts/workbench-v2-source-check \
  --repeat 2 --no-wait
```

Add `--preview` for the bounded Basic Pitch provisional lane, or install the
`corrected` extra and add `--commit` for trailing Transkun output.

Run the untouched Basic Pitch file path or replay the same samples at real
wall-clock cadence:

```text
uv run atpiano offline \
  ../atpiano-artifacts/smoke-input/input.json \
  ../atpiano-artifacts/offline
uv run atpiano replay \
  ../atpiano-artifacts/smoke-input/input.json \
  ../atpiano-artifacts/replay
uv run atpiano review ../atpiano-artifacts/replay
```

The native fixed-duration capture adapter remains available for
instrumentation experiments:

```text
uv sync --extra capture
uv run atpiano record ../atpiano-artifacts/my-piano --seconds 30
```

The `sounddevice` adapter also needs the host PortAudio shared library. On
Debian or Ubuntu, install `libportaudio2` before running `devices` or `record`.

Generated inputs, checkpoints, recordings, and run results do not belong in
Git. Each run records hashes, runtime and model versions, parameters, stage
timing, native outputs, normalized event revisions, scores, and a compact
report.

## Deployment And Operations

The authenticated family application is an on-demand macOS service proxied
through the home Pi. Its topology, security boundary, service commands, and
current operating contract live in
[Home-Hosted Family Sharing](topics/home-hosted-family-sharing.md).

Desktop release signing, publication, update routing, hashes, and acceptance
belong in the [desktop release operator runbook](desktop-release-operator-runbook.md).

## Working Principles

- Measure end-to-end latency from the audio sample clock to emitted note
  events; model inference time alone is not product latency.
- Preserve raw model output and timing evidence so post-processing can be
  compared without rerunning inference.
- Keep source timestamps separate from arrival and display timestamps.
- Treat recent acoustic events as revisable when a model needs future context.
- Compare against an offline, full-context quality ceiling before optimizing a
  streaming path.
- Keep model checkpoints, datasets, recordings, and generated benchmark
  artifacts outside Git.
