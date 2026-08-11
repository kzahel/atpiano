# Public Desktop Release

Topic: public-desktop-release

Status: **at publication hold as of 2026-08-11, with the complete LGPL media
release candidate signed, notarized, installed, and locally accepted.**
Atpiano has implemented the accepted Desktop Update Contract v1 for a first
public proof-of-concept release, with macOS Apple silicon as its only supported
target. Tactical
[`051-signed-macos-update-lane.md`](../tactical/051-signed-macos-update-lane.md)
owns the first signed baseline, successor update, and acceptance campaign.
No release has been published, the GitHub repository remains private, and no
production update-server configuration has been changed.

## Scope

This topic owns the continuing public desktop distribution contract:

- the supported desktop target and package profile;
- product, version, tag, route, and release identities;
- Developer ID, notarization, updater signing, checksums, and build
  attestations;
- desktop-only update state, scheduling, installation safety, and component
  identity;
- public-repository and distributable-content preflight; and
- durable installed old-to-new acceptance evidence.

The shared contract and canary live in `~/code/desktop-release-kit`. They are
the normative reference and conformance testbed, not an Atpiano dependency.
Atpiano owns its own workflow, updater key, endpoint, product configuration,
UI, sidecar lifecycle, supported-target declaration, and release evidence.

[`desktop-score-runtime-footprint.md`](desktop-score-runtime-footprint.md)
continues to own score-runtime size and model provenance. This topic owns only
whether that runtime may cross the public release boundary.

## Accepted Product Direction

Atpiano is a public proof of concept intended for interested people to try and
review. The same application and feature set are available to everyone. There
is no payment or eligibility tier in this phase.

The repository may become public without choosing an Atpiano source license
yet. In that state the source is visible but ordinary copyright restrictions
remain; public visibility must not be described as open-source licensing.
The maintainer's email address is acceptable public information.

The ordinary application release must not contain MIDI2ScoreTransformer
source or its checkpoint. A later optional score-generator acquisition flow
may ask the user to acknowledge the upstream personal, educational, or
academic-use boundary and then acquire the exact assets directly from the
upstream location. Atpiano must not mirror, rebundle, or imply that its own
repository terms grant rights to those assets. That later flow needs pinned
URLs, hashes, displayed terms, failure recovery, removal, and provenance; it
is not part of the first score-free signed-update acceptance campaign.

## Product And Package Contract

| Concern | Atpiano value |
| --- | --- |
| Repository | `kzahel/atpiano` |
| Tauri identifier | `com.atpiano.desktop` |
| Product ID | `atpiano` |
| Display name | `Atpiano` |
| Release tag prefix | `desktop-v` |
| Update route | `https://updates.graehlarts.com/atpiano/tauri/{{target}}/{{arch}}/{{current_version}}` |
| Supported updater target | `darwin-aarch64` only |
| Initial installer | signed and notarized DMG containing `Atpiano.app` |
| In-app update | signed Tauri `.app.tar.gz` |
| Installation privilege | no root; user copies the App from the DMG |
| Mutable data | platform application-data/config directories, outside the App |

The first proposed release pair is `desktop-v0.1.0` followed by
`desktop-v0.1.1`. The first release must already contain the updater. The
successor must carry an unmistakable visible change and coherent Tauri,
web-client, Python-sidecar, and model-pack identities.

This product-declared one-target matrix deliberately specializes the canary's
five-target contract. It does not claim Windows, Linux, or Intel macOS support.

## Publication Hold Snapshot

| Concern | Proposed or observed value |
| --- | --- |
| Baseline version/tag | `0.1.0` / `desktop-v0.1.0` |
| Successor version/tag | `0.1.1` / `desktop-v0.1.1` |
| Local signed installer | `Atpiano_0.1.0_aarch64.dmg` |
| Local signed update pair | `Atpiano.app.tar.gz` and `Atpiano.app.tar.gz.sig` |
| CI metadata/finalizer output | `latest.json` and `SHA256SUMS` |
| Corresponding media sources | `Atpiano_0.1.0_media-sources.tar.gz` |
| Product proposal | `update-server/atpiano.json` |
| Exact route | `https://updates.graehlarts.com/atpiano/tauri/...` |
| Repository state | private `kzahel/atpiano`, default branch `main` |
| Actions secrets | none configured |
| Production route | inactive; current concrete target request returns HTTP 404 JSON |

The local artifact hashes and notarization submission are retained in the
tactical execution record. `latest.json` and `SHA256SUMS` deliberately do not
exist as hand-authored local artifacts; the draft workflow produces and
validates them against the tagged GitHub release.

## Release Safety Contract

- The updater private key is unique to Atpiano. The public key embedded in the
  application is public; the private key and password remain outside Git and
  enter GitHub only as Actions secrets.
- GitHub Actions owns the release build, Developer ID signing, notarization,
  updater signing, checksums, and artifact attestations.
- Tagged builds fail closed when a required credential or artifact is absent.
- A release remains a draft until its exact supported artifact matrix,
  signatures, hashes, notarization evidence, and metadata validate.
- The production route becomes eligible only after product configuration is
  reviewed and deliberately activated.
- Desktop installation cannot begin while capture is requesting, warming,
  recording, or stopping; while any session is settling; or while a score job
  is active. The sidecar receives a graceful shutdown opportunity before
  replacement and must not survive relaunch as an orphan.
