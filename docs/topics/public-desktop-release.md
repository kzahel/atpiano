# Public Desktop Release

Topic: public-desktop-release

Status: **the source repository is public with no declared Atpiano source
license; binary publication remains on hold as of 2026-08-23 while the first
release adds user-acquired score capability.** Atpiano has implemented the
accepted Desktop Update Contract v1 for a first public proof-of-concept
release. The accepted direction now requires both macOS arm64 and Windows
x86_64 CPU applications in the first binary tag. No GitHub Release exists. All
11 required Actions secret names were configured and verified on 2026-08-23;
the credentialed workflow rehearsal has not run. Tactical
[`051-signed-macos-update-lane.md`](../tactical/051-signed-macos-update-lane.md)
owns the macOS signed baseline and update campaign. The earlier macOS
score-assets-free LGPL candidate is signed, notarized, installed, and locally
accepted. Tactical
[`052-user-acquired-score-runtime.md`](../tactical/052-user-acquired-score-runtime.md)
has added the acquisition controller, shared notice, and pinned
proof-of-concept score-support layers without adding the
MIDI2ScoreTransformer repository or checkpoint.
Tactical
[`053-windows-desktop-release-lane.md`](../tactical/053-windows-desktop-release-lane.md)
has produced and installed the matching unsigned Windows x64 development
package, including a real user-acquired CPU score result and reinstall
preservation; signed CI artifacts and updater evidence remain. No release has
been published and no production update-server configuration has been changed.

## Scope

This topic owns the continuing public desktop distribution contract:

- the supported desktop targets and package profiles;
- product, version, tag, route, and release identities;
- Developer ID, notarization, Authenticode, updater signing, checksums, and
  build attestations;
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

The repository became public on 2026-08-11 without choosing an Atpiano source
license. The source is visible but ordinary copyright restrictions remain;
public visibility must not be described as open-source licensing. The
maintainer's email address is acceptable public information.

The ordinary application release must not contain MIDI2ScoreTransformer
source or its checkpoint. The first published build is now intended to contain
the capability to acquire those exact assets directly from upstream after a
person acknowledges an education/research-only notice. The notice must also
say that upstream source and weights currently have no explicit license and
that Atpiano and the acknowledgement do not grant rights. Atpiano must not
mirror, rebundle, or imply that its own repository terms cover those assets.

The two-platform acquisition-capable release needs pinned upstream URLs and
hashes, displayed terms, local acknowledgement provenance, bounded
transactional download, failure recovery, relaunch activation, removal, update
compatibility, and an exact signed support-layer inventory. These are the scope
of tactical 052. Tactical 053 owns Windows packaging and installed parity. Both
are prerequisites of `desktop-v0.1.0`. Every release artifact remains free of
the MIDI2ScoreTransformer repository and checkpoint even though each installed
application can become score-capable after the user's separate acquisition.

All first-release models run on CPU. Basic Pitch, Transkun, and the Atpiano
MIDI2Score adapter have CPU execution paths; CUDA is not required for feature
parity. The Windows release target is x86_64 because the locked model stack has
critical Windows x64 wheels but not a complete native Windows ARM64 set. The
configured Windows 11 ARM64 machine-control testbed runs the x64 package under
supported Windows emulation for interactive acceptance. Native x64 CI plus the
existing native x64 server baseline provide complementary architecture
evidence; the emulated VM is not presented as native x64 performance evidence.

This is a free, noncommercial proof of concept rather than a general commercial
distribution program. The maintainer accepts a limited provisional dependency
risk for ScoreTransformer and MUSTER instead of delaying publication for
evaluation-only cleanup. That posture does not create a license. A credible
upstream objection triggers prompt release unpublication or route deactivation
where appropriate and a signed forward update disabling acquisition/runtime
selection; installed user files are never silently deleted.

## Product And Package Contract

| Concern | Atpiano value |
| --- | --- |
| Repository | `kzahel/atpiano` |
| Tauri identifier | `com.atpiano.desktop` |
| Product ID | `atpiano` |
| Display name | `Atpiano` |
| Release tag prefix | `desktop-v` |
| Update route | `https://updates.graehlarts.com/atpiano/tauri/{{target}}/{{arch}}/{{current_version}}` |
| Supported updater targets | `darwin-aarch64`, `windows-x86_64` |
| Initial installers | signed/notarized DMG containing `Atpiano.app`; signed per-user NSIS setup executable |
| In-app updates | signed Tauri `.app.tar.gz`; signed Windows NSIS updater artifact |
| Optional score model | direct user acquisition from pinned upstream URLs after acknowledgement; never a release asset |
| Installation privilege | no root/admin; DMG copy on macOS and per-user NSIS on Windows |
| Mutable data | platform application-data/config directories, outside the App |

The first proposed release pair is `desktop-v0.1.0` followed by
`desktop-v0.1.1`. The first release must already contain the updater. The
successor must carry an unmistakable visible change and coherent Tauri,
web-client, Python-sidecar, and model-pack identities.

