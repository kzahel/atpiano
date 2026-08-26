# Public Desktop Release

Topic: public-desktop-release

Status: **the coordinated `0.1.3` application-theme release is public/latest.**
The public, unlicensed source repository and
[`desktop-v0.1.3`](https://github.com/kzahel/atpiano/releases/tag/desktop-v0.1.3)
contain signed macOS arm64 and Windows x86_64 CPU applications. Tagged
[run 32940171525](https://github.com/kzahel/atpiano/actions/runs/32940171525)
published exact commit `12dd515274c6ac5ec33443bbcfd3e71e1e78e241` after
all source, Rust, signed-platform, notarization, packaged-flow, provenance, and
finalizer gates passed. The applications now use the public site's warm
paper/ivory/ink/red light palette and provide an explicit persistent dark
mode. The hardened macOS signature retains the narrow audio-input entitlement
required for TCC to show the native consent prompt. The production updater
offers signed `0.1.3` metadata to both `0.1.2` targets and returns no update to
`0.1.3`. An installed public `0.1.1 -> 0.1.2` clean-TCC
microphone repeat remains a follow-up, not a publication blocker. Both apps
retain the education/research acknowledgement and direct user-acquisition
capability without containing the MIDI2ScoreTransformer repository or
checkpoint. Windows installed acceptance also remains open. Tactical
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
has produced the signed public Windows x64 packages and a real user-acquired
CPU score result with reinstall preservation, and now owns the remaining
installed signed-update and full-flow acceptance.
Tactical
[`055-macos-microphone-entitlement-repair.md`](../tactical/055-macos-microphone-entitlement-repair.md)
owns the macOS microphone incident, signing correction, and replacement-release
evidence.

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
source or its checkpoint. The published `0.1.0` build contains the capability
to acquire those exact assets directly from upstream after a
person acknowledges an education/research-only notice. The notice must also
say that upstream source and weights currently have no explicit license and
that Atpiano and the acknowledgement do not grant rights. Atpiano must not
mirror, rebundle, or imply that its own repository terms cover those assets.

The two-platform acquisition-capable release uses pinned upstream URLs and
hashes, displayed terms, local acknowledgement provenance, bounded
transactional download, failure recovery, relaunch activation, removal, update
compatibility, and an exact signed support-layer inventory. These are the scope
of tactical 052. Tactical 053 owns Windows packaging and installed parity.
Every release artifact remains free of
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

The first release is `desktop-v0.1.0`; its first acceptance successor is
`desktop-v0.1.1`, its microphone correction is `desktop-v0.1.2`, and the
current website-aligned theme release is `desktop-v0.1.3`. The first release
contains the updater. Each successor carries an unmistakable visible
proof-of-concept update marker and coherent Tauri, web-client, Python-sidecar,
and model-pack identities.

This product-declared two-target matrix deliberately specializes the canary's
five-target contract. It does not claim Linux, Intel macOS, or native Windows
ARM64 support.

## Published 0.1.0 Snapshot

| Concern | Published or observed value |
| --- | --- |
| Baseline version/tag | public baseline `0.1.0` / `desktop-v0.1.0` |
| Successor version/tag | `0.1.1` / `desktop-v0.1.1` |
| macOS installer | notarized/stapled 575,135,484-byte DMG, SHA-256 `704b1623c5cfdc55b206ed2aa067aa22d931f0078549515c56266a0037720edd` |
| macOS updater | 584,024,206-byte `Atpiano.app.tar.gz`, SHA-256 `369d7efa775adb145ef21d53fa54b15aab78157bec94993d4aef5cd21eb54996`, plus verified signature |
| Windows runtime | 32,827 files and 2,102,342,989 bytes; native x64 CPU stage and independent re-audit pass |
| Windows installer/update | Authenticode-signed and timestamped 435,644,168-byte NSIS executable, SHA-256 `7ee234725481027a223089d1a6b9db242d67967706f2190158b7e82b2d796197`, plus verified updater signature |
| CI metadata | exact two-target `latest.json`, `SHA256SUMS`, and platform build-provenance attestations published |
| Corresponding media sources | 13,220,731-byte `Atpiano_0.1.0_media-sources.tar.gz`, SHA-256 `c662d0b3b2aadc11a170534cb83a7dcd071443be74a9ec8e3255ce29a58a78c2` |
| Score acquisition | controller/dialog implemented; both cancel gates pass; real Windows acquisition, CPU adapter result, and reinstall preservation pass |
| MIDI2ScoreTransformer release assets | repository and checkpoint forbidden; direct upstream acquisition only |
| Product configuration | tracked `update-server/atpiano.json`, active through the Pi service |
| Exact route | `https://updates.graehlarts.com/atpiano/tauri/...` |
| Repository state | public `kzahel/atpiano`, default branch `main`, no declared Atpiano license |
| Actions secrets | all 11 updater, Apple, and Azure Trusted Signing names configured and exercised |
| Production route | active; both targets return signed `0.1.0` metadata to `0.0.0` and HTTP 204 to `0.1.0` |

The exact release hashes, CI runs, notarization result, finalizer recovery, and
production-route checks are retained in the tactical and operator runbook.
`latest.json` and `SHA256SUMS` are release assets reconciled against GitHub's
server-side asset digests, not hand-authored repository files.

## Published 0.1.1 Snapshot

| Concern | Published or observed value |
| --- | --- |
| Version/tag/commit | public/latest `0.1.1` / `desktop-v0.1.1` / `66a82e2d4d87795c79ef286cb5f9709adb13e6c2` |
| Tagged workflow | [run 32707274179](https://github.com/kzahel/atpiano/actions/runs/32707274179), all source, Rust, signed platform, finalizer, and attestation jobs passed |
| macOS installer | notarized/stapled 575,149,993-byte DMG, SHA-256 `0cb3e9ea3c5528c76a6ef177700e80b3381881e50d2dfac5a938035c3392ccde` |
| macOS updater | 584,017,257-byte `Atpiano.app.tar.gz`, SHA-256 `01985b8f1c94dbc6a13e22eef96aaddf03ae8deca7cc9186381888f080804e8c`, plus verified signature |
| Windows installer/update | Authenticode-signed and timestamped 435,673,016-byte NSIS executable, SHA-256 `7b8f6f78b49661bcac60f9b05ef95b2b83c0aa6f223a2f73c919e0bced1d07bd`, plus verified updater signature |
| Corresponding media sources | 13,220,729 bytes, SHA-256 `f631ac0a47f82bd95968226fbea1e3bbadcd5ab08e49ece1c3bf0b30f4e6b3fe` |
| Release metadata | exact two-target `latest.json`, `SHA256SUMS`, GitHub asset digests, and tag-scoped build-provenance attestations verified |
| Production route | both `0.1.0` targets return signed `0.1.1` metadata; both `0.1.1` targets return HTTP 204 |
| Installed acceptance | macOS arm64 passed on a claimed Tart appliance; Windows x86_64 remains open |

## Published 0.1.2 Snapshot

| Concern | Published or observed value |
| --- | --- |
| Version/tag/commit | public/latest `0.1.2` / `desktop-v0.1.2` / `aaa608bd9e62b37af5c24e6029ae95048b44259f` |
| Tagged workflow | [run 32890134829](https://github.com/kzahel/atpiano/actions/runs/32890134829), all source, Rust, signed platform, finalizer, and attestation jobs passed |
| macOS installer | notarized/stapled 575,203,142-byte DMG, SHA-256 `fb3f0ea1848ff36c4f3603d35bb5c15c9dc42ecbedd96814d81cffc14248deaa` |
| macOS updater | 584,016,946-byte `Atpiano.app.tar.gz`, SHA-256 `277bf7c83c689932e3a7fb7c5e7244c1ba58a2be7b85cda8be952d53e362d76c`, plus verified signature |
| Windows installer/update | Authenticode-signed and timestamped 435,645,608-byte NSIS executable, SHA-256 `bc974a83dc8b2aadcac47441b4c15ee8433420b63c8187d0662dbc57cb2aa1dc`, plus verified updater signature |
| Corresponding media sources | 13,220,730 bytes, SHA-256 `5ac34c42caabaf36d52dcbf516e39f696459692147a364a8eb701a8ee09f2797` |
| Release metadata | exactly eight assets; two-target `latest.json`, `SHA256SUMS`, GitHub asset digests, and tag-scoped build-provenance attestations published |
| Production route | both `0.1.1` targets return signed `0.1.2` metadata; both `0.1.2` targets return HTTP 204 |
| Microphone acceptance | signed development App passed native prompt and physical capture; installed public update repeat remains follow-up |

## Published 0.1.3 Snapshot

| Concern | Published or observed value |
| --- | --- |
| Version/tag/commit | public/latest `0.1.3` / `desktop-v0.1.3` / `12dd515274c6ac5ec33443bbcfd3e71e1e78e241` |
| Tagged workflow | [run 32940171525](https://github.com/kzahel/atpiano/actions/runs/32940171525), all source, Rust, signed platform, finalizer, and attestation jobs passed |
| macOS installer | notarized/stapled 575,200,770-byte DMG, SHA-256 `943418cdb5f760da457171478923381a964d3a1e979b0c866c3d0d2025874dc5` |
| macOS updater | 584,019,267-byte `Atpiano.app.tar.gz`, SHA-256 `efa2a4b66a3c104c79cda4109158cd0f05f03f1136953cb31f6e2aec5229feea`, plus verified signature |
| Windows installer/update | Authenticode-signed and timestamped 435,668,376-byte NSIS executable, SHA-256 `005df9f2a7f372fa31c732bd55d39216ba43f46ce996adf48c184451e1db2e3c`, plus verified updater signature |
| Corresponding media sources | 13,220,730 bytes, SHA-256 `9d17f5d98c708a131b3bb5f6dd2b719d1eaca3fd05cdc269aa6a38aa136709ea` |
| Release metadata | exactly eight assets; two-target `latest.json`, `SHA256SUMS`, matching GitHub digests, and tag-scoped provenance published |
| Production route | both `0.1.2` targets return signed `0.1.3` metadata; both `0.1.3` targets return HTTP 204 |
| User-facing change | website-aligned light theme, explicit persistent dark mode, and matching native window chrome |

## Release Safety Contract

- The updater private key is unique to Atpiano. The public key embedded in the
  application is public; the private key and password remain outside Git and
  enter GitHub only as Actions secrets.
- GitHub Actions owns both release builds, Developer ID signing/notarization,
  Windows Authenticode signing, updater signing, checksums, and artifact
  attestations.
- An ordinary release is tag-driven. Tagged CI owns the full checks and
  publication; duplicating the full suite locally or running a separate signed
  rehearsal is not a release prerequisite. Rehearsals are reserved for changes
  to the signing, packaging, updater, target, credential, or release-workflow
  lane, or for an explicit maintainer request.
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

The local macOS rehearsal App contained the local username in Rust dependency
diagnostic paths and Python build-time `sysconfig` metadata. Those strings are
generated rather than tracked, disclose no user data beyond the maintainer
identity, and were replaced by GitHub runner paths in the authoritative CI
rebuild. The exact CI package audits, forbidden-content checks, signing-file
cleanup, and log review passed before publication.

Tactical 052 changed the distributable dependency and content boundary. The
release records exact provenance, known license status, and available notices
for both platform score-support layers and scans both applications plus
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
signing evidence but is not the published candidate.

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

1. **Published `0.1.3` theme release and macOS artifact gates passed.**
   The tagged App and DMG passed Developer ID signing, hardened runtime,
   exact audio-input entitlement inspection, Apple notarization, stapling,
   Gatekeeper assessment, forbidden-model audit, and packaged CPU scoring
   replay. The website-aligned light and explicit dark themes are present in
   the coordinated macOS and Windows `0.1.3` release. The retained microphone
   correction supplies `com.apple.security.device.audio-input`; repeating
   physical capture after a public installed update remains follow-up
   acceptance.
2. **Two-platform signed build: passed.** The exact candidate commit
   `ed76f74686981990ce230679ccae9af19dfd61f2` passed the credentialed
   [rehearsal](https://github.com/kzahel/atpiano/actions/runs/32666483577).
   The tagged
   [release run](https://github.com/kzahel/atpiano/actions/runs/32669326956)
   produced attested macOS and Windows artifacts. Attempt 1 encountered a
   transient `notarytool` bus error after Apple accepted the DMG submission;
   attempt 2 passed all platform gates.
3. **Release publication: passed with recorded recovery.** The automatic
   finalizer failed closed before draft creation because it expected an old
   architecture-suffixed macOS updater filename. The retained, attested
   artifacts were downloaded; updater signatures, DMG notarization, and local
   hashes were reverified; `latest.json` and `SHA256SUMS` were reconciled with
   GitHub digests; and the strict draft validator passed before publication.
   Commit `f1c905e` fixes and tests the Tauri v2 `Atpiano.app.tar.gz`
   contract for future tags.
4. **Desktop updater routing: active.** The Pi loads the tracked product config
   from the public checkout. Public macOS arm64 and Windows x64 requests from
   version `0.1.2` return exact signed `0.1.3` metadata; requests from `0.1.3`
   return HTTP 204. The earlier macOS `0.1.0 -> 0.1.1` installed replacement
   passed. Its `0.1.1 -> 0.1.2` microphone repeat and Windows installed
   replacement remain open.
5. **Distribution compliance: provisionally accepted for this proof of
   concept.** The macOS LGPL notices, exact corresponding-source archive,
   checksums, and build provenance are public. The Windows BtbN media payload
   retains exact binary/build/FFmpeg commit provenance. Its exact corresponding
   source was not reconciled into the macOS source archive; the maintainer
   explicitly accepted this limited proof-of-concept gap rather than delaying
   `0.1.0`.
6. **User-acquired score runtime: both platform acquisition flows pass.**
   Both applications contain the truthful acknowledgement and transactional
   acquisition controller without upstream source/checkpoint bytes. Both
   packaged cancel gates pass. Both platforms pass acknowledged acquisition,
   relaunch, and CPU score output; Windows additionally passes reinstall
   preservation. macOS additionally passes compatible runtime and session
   preservation through the signed update. Explicit removal on both platforms
   and Windows update persistence remain.
7. **Windows signed package: passed and published; broader acceptance
   remains.** Native x64 CI passed deterministic stage/re-audit, Azure Trusted
   Signing, Authenticode verification, trusted timestamping, updater-signature
   verification, forbidden-model checks, and provenance. Ordinary packaged
   replay/export and frontend score flows, explicit removal, and installed
   updater behavior remain open.
8. **Release credentials and publication hold: complete.** All 11 secret names
   were verified and exercised without exposing their values. The explicit
   authorization covered the real two-platform tag, public release, and
   production-route activation. The repository remains public with no
   declared Atpiano source license.
9. **Installed update campaigns: first macOS successor passed; follow-ups
   open.** The exact signed macOS `0.1.0 -> 0.1.1` path preserved and reused the
   acquired runtime and retained score. A `0.1.1 -> 0.1.2` clean-TCC
   microphone repeat and the equivalent Windows campaign remain useful
   follow-up evidence.

## Recommended Direction

The website-aligned `0.1.3` theme release is public. Next acceptance work may
install the public `0.1.1 -> 0.1.2` update, confirm the native consent prompt
from clean TCC state, retain nonzero physical-microphone samples through Stop
and settlement, and verify the existing session/update/runtime contracts. The
remaining Windows installed-update campaign is independent. Use the ordinary
tag-driven path in
[`desktop-release-operator-runbook.md`](../desktop-release-operator-runbook.md)
for future low-risk releases.
