# Product Migration Baseline

Status: frozen for Phase 1 on 2026-07-26.

This reference inventories the behavior that must remain observable while the
hosted-plus-Tauri product is introduced. It complements the normalized
machine fixtures in
[`tests/fixtures/migration/legacy-contracts.json`](../tests/fixtures/migration/legacy-contracts.json).
The current applications are regression oracles, not the package structure or
wire vocabulary of the new product.

## Reproducible Environment

The tracked project requires Python 3.10 and is installed with:

```text
uv sync
```

The ordinary environment includes Basic Pitch 0.4.0 and Partitura 1.9.0. The
optional corrected lane adds Transkun 2.0.1 and its PyTorch dependency:

```text
uv sync --extra corrected
```

The optional native microphone utility uses:

```text
uv sync --extra capture
```

The measured development platform is macOS arm64. Core ML behavior is
platform-specific; CPU is the known-good Transkun and internal-score provider.
Accelerator throughput does not replace source-clock or end-to-end latency
evidence.

The browser score views load the pinned OpenSheetMusicDisplay 1.9.9 bundle
from a CDN. An unavailable CDN may prevent rendering but must not hide or
invalidate the MusicXML artifact.

## One Automated Regression Command

Run:

```text
uv run atpiano migration-regression
```

The command writes a timestamped
`results/migration-regression/<timestamp>/report.json`, returns nonzero on a
required failure, and runs:

- all Python tests, including normalized legacy route fixtures;
- the v1 live-view and v2 timeline JavaScript tests;
- repository-wide Ruff checks;
- JavaScript syntax checks for application and test files; and
- Git whitespace checks.

The report names physical microphone, real corrected-model, internal licensed
score, and long-soak lanes as not run. They are not silently counted as
passing automation.

## Frozen Inputs

### Aligned musical fixture

Generate the 16-bar, 42-second control with:

```text
uv run atpiano musical-fixture \
  ../atpiano-artifacts/musical-loop-input
```

The bytes are generated outside Git and frozen by tracked code plus:

```text
input ID: deterministic-musical-loop-v1
audio:    0eab5d787cb482735dc840daaed2abfb6d00ad6ff7a7058fdd217522905aaa89
MIDI:     d24635a3f75d83dd8ff40e9513475dc43064e1dbb29fd836345f2057da0ec7d9
format:   mono PCM16 WAV, 48,000 Hz, 2,016,000 frames
content:  198 notes, 17 control intervals, chords, melody, Alberti bass,
          sustain, soft pedal, silence, bass, and treble
```

It supplies aligned note and controller evidence. Replay repetitions use one
continuous source sample clock and the same corrected-session engine used by
microphone capture.

### Target-piano reference

[`oracle/README.md`](../oracle/README.md) identifies the unedited lossless
34.688-second target-piano WAV by SHA-256
`3d747d653d8f7a30c2e3261c85b8b9207959a7e00e8b009aac5fd969247f6f47`.
It has no aligned MIDI or score, so it is an operational, listening, and
subjective readability reference rather than accuracy ground truth.

## Supported Behavior Inventory

### v1 `workbench`

The supported command remains:

```text
uv run atpiano workbench
```

The regression boundary includes:

- loopback-only Host and Origin enforcement;
- browser AudioWorklet PCM16 capture with source sample indices;
- bounded two-minute capture, Start, Stop, exact WAV preservation, and
  restart-readable jobs;
- strict-onset rolling Basic Pitch feedback, revisions, retractions,
  room-noise calibration, and separate timing stages;
- automatic untouched full-file Basic Pitch processing after Stop;
- job status, normalized events, report, MIDI, piano roll, experimental
  notation variants, and imported-oracle artifacts; and
- the existing `atpiano.workbench-config.v1` route shape.

Its two-minute limit, large framework-free frontend, experimental sequential
staff, rough fixed-tempo glyphs, and server composition are prototype
properties. They stay runnable but are not durable product architecture.

### v2 `workbench-v2`

The supported deterministic and microphone commands remain:

```text
uv run atpiano workbench-v2 \
  --replay ../atpiano-artifacts/musical-loop-input/input.json

uv run atpiano workbench-v2
```

The regression boundary includes:

- replay and microphone blocks entering the same source-sample-indexed
  `CorrectedSession`;
- a bounded PCM ring, segmented lossless audio and append-only events,
  materialized range index, monotonic provisional and commit horizons, and
  explicit source boundaries;
- optional Basic Pitch preview and trailing Transkun correction lanes;
- provisional, committed, revised, retracted, note, sustain, and soft-pedal
  products;
- Stop tail flush, complete or failed manifests, restart recovery of the
  latest valid session, and stale-active recovery as failed;
- visible-range event reads capped at 120 seconds;
- committed MIDI, complete revision-history JSONL, export manifests, and
  on-demand internal score snapshots;
- independent timeline, keyboard, and score views; and
- the normalized current route shapes frozen by the legacy fixture.

The existing `/api/session`, `/api/events`, `/api/score`, and unqualified
artifact routes resolve through one server-global latest/current session.
That ambiguity is frozen only as compatibility behavior. Phase 2 introduces
explicit session-addressed contracts; selection must never retarget capture
or a job.

## Manual And Machine-Dependent Lanes

### Physical microphone smoke

1. Run `uv run atpiano workbench-v2`.
2. Grant microphone permission and press **Start microphone**.
3. Confirm the page reaches active capture and the source head advances.
4. Play silence, isolated notes, repeated notes, a sustained chord, bass,
   treble, and pedal.
5. Press **Stop** and confirm history JSONL and MIDI download.
6. Restart the command with the same workspace and confirm the completed
   session, event range, exports, and score state remain readable.

This is consentful subjective evidence. Automation sends exact synthetic PCM
through the same WebSocket protocol but never opens an ambient microphone.

### Real corrected replay

```text
uv run atpiano replay-v2 \
  ../atpiano-artifacts/musical-loop-input/input.json \
  ../atpiano-artifacts/migration-corrected \
  --no-wait --preview --commit
```

This requires `uv sync --extra corrected` and cached model assets. Compare
normalized identities, horizons, pedal intervals, and exports with the
completed tactical evidence; do not treat an empty successful process as a
valid result.

### Internal score snapshot

`uv run atpiano setup-midi2score` installs the ignored Python 3.11 runtime,
pinned upstream commit, and 389,829,880-byte checkpoint. Its checkpoint hash
is
`7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`.
The upstream repository has no confirmed license. Internal private research is
accepted, but public operation, desktop bundling, or distribution is blocked.

### Longevity

Fake-model tests cover an eight-hour preview source clock and a 30-minute
two-lane source clock while asserting bounded state. Multi-hour real-model
resource use, browser reconnect, and physical-device behavior remain separate
evidence.

## Deliberate Non-Parity

The migration should not preserve these as permanent product requirements:

- the v1 two-minute resource limit;
- server-global current-session targeting or unqualified durable routes;
- exact HTML, CSS, and proof-of-concept file composition;
- automatic selection of the newest session without a visible historical
  label;
- a score converter whose rights do not permit the target deployment; or
- implementation quirks that do not affect normalized events, artifacts,
  sample clocks, or user-visible behavior.

No current useful behavior was found whose disposition is ambiguous enough to
require an R1 product decision. Phase 2 may therefore proceed while keeping
both current applications and compatibility routes intact.