This product-declared two-target matrix deliberately specializes the canary's
five-target contract. It does not claim Linux, Intel macOS, or native Windows
ARM64 support.

## Publication Hold Snapshot

| Concern | Proposed or observed value |
| --- | --- |
| Baseline version/tag | `0.1.0` / `desktop-v0.1.0` |
| Successor version/tag | `0.1.1` / `desktop-v0.1.1` |
| Accepted local macOS installer | `Atpiano_0.1.0_aarch64.dmg` baseline; acquisition-capable rebuild pending |
| macOS update pair | `Atpiano.app.tar.gz` and `Atpiano.app.tar.gz.sig` |
| Windows runtime | complete 2.12 GB x64 resource stage passes twice under x64-on-ARM64 emulation |
| Windows installer/update | corrected unsigned NSIS package accepted locally; signed CI package and updater proof pending |
| CI metadata/finalizer output | exact two-target `latest.json` and final `SHA256SUMS` implemented; credentialed run pending |
| Corresponding media sources | `Atpiano_0.1.0_media-sources.tar.gz` |
| Score acquisition | controller/dialog implemented; both cancel gates pass; real Windows acquisition, CPU adapter result, and reinstall preservation pass |
| MIDI2ScoreTransformer release assets | repository and checkpoint forbidden; direct upstream acquisition only |
| Product proposal | `update-server/atpiano.json` |
| Exact route | `https://updates.graehlarts.com/atpiano/tauri/...` |
| Repository state | public `kzahel/atpiano`, default branch `main`, no declared Atpiano license |
| Actions secrets | none configured; 11 required updater, Apple, and Azure Trusted Signing names |
| Production route | inactive; current macOS arm64 and Windows x64 `0.1.0` requests both return HTTP 404 JSON |

The local artifact hashes and notarization submission are retained in the
tactical execution record. They remain baseline signing evidence rather than
the exact future `0.1.0` candidate once tactical 052 changes the App.
`latest.json` and `SHA256SUMS` deliberately do not exist as hand-authored local
artifacts; the draft workflow produces and validates them against the tagged
GitHub release.

## Release Safety Contract

- The updater private key is unique to Atpiano. The public key embedded in the
  application is public; the private key and password remain outside Git and
  enter GitHub only as Actions secrets.
- GitHub Actions owns both release builds, Developer ID signing/notarization,
  Windows Authenticode signing, updater signing, checksums, and artifact
  attestations.
- Tagged builds fail closed when a required credential or artifact is absent.
- A release remains a draft until both entries in its exact supported artifact matrix,
  signatures, hashes, notarization evidence, and metadata validate.
- The production route becomes eligible only after product configuration is
  reviewed and deliberately activated.
- The applications, DMG, Windows installer, updater artifacts, GitHub Release,
  attestations, and media-source archives contain no MIDI2ScoreTransformer
  repository or checkpoint. A tracked acquisition contract and pinned,
  inventoried proof-of-concept support layers may ship only after tactical 052
  passes its separate audit.
- Optional score acquisition is a deliberate desktop action after local
  acknowledgement. App startup, automatic update checks, and score-view
  rendering never download the model implicitly.
- Acquired assets live outside the signed App, remain independent of the
  updater payload, and are selected only when their exact contract remains
  compatible. Updates never silently acquire, rewrite, or delete them.
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
history. The scan was repeated at the exact publication candidate before the
repository became public, with the same result. The per-product updater
private key is outside the repository, and only its public key is tracked.
The maintainer-approved email address is present in history. The preflight
consciously reviewed:

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

The local macOS rehearsal App contains the local username in Rust dependency
diagnostic paths and Python build-time `sysconfig` metadata. Those strings are
generated rather than tracked, disclose no user data beyond the maintainer
identity, and will be replaced by GitHub runner paths in the authoritative CI
rebuild. The exact CI artifacts still require a post-build private-path and
secret-pattern scan before publication.

Tactical 052 changes the distributable dependency and content boundary. Before
publication, record exact provenance, known license status, and available
notices for both platform score-support layers and scan both applications plus
every nested release archive for the MIDI2ScoreTransformer repository tree,
checkpoint name/hash, internal runtime manifests, acquisition staging, and
local acknowledgement data. ScoreTransformer and MUSTER are provisionally
accepted helper dependencies for this noncommercial proof of concept; their
removal is a later todo. The tracked acquisition contract is expected public
content; acquired model bytes are not. Windows preflight also scans PE/DLL and
installer metadata, decoded-signing-file cleanup, and build paths without
publishing certificate material or private testbed inventory.

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