- Hosted-web `ClientUpdateNotice` continues to own deployed web-asset refresh.
  Tauri update behavior lives at the desktop composition/runtime boundary.
- The stable anonymous installation UUID contains no user, account, document,
  hostname, or device identity and is sent only as `X-CFU-Id`.
- Automatic checks are silent after startup and once per day. Manual checks,
  available releases, download progress, installation, and errors are visible.

## Distribution Preflight

A 2026-08-11 read-only inspection found no key/certificate files or
high-confidence credential patterns in the working tree or reachable Git
history. The per-product updater private key is outside the repository, and
only its public key is tracked. The maintainer-approved email address is
present in history. Before changing repository visibility, re-run the scan at
the exact candidate commit and consciously review:

- the tracked 34.7-second piano recording and its named reference image under
  `oracle/`;
- home-service hostnames, a historical LAN address, and family-role wording in
  documentation and scripts; and
- generated release files, manifests, logs, and workflow output for private
  paths or identifiers.

The follow-up human-context review found that the tracked oracle is a
34.688-second piano MP3 with only an FFmpeg encoder tag and a reference score
image titled `kyle test recording`. It contains the maintainer's already
public name but no embedded account/contact metadata. Ignored WAV and tool
screenshots are not tracked. A personal-family sentence in a product-vision
topic was generalized; other child/family references describe product scope.
The one literal `192.168.1.104` is an unroutable historical LAN default in the
sharing script, not a public host or credential.

The local rehearsal App contains the local username in Rust dependency
diagnostic paths and Python build-time `sysconfig` metadata. Those strings are
generated rather than tracked, disclose no user data beyond the maintainer
identity, and will be replaced by GitHub runner paths in the authoritative CI
rebuild. The exact CI artifacts still require a post-build private-path and
secret-pattern scan before publication.

The earlier rehearsal used Homebrew FFmpeg 8.1.2 with `--enable-gpl`, x264,
x265, and 18 bundled media libraries. That artifact remains useful historical
signing evidence but is no longer the proposed public candidate.

The replacement media contract is tracked in `desktop-media/manifest.json`.
It builds FFmpeg 8.1.2 as LGPL-2.1-or-later and LAME 4.0 as
LGPL-2.0-or-later from pinned upstream archives, enables shared linking, and
explicitly excludes both `--enable-gpl` and `--enable-nonfree`. Only WAV/MP3
probe, decode, concatenation, raw PCM, null verification, resampling, and
`libmp3lame` export components are enabled. The runtime has two binaries and
six shared libraries with relative load paths; its build identity is
`717d1632bf240196e8c482f00ee665a378b0255536379890cb3cea75a36fdd78`.

Applicable license texts and `THIRD_PARTY_NOTICES.md` are installed in the
App. Every tagged draft must contain the deterministic
`Atpiano_<version>_media-sources.tar.gz` asset with the exact verified upstream
archives, complete build implementation/configuration, notices, and an
internally reconciled hash manifest. The finalizer rejects a draft without
that asset, and checksums and GitHub build provenance cover it. The shared
libraries remain replaceable/relinkable after local re-signing, and Atpiano
has no EULA restricting LGPL debugging or modification.

## Current Gates

1. **Complete-bundle signing rehearsal: passed.** The complete score-free LGPL
   candidate passed Developer ID signing, hardened runtime, notarization,
   stapling, mounted-DMG and installed-App Gatekeeper checks, packaged replay,
   a visible 42-second import/scoring flow, external-session persistence,
   stable installation identity, and clean shutdown. The sealed App contains
   14,327 files, 1,035,469,721 bytes, and 381 individually verified arm64
   native signatures.
2. **Release lane: implemented locally.** The product JSON, macOS-26 arm64
   workflow, draft validator/finalizer, checksums, and attestations are present
   and tested. No GitHub workflow has run and no Actions secrets have been
   uploaded.
3. **Desktop updater: implemented and locally accepted.** The installed
   notarized App exposes manual and scheduled checks, stable installation and
   component identities, install blockers, download/install states, and
   graceful sidecar preparation/recovery. A manual check reached the proposed
   route and failed safely against its expected HTTP 404 while the product was
   inactive. The installation UUID remained unchanged across relaunch.
4. **Distribution compliance: locally accepted.** The pinned minimal LGPL
   build, notices, exact corresponding-source archive, release attachment,
   checksum, attestation, and fail-closed draft validation are implemented.
   The unsigned full stage passed with 14,321 files, 1,015,793,592 bytes and
   378 arm64 native files. The signed App reconciles a 14-file/2,871,458-byte
   media category and passed Gate 1.
5. **Publication hold:** review the proposed tag, artifact set, exact route,
   rehearsal evidence, public-repository preflight, and remaining risks before
   changing repository visibility, uploading Actions secrets, activating the
   production product config, pushing a release tag, or publishing a release.
6. **Installed update campaign:** after approval, prove the exact signed
   `0.1.0 -> 0.1.1` path through production and retain redacted evidence.

## Recommended Direction

Review the exact publication candidate and then deliberately authorize the
external mutations as one bounded release operation. The local implementation
and accepted installed-DMG rehearsal are not authorization to make the
repository public, upload secrets, activate production routing, push a tag, or
publish a release. Only a later signed `0.1.0 -> 0.1.1` campaign through
production can close the update contract.
