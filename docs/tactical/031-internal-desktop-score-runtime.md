# 031 — Internal Desktop Score Runtime

Master phase: 5. Early Tauri skeleton, R5 revision

Topics: `multi-tenant-hybrid-service-architecture`,
`performance-to-notation`

Status: **in progress on 2026-07-27.**

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

No implementation commits yet.
