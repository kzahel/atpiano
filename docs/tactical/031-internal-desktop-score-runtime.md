# 031 — Internal Desktop Score Runtime

Master phase: 5. Early Tauri skeleton, R5 revision

Topics: `multi-tenant-hybrid-service-architecture`,
`performance-to-notation`

Status: **implemented; score rendering was human-validated on 2026-07-28.
R5 remains open for the broader desktop boundary.**

## Entry Evidence

- Tactical 030 completed the self-contained macOS arm64 Tauri boundary and is
  held at R5.
- The user tested that application successfully and found its deliberate
  score-unavailable degradation.
- The existing ignored `results/midi2score-runtime/` installation produces
  useful score snapshots through the framework-independent score service.
- The ISMIR paper is published under CC BY 4.0, while the linked GitHub source
  and v0.0.1 checkpoint still carry no explicit license notice of their own.
- On 2026-07-27 the user explicitly authorized provisional internal testing
  on the assumption that the checkpoint follows the paper's CC BY 4.0 terms.
  This is not approval for public distribution.

## User-Visible Outcome

Produce a separate, unsigned, macOS arm64 internal-development `.app` in which
the existing **Render committed score** action runs the pinned
MIDI2ScoreTransformer CPU checkpoint locally. The score-free R5 build remains
the default and remains independently reproducible.

## Invariants

- The provisional license assumption is recorded as an internal-testing
  exception, never as confirmed upstream licensing.
- No command that creates a review or release archive includes the score
  runtime.
- Atpiano code may later use MIT, but third-party source, weights, and
  dependencies retain separate provenance and terms.
- The score process remains isolated from capture and transcription. A score
  failure cannot stop capture, review, playback, or exports.
- The existing desktop token, loopback-origin, thin-Rust, CPU-only, immutable
  bundle, and source-clock contracts remain unchanged.
- R5 remains open. This revision does not authorize Phase 6.

## Exact Implementation Scope

1. Make desktop score capability a validated handshake property instead of a
   compile-time false literal.
2. Let the desktop sidecar receive an explicit score-runtime root and report
   availability only after the pinned runtime manifest, source, checkpoint,
   and Python executable validate.
3. Add an opt-in staging mode that:
   - requires the existing ignored internal score runtime;
   - copies a relocatable standalone CPython 3.11 runtime;
   - stages the exact installed score packages, pinned upstream source, and
     checksummed v0.0.1 checkpoint;
   - records source, package, checkpoint, and provisional-license provenance;
   - removes caches, development launchers, and private absolute paths; and
   - audits native arm64 dependencies and bundle immutability.
4. Add a separate internal build command and output directory. Do not create a
   ZIP, DMG, updater payload, or other distribution artifact.
5. Exercise the packaged sidecar through golden replay, request a real score
   snapshot, validate MusicXML and alignment artifacts, and confirm that the
   ordinary score-free build still reports the capability unavailable.

## Explicit Exclusions

- No claim that MIDI2ScoreTransformer source or checkpoint licensing is
  resolved.
- No public sharing, hosted operation, release archive, signing, notarization,
  installer, updater, or model-pack publication.
- No score-model quality change, retraining, quantization, MPS execution, or
  progressive engraving.
- No Phase 6 microphone, SQLite, settings, update, or daily-use work.
- No Windows, Linux, or Intel Mac score packaging.

## Migration And Compatibility

The normal `stage`, `build`, and `audit` commands continue to reject every
score-runtime asset. New internal commands require an explicit opt-in and
write a manifest whose `internal_only` and `public_distribution` fields make
the boundary machine-readable.

The Rust shell always passes the bundled score-runtime location. A missing or
invalid directory degrades to `score_available=false`; a valid internal
runtime produces `score_available=true`. The React application continues to
consume the existing runtime capability and score-job contracts without a
desktop-specific component branch.

## Automated Validation

- Python tests cover dynamic handshake capability, score-root selection,
  internal staging provenance, ordinary-build rejection, component
  accounting, and audit behavior.
- Rust tests accept both available and unavailable score capability while
  preserving every other handshake check.
