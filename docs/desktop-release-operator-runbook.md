# Desktop Release Operator Runbook

This is the minimal operator path for the first public Atpiano desktop proof
of concept. The release is one coordinated `desktop-v*` tag with exactly two
packages: macOS arm64 and Windows x86_64. Do not publish one platform by
itself.

## Current Boundary

As of 2026-08-24, `kzahel/atpiano` is public and has no declared Atpiano
source license. The public/latest
[`desktop-v0.1.1`](https://github.com/kzahel/atpiano/releases/tag/desktop-v0.1.1)
release contains signed macOS arm64 and Windows x86_64 CPU applications. Both
contain the score-model acknowledgement and acquisition capability but no
MIDI2ScoreTransformer source or checkpoint.

All 11 required GitHub Actions secret names were configured, independently
verified, and exercised. The credentialed
[two-platform rehearsal](https://github.com/kzahel/atpiano/actions/runs/32666483577)
passed on exact candidate commit
`ed76f74686981990ce230679ccae9af19dfd61f2`. The
[tagged run](https://github.com/kzahel/atpiano/actions/runs/32669326956)
produced and attested both platform sets from that same commit. Private
credential values remain outside Git and release evidence.

The exact `0.1.1` candidate commit `66a82e2d4d87795c79ef286cb5f9709adb13e6c2`
passed credentialed rehearsal
[32703066998](https://github.com/kzahel/atpiano/actions/runs/32703066998)
and tagged publication
[32707274179](https://github.com/kzahel/atpiano/actions/runs/32707274179).
Production update routing is active. Public `darwin/aarch64` and
`windows/x86_64` requests from version `0.1.0` return signed `0.1.1` metadata;
requests from `0.1.1` return HTTP 204. Installed old-to-new acceptance remains
open until both applications complete replacement and persistence checks.

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

For `0.1.0`, rehearsal run
[`32666483577`](https://github.com/kzahel/atpiano/actions/runs/32666483577)
passed both signed platform jobs at candidate commit `ed76f74`. Its updater
signatures verified against the embedded public key; the DMG passed signing,
stapler, and Gatekeeper checks; and the Windows installer passed Azure Trusted
Signing, Authenticode, and Microsoft trusted-timestamp verification.

For `0.1.0`, the maintainer explicitly accepted proof-of-concept publication
before the real macOS acquisition, complete packaged score/removal paths, and
ordinary native-x64 Windows replay matrix were complete. That was the truthful
publication boundary; later macOS acquisition/score evidence is recorded
separately, while removal and broader Windows work remain. The Windows
x64-on-ARM64 testbed proves correctness boundaries but is not native x64 timing
evidence.

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

The first tag exposed one Tauri v2 filename drift after both platform jobs
passed: the finalizer expected an architecture-suffixed macOS updater, while
Tauri emitted `Atpiano.app.tar.gz`. It failed before creating a draft. Release
recovery used only the retained, attested tagged-run artifacts, independently
verified both updater signatures and the notarized DMG, reconciled every local
hash with GitHub's asset digests, generated the exact two-target metadata, and
passed the strict draft validator before publication. Commit `f1c905e` fixes
and tests the automatic selector for all future tags.

## Published 0.1.0 Evidence

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `Atpiano_0.1.0_aarch64.dmg` | 575,135,484 | `704b1623c5cfdc55b206ed2aa067aa22d931f0078549515c56266a0037720edd` |
| `Atpiano.app.tar.gz` | 584,024,206 | `369d7efa775adb145ef21d53fa54b15aab78157bec94993d4aef5cd21eb54996` |
| `Atpiano.app.tar.gz.sig` | 404 | `6fdf3cddb73ccfadaf300463a43188e693e723f20e535ce24fc4646327fd557d` |
| `Atpiano_0.1.0_x64-setup.exe` | 435,644,168 | `7ee234725481027a223089d1a6b9db242d67967706f2190158b7e82b2d796197` |
| `Atpiano_0.1.0_x64-setup.exe.sig` | 416 | `3ee00e5c7af232d523ca0f2b8dd271aa5ffa1a13dd4a12191106c1bd23187365` |
| `Atpiano_0.1.0_media-sources.tar.gz` | 13,220,731 | `c662d0b3b2aadc11a170534cb83a7dcd071443be74a9ec8e3255ce29a58a78c2` |
| `latest.json` | 1,749 | `d204eca56f8d17f1d6593fc7243380b809e8f75de34675ab62a06bf0531bf765` |
| `SHA256SUMS` | 637 | `8e2f0506d89ed26ec8bf9d52633ff2c3547bb6c6110512f17495d3cf5e2220e1` |

The Windows signing audit records signer subject `Kyle Graehl`, certificate
thumbprint `E1C64C8768CD2EB85F6CC1E759309B72FBB311A5`, the Microsoft
Public RSA Time Stamping Authority, and zero forbidden score assets. GitHub
build-provenance verification resolves all six platform files to workflow
`.github/workflows/desktop.yml` at `refs/tags/desktop-v0.1.0`.

## Published 0.1.1 Evidence

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `Atpiano_0.1.1_aarch64.dmg` | 575,149,993 | `0cb3e9ea3c5528c76a6ef177700e80b3381881e50d2dfac5a938035c3392ccde` |
| `Atpiano.app.tar.gz` | 584,017,257 | `01985b8f1c94dbc6a13e22eef96aaddf03ae8deca7cc9186381888f080804e8c` |
| `Atpiano.app.tar.gz.sig` | 404 | `366ea0e5c6976eb140ff59e5de9c113ef1c50d3e935c9cc654d6eb96e17664ee` |
| `Atpiano_0.1.1_x64-setup.exe` | 435,673,016 | `7b8f6f78b49661bcac60f9b05ef95b2b83c0aa6f223a2f73c919e0bced1d07bd` |
| `Atpiano_0.1.1_x64-setup.exe.sig` | 416 | `e08feeec8702f538237a1ddaa7416bfd8e7b7ca7586bb477d115ea833c826502` |
| `Atpiano_0.1.1_media-sources.tar.gz` | 13,220,729 | `f631ac0a47f82bd95968226fbea1e3bbadcd5ab08e49ece1c3bf0b30f4e6b3fe` |
| `latest.json` | 1,602 | `a07227cdf7f318e9fcf92c556082a23bba3a4d6e13f9abb22d435bf87482cdab` |
| `SHA256SUMS` | 637 | `eebccd7f0e746048336de3a0486fa4f27a9ca8f719daa9a63d04ee98d904ed4d` |

The finalizer published exactly eight assets and marked the release latest,
non-draft, and non-prerelease. GitHub server-side digests match
`SHA256SUMS`. Local verification of the detached signature files and checksum
manifest resolves tag-scoped GitHub build provenance to
`refs/tags/desktop-v0.1.1`. The tag and workflow head SHA both resolve to
`66a82e2d4d87795c79ef286cb5f9709adb13e6c2`.

The production product is the tracked `update-server/atpiano.json` exposed by
the shared update service. Validate it after deployment with:

```bash
curl -i https://updates.graehlarts.com/atpiano/tauri/darwin/aarch64/0.0.0
curl -i https://updates.graehlarts.com/atpiano/tauri/windows/x86_64/0.0.0
curl -i https://updates.graehlarts.com/atpiano/tauri/darwin/aarch64/0.1.1
curl -i https://updates.graehlarts.com/atpiano/tauri/windows/x86_64/0.1.1
```

The first two must return HTTP 200 with the current version, exact release
URLs, and published signatures. The last two must return HTTP 204.

## Remaining Acceptance After `0.1.0`

Auto-update is implemented in the applications and release metadata and is
live through the production product route. It is not fully accepted until the
installed `0.1.0 -> 0.1.1` campaign passes on both operating systems. That
campaign must preserve sessions, installation identity, acknowledgement, and
the compatible externally acquired score runtime without downloading the
model again.

The Windows media corresponding-source attachment gap was explicitly accepted
for this free proof-of-concept release: the tracked Windows manifest pins the
BtbN build repository and FFmpeg commits, while the attached source archive is
the exact macOS FFmpeg/LAME source set. Do not describe that archive as exact
corresponding source for the Windows binaries. Reconcile a Windows source
bundle in a future release when practical.
