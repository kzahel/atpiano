# 055 — macOS Microphone Entitlement Repair

Topic: public-desktop-release

Status: **complete for the correction release. Signed development prompt and
physical capture passed, and the exact `0.1.2` replacement is public.**

## Incident

The installed public `0.1.1` App failed immediately after **Start microphone**
without showing a native consent prompt. The App's merged `Info.plist` did
contain `NSMicrophoneUsageDescription`, but its hardened Developer ID signature
contained no application entitlements.

The 2026-08-25 macOS unified log recorded the exact policy failure for
`com.atpiano.desktop`: microphone prompting under hardened runtime required
`com.apple.security.device.audio-input`; because it was missing, TCC disallowed
the prompt and WebKit denied `getUserMedia`.

This was an acceptance gap rather than a microphone-device or frontend defect.
The earlier Tauri tactical explicitly excluded microphone parity, the migration
matrix deferred physical Tauri microphone smoke to Phase 6, and signed-release
acceptance used the packaged WAV fixture and recording import. Browser
microphone reviews did not exercise TCC for the signed macOS application.

## Implemented Contract

- The Tauri shell has a dedicated application entitlement containing exactly
  `com.apple.security.device.audio-input = true`.
- The macOS bundle configuration names that entitlement file while retaining
  hardened runtime and the existing microphone usage description.
- Repository release validation fails when the entitlement path, exact narrow
  entitlement set, true value, `Info.plist` path, or nonempty usage description
  drifts.
- Signed-artifact validation inspects the final App signature and fails unless
  the audio-input entitlement is embedded.
- Local app-only and development-signed builds disable updater artifacts; they
  do not require production updater private keys merely to exercise packaging
  and TCC.

## Validation

- The focused Node release-contract suite passes 18 tests, including rejection
  of a missing audio entitlement, an extra camera entitlement, and a missing
  microphone usage description.
- Both entitlement and `Info.plist` sources pass `plutil -lint`; the release
  repository validator accepts the corrected `0.1.2` source identity.
- A complete arm64 development App was built with Apple Development identity
  `22WW382YN8`. Strict deep signature validation passes, hardened runtime
  remains enabled, the final signature reports
  `com.apple.security.device.audio-input = true`, and the merged bundle
  contains the expected microphone usage description.
- The signed App reached a real native macOS prompt stating that Atpiano would
  like to access the microphone and displaying the tracked local-transcription
  usage description. This directly reverses the public artifact's TCC
  `Policy disallows prompt` failure.
- After consent, the built-in `MacBook Pro Microphone` granted mono 48 kHz
  capture with the requested echo cancellation, noise suppression, and
  automatic gain controls disabled. A 16.696-second take retained all 801,408
  source frames with no missing input, render-clock gaps, repeated frames, or
  boundary jumps of at least 0.05. Stop produced a verified 268,077-byte MP3,
  a settled one-note session, MIDI/event exports, and a score snapshot.
- Exact commit `aaa608bd9e62b37af5c24e6029ae95048b44259f` was published as
  [`desktop-v0.1.2`](https://github.com/kzahel/atpiano/releases/tag/desktop-v0.1.2)
  by tagged
  [run 32890134829](https://github.com/kzahel/atpiano/actions/runs/32890134829).
  Source, Rust, signed Windows, Developer ID, hardened-runtime entitlement,
  notarization, packaged replay, updater-signature, provenance, and finalizer
  gates all passed.
- The finalizer published exactly eight non-draft, non-prerelease assets. The
  notarized DMG SHA-256 is
  `fb3f0ea1848ff36c4f3603d35bb5c15c9dc42ecbedd96814d81cffc14248deaa`;
  `SHA256SUMS` and GitHub server-side digests are public with the release.
- Production updater requests from `0.1.1` return signed `0.1.2` metadata for
  both supported platforms; requests from `0.1.2` return HTTP 204.

## Post-Publication Follow-Up

An installed `0.1.1 -> 0.1.2` acceptance may still verify that update
replacement preserves sessions, installation identity, acknowledgement, and a
compatible acquired runtime before repeating the clean-TCC microphone flow.
That follow-up is not part of the completed correction-publication gate.

The public `0.1.1` binary cannot be repaired by resetting System Settings;
only the newly signed `0.1.2` App supplies the missing entitlement. WAV and MP3
import remain the temporary recording path for users who stay on `0.1.1`.