1. **Complete-bundle signing baseline: passed; exact-candidate rerun pending.**
   The complete score-assets-free LGPL candidate passed Developer ID signing,
   hardened runtime, notarization, stapling, mounted-DMG and installed-App
   Gatekeeper checks, packaged replay, a visible 42-second import/scoring flow,
   external-session persistence, stable installation identity, and clean
   shutdown. The sealed App contains 14,327 files, 1,035,469,721 bytes, and 381
   individually verified arm64 native signatures. Tactical 052 changes the
   signed contents, so its final acquisition-capable candidate must repeat
   this gate before tagging.
2. **Two-platform release lane: implemented; credentialed CI pending.** The
   product JSON, macOS-26 arm64 and Windows-2025 x64 jobs, Azure Trusted
   Signing verification, exact two-target updater-manifest writer, draft
   validator/finalizer, final checksums, and attestations are present and pass
   local tests plus `actionlint`. The earlier one-target public
   [source run](https://github.com/kzahel/atpiano/actions/runs/31516122672)
   passed its Ubuntu source and macOS Rust jobs. A subsequent
   [manual rehearsal](https://github.com/kzahel/atpiano/actions/runs/31516446700)
   passed both prerequisite jobs, then failed closed before signing setup with
   `Desktop builds require both Atpiano updater signing secrets`. No Actions
   secrets have been uploaded.
3. **Desktop updater: implemented and locally accepted.** The installed
   notarized App exposes manual and scheduled checks, stable installation and
   component identities, install blockers, download/install states, and
   graceful sidecar preparation/recovery. A manual check reached the proposed
   route and failed safely against its expected HTTP 404 while the product was
   inactive. The installation UUID remained unchanged across relaunch.
4. **Distribution compliance: locally accepted.** The pinned minimal LGPL
   macOS build, notices, exact corresponding-source archive, release
   attachment, checksum, attestation, and fail-closed draft validation are
   implemented.
   The unsigned full stage passed with 14,321 files, 1,015,793,592 bytes and
   378 arm64 native files. The signed App reconciles a 14-file/2,871,458-byte
   media category and passed Gate 1. The separately consumed Windows BtbN
   media build has exact binary/build/FFmpeg commit provenance, but its exact
   corresponding-source attachment has not been reconciled with the macOS
   source archive and remains a publication gap.
5. **User-acquired score runtime: implemented core; macOS and full-flow
   acceptance still blocking.** The shared truthful acknowledgement, direct
   upstream transactional acquisition, dependency inventories, external
   activation/removal, and forbidden-model-content checks are implemented.
   Both packaged dialogs pass the disabled-until-accepted and cancel-with-no-
   acquisition gate. Windows also passes a real acknowledged download,
   relaunch, direct CPU MusicXML/alignment result, and uninstall/reinstall
   preservation. The equivalent macOS acquisition, full packaged score
   request, explicit removal, and compatible-update persistence remain.
6. **Windows desktop lane: unsigned development package accepted; signing and
   complete behavior remain.** The generalized sidecar/resource boundary,
   Windows x64 CPU and score-support runtime, current-user NSIS installer,
   hidden sidecar, and installed disclosure pass on the machine-control
   testbed under x64-on-ARM64 emulation. Its actual acquisition, isolated CPU
   adapter result, and reinstall preservation also pass. The exact credentialed
   CI package, packaged replay/export and frontend score flows, explicit
   removal, and Windows updater remain.
7. **Release credentials: configured; rehearsal pending.** GitHub reports all
   11 required Actions secret names. The exact contract is eight updater/Apple names plus
   `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_CLIENT_SECRET`. The tracked
   updater public key matches the local Atpiano per-product public-key file.
   The local Developer ID identity validates, App Store Connect notarization
   authentication succeeds, and the private credential files are owner-only.
   The canonical attended helper validated all four credential groups before
   uploading through non-logging input boundaries, and
   `scripts/check-desktop-release-secrets` confirms every expected name. Run
   the non-tagged two-platform rehearsal before creating a tag.
8. **Binary-publication hold:** repository visibility and public CI rehearsal
   are complete. Review the proposed tag, artifact set, exact route, rehearsal
   evidence, and remaining risks before uploading Actions secrets, activating
   the production product config, pushing a release tag, or publishing a
   release.
9. **Installed update campaigns:** after approval, prove the exact signed
   `0.1.0 -> 0.1.1` path through production on macOS and Windows with each
   acquired runtime retained and usable, then retain redacted updater and
   upstream-request evidence.

## Recommended Direction

Use [`desktop-release-operator-runbook.md`](../desktop-release-operator-runbook.md)
to configure and verify the 11 secrets, run one non-tagged credentialed
rehearsal, and inspect both exact signed candidates. Reconcile the Windows
media corresponding-source attachment, perform the macOS acquisition and the
remaining full score/removal paths on both OSes, then review and deliberately
authorize the tag and production-route mutations. The existing local
implementation, unsigned Windows install, and accepted score-free DMG
rehearsal are not authorization to activate production routing, push a tag, or
publish a release. Only signed `0.1.0 -> 0.1.1` campaigns through production
on both platforms, with compatible user-acquired runtimes preserved and
exercised, can close the update contract.
