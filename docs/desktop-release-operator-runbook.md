# Desktop Release Operator Runbook

This is the minimal operator path for the first public Atpiano desktop proof
of concept. The release is one coordinated `desktop-v*` tag with exactly two
packages: macOS arm64 and Windows x86_64. Do not publish one platform by
itself.

## Current Boundary

As of 2026-08-23, `kzahel/atpiano` is public and has no GitHub Release. The
source tree contains the score-model notice and acquisition capability, but no
MIDI2ScoreTransformer source or checkpoint. GitHub Actions has none of the 11
required secret names configured. The production updater product remains
inactive: both the macOS arm64 and Windows x64 concrete `0.1.0` routes return
HTTP 404 `Unknown product for this hostname`.

The local Developer ID identity is valid and App Store Connect notarization
authentication succeeds. The Atpiano updater keypair is present and its public
half matches the application configuration. Private key/certificate files are
owner-readable only. The certificate/updater passwords and Azure client secret
still require attended validation before the 11 values can be uploaded.

The Windows package built and installed successfully on the Windows 11 ARM64
testbed as an x64-emulated, unsigned development package. Its real acknowledged
model acquisition, CPU MusicXML/alignment smoke, relaunch, and package
reinstall preservation pass. The exact unsigned installer is 433,446,738 bytes
with SHA-256
`a6c9fb9edc469bd6ab9cf9711f32b1e7f9a9fec181bb063f9e6f348abbef43df`.
The macOS package has an earlier signed/notarized baseline, but the exact
acquisition-capable build still needs its credentialed CI rehearsal. Neither
local artifact is a public release candidate.

## Required Actions Secrets

| Secret | Scope |
| --- | --- |
| `TAURI_SIGNING_PRIVATE_KEY` | Atpiano-only updater private key |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Atpiano updater-key password |
| `MACOS_CERTIFICATE_P12_BASE64` | Shared Developer ID certificate |
| `MACOS_CERTIFICATE_PASSWORD` | Developer ID export password |
| `MACOS_KEYCHAIN_PASSWORD` | Random temporary CI keychain password |
| `ASC_API_KEY_P8_BASE64` | Shared App Store Connect notarization key |
| `ASC_API_KEY_ID` | App Store Connect key ID |
| `ASC_API_ISSUER_ID` | App Store Connect issuer ID |
| `AZURE_CLIENT_ID` | Azure Trusted Signing application ID |
| `AZURE_TENANT_ID` | Azure tenant ID |
| `AZURE_CLIENT_SECRET` | Azure application secret value |

The workflow uses the established Azure Trusted Signing account and public
certificate profile named in `.github/workflows/desktop.yml`. It does not use
or retain an exportable Windows PFX.

Use the maintainer's canonical private desktop-signing runbook to validate all
four credential groups locally before setting anything. Override its target
repository, updater-key file, and desktop directory for Atpiano. Passwords are
entered through its hidden prompts; values never belong in command arguments,
the repository, workflow inputs, terminal logs, or release evidence.

The updater public key tracked in `app/src-tauri/tauri.conf.json` must exactly
equal the contents of the selected Atpiano `.key.pub` file before its matching
private key is uploaded.

After the guarded setup, verify names and timestamps only:

```bash
scripts/check-desktop-release-secrets
```

This checker never reads secret values and fails if any required name is
absent or if it resolves a repository other than `kzahel/atpiano`.

## Credentialed Rehearsal

Push the exact candidate commit to `main`, then run the workflow manually:

```bash
gh workflow run desktop.yml --repo kzahel/atpiano --ref main
gh run watch --repo kzahel/atpiano
```

`workflow_dispatch` builds both platforms and retains short-lived Actions
artifacts and redacted audits. It does not create a GitHub Release. Require:

- source, frontend, Python, and native Rust checks on their declared hosts;
- a signed, notarized, and stapled macOS application and DMG;
- an Authenticode-valid, trusted-timestamped Windows app and NSIS installer
  signed by the `Kyle Graehl` publisher through Azure Trusted Signing;
- updater archives and detached signatures for both exact targets;
- independent runtime audits with no MIDI2ScoreTransformer source/checkpoint;
- the final packaged education/research notice and acknowledgement gate on
  both installed applications; and
- cleanup with no decoded key/certificate files or leaked secret values.

Download and inspect the rehearsal artifacts before authorizing a tag. A
successful rehearsal proves build/signing readiness, not the production
updater or a public release.

Before treating the rehearsal as the exact candidate, repeat the real model
acquisition and score check on macOS, exercise the complete packaged score
request and removal paths on both systems, and run the ordinary Windows
import/replay/export matrix on a native x64 host. The Windows x64-on-ARM64
testbed proves correctness boundaries but is not native x64 timing evidence.

## Tag And Draft-First Publication

Creating or pushing a `desktop-v*` tag is a publication action and requires an
explicit final decision after rehearsal review. The version must match
`app/src-tauri/tauri.conf.json` and the changelog.

On a tag, the macOS and Windows jobs upload only internal Actions artifacts.
The finalizer then:

1. flattens both validated artifact sets and refuses duplicate names;
2. creates or reuses only a draft GitHub Release;
3. creates one signed `latest.json` with exactly `darwin-aarch64` and
   `windows-x86_64`;
4. uploads the exact package matrix, creates `SHA256SUMS`, and refreshes
   GitHub's asset digests;
5. validates the still-private draft and attests release files; and
6. publishes only after every required job and validation succeeds.

Any missing credential, platform, signature, hash, source archive, or expected
asset fails closed. The finalizer refuses to replace an already-public release.

## Remaining Acceptance After `0.1.0`

Auto-update is implemented in the applications and release metadata, but it is
not accepted until the production product route is deliberately activated and
an installed `0.1.0 -> 0.1.1` campaign passes on both operating systems. That
campaign must preserve sessions, installation identity, acknowledgement, and
the compatible externally acquired score runtime without downloading the
model again.

Before the first tag, also close or explicitly waive the current Windows media
corresponding-source attachment gap: the tracked Windows manifest pins the
BtbN build repository and FFmpeg commits, while the existing attached source
archive was produced for the macOS FFmpeg/LAME build. Do not describe that one
archive as exact corresponding source for both binaries until the Windows
source bundle is reconciled.