- The ordinary Python, TypeScript, frontend, and Rust validation lanes remain
  green.
- The internal `.app` passes native architecture, external-load, symlink,
  cache, package, and component-inventory audits.
- A packaged real replay settles and a subsequent score job publishes valid,
  plausible MusicXML plus a validated v2 source alignment.
- The app bundle remains byte-for-byte unchanged by launch, replay, and score
  generation.

## Manual Validation

- Launch the separate internal app and verify the local engine becomes ready.
- Complete or select a settled performance and choose **Render committed
  score**.
- Confirm the generated score renders, opens in the reader, and survives an
  app restart through retained session artifacts.
- Confirm the ordinary R5 app still gives the intentional unavailable
  message.

## Human Review Packet

Provide the internal app path, exact opt-in build command, capability and
score evidence, installed-size delta, provenance/license warning, tests,
commits, and rollback command. Ask for R5 acceptance only after the score path
has been reviewed.

## Rollback Or Disable Path

Run the ordinary score-free build. It replaces staged resources and the Tauri
bundle with the original R5 boundary and continues to reject score assets.
The internal generated app and reports remain ignored and can be discarded
without changing source sessions or the existing private score runtime.

## Execution Record

Implementation commits:

- `83d72f7` — open the internal-only policy and tactical;
- `244d366` — negotiate score capability from the validated runtime;
- `2ad8ed8` — stage, audit, and validate the opt-in score runtime;
- `0cf5b27` — redirect native-launch library caches into app data; and
- `02ea998` — apply the same cache policy to Python launch and validation
  paths.

The opt-in build command is:

```text
scripts/build-atpiano-desktop build-internal-score
```

It produced this ignored, unsigned review application and no ZIP, DMG, or
other archive:

```text
results/desktop-internal-score/Atpiano-Internal-Score.app
```

The initial Tactical 031 application contained 32,704 files and
2,361,066,073 installed bytes. Its 1,316,271,921-byte score runtime contains
standalone CPython
3.11.14, 62 installed packages, pinned MIDI2ScoreTransformer source at
`115432bda16ca16e0fec2e9465788f2ba369971f`, and the v0.0.1 checkpoint at
SHA-256
`7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`.
The runtime manifest says `internal_only=true`,
`public_distribution=false`, and `license.status=provisional-unconfirmed`.

The final packaged replay reached the exact 2,016,000-sample audio and commit
horizons with 151 closed notes, retained one MP3 and zero WAV files, and then
completed score generation in 7.61 seconds. The result contains a
12-measure, two-part MusicXML 4.0 score with 152 pitched note elements and a
valid v2 alignment mapping 131 of the 151 source notes. The MusicXML SHA-256
for this session-addressed result is
`21668c49f72563d21383cfbd42f3f0505934576ccbd18dc757b0c60e4731350f`.

The complete bundle tree SHA-256 was
`20b8ac3377008c54cb63fc3ec34463c564f7b927563e7792c5e13c130361d792`
both before and after replay and score generation. A real Tauri launch then
started the bundled sidecar with the bundled score root and passed the full
post-launch audit. That launch exposed and led to fixing Numba's initially
empty in-bundle cache directory; library caches now go to mutable app data.

The ordinary `stage` command was run last for this initial slice. It restored
the 1,035,523,314-byte score-free runtime, left no `score-runtime` directory,
and advertised `score_available=false`. The existing score-free R5 archive
remained the only review archive.

Machine-readable ignored evidence:

```text
results/desktop-internal-score/stage-report.json
results/desktop-internal-score/bundle-audit.json
results/desktop-internal-score/packaged-score-report.json
```

Final automated gates passed with 177 Python tests and Ruff, 5 Node contract
tests, 47 Vitest tests, frontend typecheck and production build, and 8 Rust
tests plus formatting and Clippy with warnings denied. The internal
application reached subjective score review. On 2026-07-28 the user confirmed
that score engraving works in the desktop app. That review exposed the
separate artifact-export gap now owned by Tactical 032. R5 remains open and
Phase 6 remains closed until explicit acceptance.
