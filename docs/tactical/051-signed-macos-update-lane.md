# 051 — Signed macOS Update Lane

Topic: public-desktop-release

Status: **complete; signed `0.1.1` published and installed update accepted.**
The public/latest `desktop-v0.1.1` release contains the signed/notarized macOS
arm64 application alongside the signed Windows x64 application. The tagged App
and DMG passed hardened signing, app and DMG notarization, stapling, Gatekeeper,
packaged replay, forbidden-model audit, updater-signature verification, and
build-provenance verification. Production routing returns signed `0.1.1`
metadata to `0.1.0`. A claimed Tart macOS arm64 appliance installed the exact
public `0.1.0`, acquired and used the external score runtime, updated through
the production in-app route, and retained that runtime, its acknowledgement,
installation identity, session, and score under `0.1.1`.

## Outcome

Turn the accepted R5 Tauri boundary into Atpiano's repeatable signed macOS
arm64 half of the first release lane, contribute a score-assets-free but
user-acquisition-capable App to the coordinated two-platform tag, then prove
one real installed signed update from `0.1.0` to `0.1.1` through the production
update service without losing the compatible external score runtime.

This tactical adopts `~/code/desktop-release-kit/contract/desktop-update-v1.md`
and the canary's accepted `0.1.0 -> 0.1.1` evidence. It does not add a Git
dependency, submodule, copied application scaffold, Windows/Linux matrix, or
generic release framework.

## Entry Evidence

- R5 accepted the score-free, self-contained macOS arm64 application and its
  authenticated loopback Python sidecar on 2026-07-28.
- The real bundle is approximately 1.04 GB installed and 345 MB compressed,
  including standalone Python, native libraries, Basic Pitch, Transkun,
  FFmpeg, and FFprobe.
- The existing artifact is unsigned/ad-hoc, uses Tauri `0.1.0`, targets only
  `.app`, disables hardened runtime, and has no updater integration.
- Desktop Release Canary has proven signed DMG/App replacement through Tauri's
  `.app.tar.gz` updater on macOS Apple silicon.
- The dotfiles signing runbook owns the shared Developer ID and notarization
  credential procedure. Atpiano needs a new per-application updater key.

## Frozen Scope

- Support only `darwin-aarch64` and reject accidental expansion.
- Initial installation is a signed, notarized DMG; update installation uses a
  signed `.app.tar.gz` and remains no-root.
- Retain `com.atpiano.desktop`, product ID `atpiano`, route prefix `/atpiano`,
  and `desktop-v<version>` tags.
- Keep user workspace and installation identity outside the App bundle.
- Keep the ordinary release score-assets-free. Do not stage, archive, attest,
  or publish the MIDI2ScoreTransformer repository or checkpoint. The
  acquisition controller, tracked upstream contract, and pinned, inventoried
  proof-of-concept support layer from tactical 052 may enter the App only after
  their dedicated audits pass.
- Preserve hosted-web asset-update behavior as a separate composition.
- Do not publish a release or activate the production update-server product
  before the explicit binary-publication hold. Repository visibility may
  change only after its separate public-tree/history preflight and approval.

## Stage 1 — Signing And Notarization Gate

1. Make hardened runtime and Developer ID signing first-class release build
   settings while retaining an explicit unsigned local-development path.
2. Stage the complete real score-free runtime and sign nested Mach-O code in
   dependency-safe order with the expected Developer ID identity.
3. Build the App, updater archive, and DMG from the real bundle.
4. Verify strict nested signatures and entitlements, submit for notarization,
   staple the App and DMG where supported, and validate Gatekeeper assessment.
5. Install from the DMG and validate launch, authenticated sidecar handshake,
   representative replay/scoring, artifact export, bundle immutability, and
   clean shutdown with no Python/media orphan.

The score-free baseline has passed this gate. After tactical 052 lands, repeat
all five steps for the exact acquisition-capable candidate from clean staged
inputs. Also acquire the external runtime from a clean installed App, generate
the accepted score, and prove that neither acquisition nor use mutates the
sealed App. Prior notarization is implementation evidence, not acceptance of
changed signed contents.

If a keychain or password prompt is required, stop at that exact interactive
step and give the maintainer the safe command. Do not put credential values in
arguments, logs, documentation, or repository files.

This gate must use the complete packaged Python/model/media tree. A toy App or
an outer `codesign --deep` success without nested verification is not evidence.

## Stage 2 — Product Release Lane

1. Add the product-owned update-server JSON for `kzahel/atpiano`, path prefix
   `/atpiano`, tag prefix `desktop-v`, and Tauri updates enabled.
2. Add a macOS-26, arm64-only GitHub workflow with source checks and a
   draft-first tagged release job.
3. Require the eight macOS/updater secrets named by the shared runbook on
   tagged builds and keep secret interpolation out of shell command text.
4. Build and upload the signed DMG, signed `.app.tar.gz`, detached updater
   signature, `latest.json`, and exact corresponding-source archive for the
   bundled LGPL media libraries.
5. Validate exactly `darwin-aarch64`, GitHub SHA-256 asset digests, matching
   version/tag/URL, non-empty signature, Developer ID signing, notarization,
   stapling, the exact acquisition contract/support manifest, and the absence
   of the forbidden MIDI2ScoreTransformer repository and checkpoint.
6. Write `SHA256SUMS`, attach GitHub artifact attestations for distributable
   files, and publish only from the successful finalizer after approval.

The workflow must not inherit the canary's five-target requirement. Its
validator consumes Atpiano's explicit supported target/artifact declaration.
It must construct the public App without access to the ignored local score
runtime or upstream checkpoint.

This stage's macOS job and credential contract remain platform-specific.
Tactical 053 adds the Windows job, certificate contract, artifacts, and second
target to the coordinated finalizer. It must not weaken any macOS gate while
expanding the final artifact matrix.

## Release Credential Setup And Verification

The current workflow requires exactly these repository Actions secrets:

| Secret | Purpose |
| --- | --- |
| `TAURI_SIGNING_PRIVATE_KEY` | Atpiano-specific updater private key |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Updater key password |
| `MACOS_CERTIFICATE_P12_BASE64` | Developer ID Application certificate and private key |
| `MACOS_CERTIFICATE_PASSWORD` | PKCS#12 import password |
| `MACOS_KEYCHAIN_PASSWORD` | Temporary CI build-keychain password |
| `ASC_API_KEY_P8_BASE64` | App Store Connect notarization API private key |
| `ASC_API_KEY_ID` | Notarization API key ID |
| `ASC_API_ISSUER_ID` | Notarization API issuer ID |

Secrets are an external mutation and remain behind publication approval. When
approved, follow the canonical dotfiles signing runbook and add a local helper
or operator procedure with these properties:

1. verify the authenticated GitHub account and exact target repository
   `kzahel/atpiano` before reading secret material;
2. obtain key files from explicit maintainer-selected paths and passwords from
   a hidden TTY or local Keychain lookup, never command-line arguments;
3. transmit each value through `gh secret set --repo kzahel/atpiano` using
   standard input; encode binary P12/P8 data in memory or a permission-bounded
   temporary file and delete that file on every exit path;
4. never echo values, enable shell tracing, place values in GitHub workflow
   inputs, write them under the repository, or retain base64 output;
5. query GitHub's secret metadata after upload and verify that all eight names
   exist without attempting to read values; and
6. retain only secret names, GitHub `updated_at` timestamps, operator time,
   target repository, and the following CI run URL as redacted evidence.

Secret presence is not acceptance. Immediately run the existing
`workflow_dispatch` lane from the exact candidate commit. It must pass source
and Rust prerequisites, import the Developer ID identity without a prompt,
sign every nested native file, build the updater signature with the Atpiano
key, notarize and staple the App/DMG, run the packaged scoring smoke, audit the
acquisition-capable score-assets-free contents, and clean its temporary
keychain/key files. A manual run has no release tag and must create no public
GitHub Release. Inspect logs for accidental secret, private-path, certificate,
or key material before authorizing a tag.

If any credential is missing, expired, rejected, or prompts unexpectedly, stop
at that exact boundary. Rotate or re-upload only the affected external secret,
repeat metadata verification, and rerun the non-tagged rehearsal. Do not weaken
the fail-closed workflow or fall back to local signing for the published build.

## Stage 3 — Desktop Updater

Implement the v1 state machine at the desktop composition boundary:

```text
idle
checking
up-to-date
available
manual-install
downloading
installing
error(check | install)
```

The client must:

- persist a random installation UUID in the platform application-config
  directory and attach it as `X-CFU-Id`;
- attach exactly one `X-Check-Reason` value: startup, periodic, or manual;
- check silently five seconds after startup and every 24 hours;
- expose a visible manual action, release notes, download progress, install
  confirmation, retry, and bounded credential-free errors;
- deduplicate checks, use a 20-second timeout, retain discovered updates
  through later silent checks, and fail closed on signature errors; and
- report Tauri app version, web build identity, Python sidecar/package build
  identity, model-pack identity/hash, optional score-runtime contract/state,
  and stable installation identity.

Before `downloadAndInstall`, the application must prove that no capture is
requesting, warming, recording, or stopping; no session or import is settling;
and no score job is running. After successful replacement, normal Tauri exit
must gracefully stop and reap the Python sidecar before relaunch. Installation
failures retain the running application and recovery action.

The external score runtime lives outside the App and updater archive. A signed
update must preserve it byte-for-byte when its acquisition contract remains
compatible, must never acquire it as part of an automatic update, and must
degrade visibly without blocking startup when it becomes incompatible.

## Stage 4 — Installed Acceptance Campaign

After the publication hold is approved:

1. Freeze the exact `desktop-v0.1.0` DMG, hashes, workflow, commit, update
   metadata, and macOS testbed identity.
2. Install its App from the DMG, launch it from clean application data, and
   complete a representative score-free Atpiano flow.
3. Review and accept the optional score notice, acquire the exact runtime
   directly from upstream, relaunch, and generate a retained score with
   verified runtime and producer provenance.
4. Publish a `desktop-v0.1.1` successor with an unmistakable visible change
   and a compatible score-acquisition contract.
5. Discover, download, install, and relaunch the successor through the
   production `/atpiano` route.
6. Verify all component identities, workspace/session persistence, unchanged
   installation UUID, unchanged local acknowledgement/runtime hashes, score
   capability without reacquisition, post-update score generation, and zero
   orphan processes.
7. Remove the optional runtime, relaunch, and prove that capture/review and
   retained sessions/artifacts survive while capability returns to unavailable.
8. Inspect redacted update-server requests for startup, manual discovery, and
   relaunched startup. Separately retain redacted upstream acquisition
   destinations proving that no model bytes came from Atpiano infrastructure.
   Keep the acknowledgement receipt local and redact private paths from all
   evidence.

## Publication Hold

Stop before activating the product configuration on the shared production
server, pushing the first release tag, or publishing the first release.
Repository visibility has a separate preflight and approval boundary. Present:

- proposed version and tag;
- complete public artifact set;
- completed tactical 052 acceptance and exact score-acquisition contract;
- completed tactical 053 Windows package, signing, and testbed acceptance;
- proof that the candidate contains no MIDI2ScoreTransformer repository or
  checkpoint;
- exact product route and JSON configuration;
- signing/notarization rehearsal commands and results;
- the complete configured secret names/timestamps and successful non-tagged
  macOS and Windows credentialed CI rehearsals, with no values;
- public-tree/history and distribution-license preflight;
- exact remaining risks and manual steps.

Pushing `desktop-v0.1.0` authorizes the workflow finalizer to publish the
validated draft automatically. Treat the tag push itself as the irreversible
publication action; do not describe it as a harmless build rehearsal.

## Publication And Update Operation

After the hold packet is explicitly approved, execute the external mutations
in this order:

1. start from a clean `main` whose intended commits are pushed and whose
   ordinary public CI run is green;
2. validate coherent `0.1.0` in `pyproject.toml`, `src/atpiano/__init__.py`,
   `app/package.json`, `app/src-tauri/Cargo.toml`,
   `app/src-tauri/tauri.conf.json`, lock/generated identities, acquisition
   compatibility, and `CHANGELOG.md`;
3. replace the historical changelog statement that the score generator is
   intentionally absent with accurate score-assets-free, user-acquisition
   release notes;
4. record the candidate commit, source/tree scan, acquisition-contract hash,
   local signed artifact evidence, and clean-account acceptance;
5. upload and metadata-verify the eight macOS/updater Actions secrets using the
   preceding procedure and the Windows signing secrets using tactical 053;
6. run and inspect both credentialed non-tagged workflow rehearsals from that
   exact commit;
7. deploy and validate `update-server/atpiano.json` through the shared update
   server's own review/restart procedure, confirming only product `atpiano`,
   path `/atpiano`, repository `kzahel/atpiano`, and exactly
   `darwin-aarch64` plus `windows-x86_64` are eligible;
8. create and push annotated tag `desktop-v0.1.0` at the frozen commit, then
   monitor the workflow through final publication without manually bypassing
   a failed or draft gate;
9. verify the public release's exact DMG, Windows NSIS installer, both updater
   artifacts/signatures, `latest.json`, `SHA256SUMS`, corresponding media
   sources, attestations, release notes, platform signatures, macOS
   notarization, and forbidden-score-content result;
10. verify the production route returns each signed `0.1.0` platform update
    only for an eligible older test version and no update for installed
    `0.1.0`;
11. install both public `0.1.0` applications, run their clean
    acquisition/score acceptances, and retain their external runtimes and
    installation UUIDs;
12. implement one unmistakable visible successor change, update the same
    complete identity set coherently to `0.1.1`, add its changelog entry, and
    keep the score-acquisition contract compatible unless a deliberate new
    acknowledgement is part of the test;
13. pass local and ordinary CI gates, freeze the new commit, and push annotated
    tag `desktop-v0.1.1`;
14. discover, download, install, and relaunch `0.1.1` from each installed
    `0.1.0` application through the production route; and
15. finish every Stage 4 identity, persistence, score, request, removal,
    signature, immutability, and orphan-process check before marking this
    tactical complete.

Rollback before `desktop-v0.1.0` publication means removing or deactivating the
product config and retaining any draft release. Rollback after publication
uses a new signed forward release; never retarget or replace a published tag,
serve unsigned metadata, reuse an updater signature for different bytes, or
delete an acquired runtime silently.

## Validation

- Existing Python, frontend, contract, Rust, and packaging tests remain green.
- Focused updater policy, schedule, state, identity, and lifecycle tests pass.
- Configuration and draft-finalization tests reject version drift, unexpected
  targets, missing artifacts, absent signatures/digests, and forbidden score
  content.
- Score-acquisition tests prove informed opt-in, direct upstream URLs,
  transactional external installation/removal, score parity, update
  persistence, and complete exclusion of acquired assets from releases.
- The staged and final App audits reconcile all files and bytes, validate all
  Mach-O architectures/load paths/signatures, and remain immutable after use.
- CI proves signed artifact construction; only Stage 4 proves installed
  old-to-new update behavior.

## Rollback

The release workflow, product configuration, updater plugin, and desktop-only
UI are additive. Hosted web operation and its refresh notice remain
independent. Removing the updater configuration and desktop composition
returns to the accepted R5 boundary without migrating or deleting the external
workspace. Disabling acquisition or refusing an incompatible external score
runtime returns to score-free behavior without deleting the user's acquired
runtime or existing score artifacts. Draft GitHub Releases and an unactivated
product JSON are not eligible for production update checks.

## Execution Record

Planning opened on 2026-08-10. The first local signing investigation used the
complete 14,326-file, 1,051,953,285-byte staged runtime. It established that
Tauri signs the shell executable and outer App but does not re-sign Mach-O
files placed under `Contents/Resources`. The release script now signs every
staged executable, dynamic library, and Python extension before Tauri seals
the App, and then verifies every final native signature individually.

An ad-hoc hardened build was useful only as a structural probe. Its Python
interpreter could not load `libpython3.10.dylib` because ad-hoc code has no
common Apple Team ID. Repeating the rehearsal with the installed Apple
Development identity gave the shell, Python, FFmpeg, and native dependency
tree Team ID `VD7BYQ6ABM` and passed strict validation for all 393 final Mach-O
files with hardened-runtime flags.

The first development-signed replay then exposed the expected dynamic-code
boundary: macOS killed the spawned Python model worker with
`CODESIGNING: Invalid Page` while llvmlite allocated executable memory. The
bundled Python interpreter now receives only
`com.apple.security.cs.allow-unsigned-executable-memory`; the Tauri shell and
other native files do not. Verification rejects any accidental
`com.apple.security.cs.disable-library-validation` entitlement. This narrow
exception is required by the current Numba/llvmlite path and remains a
security surface to review if that dependency changes.

`scripts/build-atpiano-desktop rehearse-development` then passed from a fresh
stage on 2026-08-10:

- bundle audit: `passed`, 14,331 files, 1,067,822,645 bytes, 101 Python
  packages, 393 arm64 Mach-O files, and no score-runtime assets;
- strict nested signing: all 393 native files carried hardened runtime and the
  Apple Development authority with Team ID `VD7BYQ6ABM`;
- packaged 42-second replay: `passed`, authenticated sidecar ready in 2.30 s,
  651 exported events, MP3 playback ready, and CPU commit inference complete;
- outer App launch: the Tauri process reached its internally validated
  sidecar handshake, the sidecar listened only on loopback, and an
  unauthenticated handshake request returned HTTP 401; and
- normal Apple-event quit returned status 0 and left no Atpiano, Python,
  FFmpeg, or FFprobe process.

Local ignored reports are under `results/desktop-release-rehearsal/`, including
`bundle-audit.json` and `packaged-replay-development.json`.

The maintainer imported the Developer ID identity and granted Apple signing
tools access through the login-keychain partition list. A disposable hardened
timestamped `codesign` probe then succeeded without a prompt. The final fresh
`scripts/build-atpiano-desktop rehearse-developer-id` run on 2026-08-11
produced:

- a 14,326-file, 1,051,953,463-byte staged runtime and a 14,332-file,
  1,067,832,666-byte final App;
- 393 individually verified arm64 native signatures with hardened runtime,
  the Developer ID authority, and Team ID `VD7BYQ6ABM`;
- Apple notarization status `Accepted` for submission
  `f4c97e0d-83fb-4264-b9e5-0c5c516cc1ab`, followed by successful stapling;
- a signed `Atpiano_0.1.0_aarch64.dmg` whose mounted App passes strict
  `codesign`, Gatekeeper `Notarized Developer ID` assessment, and stapler
  validation; and
- a passing packaged replay report at
  `results/desktop-release-rehearsal/packaged-replay-developer-id.json`.

The DMG-installed UI check exposed one application defect rather than a
signing defect: recording import with a selected performer sent
`X-Atpiano-Performer-Profile`, but desktop CORS preflight did not allow that
header. The sidecar allowlist and regression test now cover it. A rebuilt,
renotarized DMG was installed and visibly imported the bundled 42-second WAV
as `Pianist`; settling completed with 151 notes, audio and performance views
remained available, and the score view correctly explained that the optional
score runtime was not installed. The imported session and older sessions
survived App replacement, quit, and relaunch. Normal menu quit reaped the
Tauri shell and Python sidecar with no orphan, and post-use strict signature
verification still passed.

Stage 1 is therefore passed for the real score-free bundle.

Stages 2 and 3 then landed as product-owned Atpiano code rather than a release
kit dependency:

- `update-server/atpiano.json` declares only product `atpiano`, repository
  `kzahel/atpiano`, prefix `/atpiano`, tags `desktop-v*`, and Tauri updates;
- `.github/workflows/desktop.yml` runs source gates, requires all eight macOS
  and updater secrets for release construction, stages/signs the nested
  runtime, creates a draft, validates the exact artifact matrix, writes
  checksums, attests artifacts, and finalizes only after successful gates;
- the release validators reject version, repository, route, target, public-key,
  artifact, digest, signature, and draft-state drift;
- the desktop runtime persists `cfu-id` outside the App, attaches `X-CFU-Id`,
  reports coherent app/web/sidecar/model identities, and coordinates sidecar
  stop and failure recovery around installation; and
- the React desktop composition owns scheduled/manual checks, explicit update
  states, progress and notes, package selection, capture/settling/score
  blockers, and install/relaunch UI while leaving hosted-web refresh behavior
  unchanged.

The Atpiano updater key was generated outside the repository. Its embedded
public key validates as a minisign public-key file and is explicitly rejected
if replaced with the canary key. Its encrypted private-key passphrase is held
in the local login Keychain for rehearsal; neither private material nor
passphrase entered the repository or logs. A disposable updater signature
probe passed before the full build.

The proposed `update-server/atpiano.json` also loaded successfully through the
actual `simple-app-update-server` product parser and has the same field shape
as the accepted canary: the only product-specific values are identity,
display name, repository, and `/atpiano` prefix.

The fresh updater-enabled `rehearse-developer-id` run on 2026-08-11 produced:

- a 14,326-file, 1,051,953,463-byte staged runtime and a 14,332-file,
  1,071,633,050-byte final App;
- 390 pre-signed staged native files and 393 individually verified hardened
  signatures in the sealed App;
- Apple notarization status `Accepted` for submission
  `a2dd7cd8-fae8-4f74-930b-d58742b5e960`, followed by successful stapling;
- `Atpiano_0.1.0_aarch64.dmg` (343,831,575 bytes, SHA-256
  `98940e75e7611094e288ecaf1ab4abd0a6f296322c68d1ce8706f5735d55fb6a`);
- `Atpiano.app.tar.gz` (349,235,977 bytes, SHA-256
  `fcd6ef73636490b702a3bb47f63bef99d8e60582a74e8a15424093804e1b95a0`);
- `Atpiano.app.tar.gz.sig` (404 bytes, SHA-256
  `498ede373fd8accb4854b2db3ad4c75dbeccaa49bb89a79d4a0724211b1e16c9`),
  cryptographically verified against the public key in `tauri.conf.json`; and
- another passing packaged replay, mounted-DMG signature/Gatekeeper/stapler
  validation, and post-use strict signature verification.

The DMG build replaced the prior user installation while preserving all
external sessions. The updater panel visibly reported app `0.1.0`, the web
build hash, Python sidecar `0.1.0`, model-pack ID/hash, macOS arm64, and the
anonymous install identity. That identity remained byte-for-byte unchanged
after normal quit/relaunch. A manual check reached the proposed production URL
and reported a bounded release-JSON error against the expected inactive HTTP
404. Normal quit left no Atpiano, Python, FFmpeg, or FFprobe process.

Validation at this hold includes 260 Python tests, 16 Node policy/contract
tests, 105 Vitest tests, 13 Rust tests, 12 release-tool tests, TypeScript
typecheck, production frontend build, Rust format/clippy, shell syntax, release
configuration validation, clean diff whitespace, and `npm audit` with zero
known vulnerabilities. The shared live service was stopped, so it was not
started or restarted.

At that point, no public release, production server activation, GitHub Actions
secret upload, tag push, repository visibility change, or installed old-to-new
update had been made. Stage 4 remained subject to explicit publication
approval.

The Homebrew FFmpeg rehearsal then exposed a needlessly broad GPL surface:
`--enable-gpl --enable-version3`, x264/x265, and 18 media libraries even though
Atpiano uses only WAV/MP3 probe, decode, concatenation, raw PCM, null decode
verification, resampling, and MP3 export. That artifact is retained only as
historical signing evidence.

The replacement is a tracked, deliberately minimal media build:

- `desktop-media/manifest.json` pins FFmpeg 8.1.2 and LAME 4.0 official source
  archives and SHA-256 values;
- FFmpeg reports `LGPL version 2.1 or later`, uses shared linking, enables only
  the required media surface, and contains neither `--enable-gpl` nor
  `--enable-nonfree`; LAME is a shared encoder library with its frontend and
  decoder disabled;
- the compact runtime is 2.8 MB, contains two binaries and six dylibs, uses
  only relative/system load paths, contains no maintainer home path, and has
  build identity
  `717d1632bf240196e8c482f00ee665a378b0255536379890cb3cea75a36fdd78`;
- `THIRD_PARTY_NOTICES.md` and the upstream license texts are installed in the
  App, while the deterministic `Atpiano_<version>_media-sources.tar.gz`
  contains the exact upstream archives, complete build code/configuration,
  notices, and a reconciled hash manifest; and
- the tagged workflow uploads and attests that source archive, and the draft
  finalizer rejects a release where it is absent or unexpected.

The new runtime passed its own WAV/MP3 exercise, the real upload adapter for
both formats, a two-segment playback export through `libmp3lame`, probe and
full decode verification, and full desktop staging. The staged score-free
runtime has 14,321 files and 1,015,793,592 bytes with 378 arm64 native files.
Its sidecar smoke remained authenticated, score-free, and cleanly reaped at
parent EOF.

A fresh `scripts/build-atpiano-desktop rehearse-developer-id` then accepted
the complete LGPL candidate without an interactive Keychain prompt:

- the sealed App has 14,327 files, 1,035,469,721 bytes, 381 individually
  verified hardened arm64 signatures, and a reconciled
  14-file/2,871,458-byte media category;
- Apple notarization returned `Accepted` for submission
  `e32db6b4-4161-4977-a09a-865b6175decf`, after which App stapling succeeded;
- `Atpiano_0.1.0_aarch64.dmg` is 328,349,947 bytes with SHA-256
  `fc1b975369dfef999bcce749a6e7d13acfde19aa953a264ed31bec226eef703e`;
- `Atpiano.app.tar.gz` is 333,161,900 bytes with SHA-256
  `b18046bc60553e614da19d89fef68e3d1df54d5d475229ce8a8c0bf567a28905`;
- `Atpiano.app.tar.gz.sig` is 404 bytes with SHA-256
  `e9ef47b042b71fe6facacc86cb7d443cbbe2f8b5242b540cdf3ffd4618044969`
  and verifies against the embedded updater public key;
- `Atpiano_0.1.0_media-sources.tar.gz` is 13,220,731 bytes with SHA-256
  `c662d0b3b2aadc11a170534cb83a7dcd071443be74a9ec8e3255ce29a58a78c2`
  and passes the corresponding-source validator; and
- packaged replay, strict App and mounted-DMG signature checks, Gatekeeper
  `Notarized Developer ID` assessment, and stapler validation all passed.

The prior user App was moved recoverably to Trash and the fresh App was
installed from the signed DMG. Existing external sessions survived. The UI
imported the bundled 42-second WAV as `Pianist`, settled to a saved 151-note
performance, exposed audio and performance views, and correctly kept score
generation unavailable. The new session and installation UUID
`65f89f6a-a49e-4072-96d9-9a0c29e0a469` survived normal quit/relaunch. Both
normal menu quits reaped the Tauri shell, Python sidecar, FFmpeg, and FFprobe;
post-use strict signature, Gatekeeper, and stapler validation still passed.

Stage 1 is current for the LGPL release candidate.

The maintainer then approved the separate source-publication and public-CI
rehearsal boundary. The release-lane work was rebased without force over the
new native Windows runtime commits on `main`, and this tactical moved from
number 049 to 051 to preserve their accepted numbering. The exact candidate
tree and reachable history were scanned again before publication. They had no
high-confidence credential or private-key findings, no sensitive
key/certificate filenames, and no tracked model checkpoint. The only reviewed
personal data was the approved maintainer identity and previously documented
historical private-LAN address.

`kzahel/atpiano` became public on 2026-08-11. It has no root license file and
GitHub detects no repository license, so this is public source under ordinary
copyright restrictions rather than an open-source license grant. It still has
zero Actions secrets, zero GitHub releases, and no release tag or active
production product route.

The first public workflow executions exposed two source-lane assumptions:
Ubuntu needed FFmpeg for existing recording-import tests, and the macOS-only
Tauri crate should not be compiled as a Linux desktop application. The final
workflow installs FFmpeg only for Ubuntu source tests and runs Rust checks on
macOS 26. An ordinary
[public push run](https://github.com/kzahel/atpiano/actions/runs/31516122672)
then passed the complete Ubuntu source and macOS Rust jobs, with release jobs
skipped as designed.

The final
[manual rehearsal](https://github.com/kzahel/atpiano/actions/runs/31516446700)
passed both prerequisite jobs on attempt 2. Its signed build job stopped in 19
seconds at `Require complete release credentials` with the exact annotation
`Desktop builds require both Atpiano updater signing secrets`. All keychain,
certificate, notarization, packaging, and artifact steps were skipped, and the
release finalizer did not run. This proves that the public lane fails closed
before signing when credentials are absent without invoking the maintainer's
local Keychain.

The publication prerequisites subsequently completed. All 11 Actions secret
names were configured and verified. Exact-candidate
[rehearsal run 32666483577](https://github.com/kzahel/atpiano/actions/runs/32666483577)
passed both signed platforms at commit
`ed76f74686981990ce230679ccae9af19dfd61f2`.

## Published 0.1.0 Execution Record

Annotated tag `desktop-v0.1.0` resolves to the same candidate commit. Tagged
[run 32669326956](https://github.com/kzahel/atpiano/actions/runs/32669326956)
passed the macOS and Windows build gates. The first macOS attempt successfully
notarized and stapled the App, submitted the DMG as Apple request
`5862795e-692d-4ef4-b6ea-4c2e3e91ff16`, then encountered a transient
`notarytool` bus error while waiting. The failed-job rerun passed app and DMG
notarization, stapling, Gatekeeper, packaged replay, release retention, and
build-provenance attestation.

The exact published macOS files are:

- `Atpiano_0.1.0_aarch64.dmg`: 575,135,484 bytes, SHA-256
  `704b1623c5cfdc55b206ed2aa067aa22d931f0078549515c56266a0037720edd`;
- `Atpiano.app.tar.gz`: 584,024,206 bytes, SHA-256
  `369d7efa775adb145ef21d53fa54b15aab78157bec94993d4aef5cd21eb54996`;
- `Atpiano.app.tar.gz.sig`: 404 bytes, SHA-256
  `6fdf3cddb73ccfadaf300463a43188e693e723f20e535ce24fc4646327fd557d`;
  and
- `Atpiano_0.1.0_media-sources.tar.gz`: 13,220,731 bytes, SHA-256
  `c662d0b3b2aadc11a170534cb83a7dcd071443be74a9ec8e3255ce29a58a78c2`.

The automatic finalizer failed closed before draft creation because its
macOS selector expected a historical architecture-suffixed updater name.
Recovery used only the retained, attested tagged artifacts. Both updater
signatures and the notarized DMG were independently reverified, every local
hash matched GitHub's digest, and the exact draft validator passed. Commit
`f1c905e` fixes and tests the Tauri v2 `Atpiano.app.tar.gz` contract for future
tags. The public/latest release was published on 2026-08-24.

The production updater now returns exact signed `0.1.0` metadata for
`darwin/aarch64/0.0.0` and HTTP 204 for `darwin/aarch64/0.1.0`. The response
signature matches public `latest.json`. This completes initial publication,
but not the real installed `0.1.0 -> 0.1.1` campaign or compatible acquired
runtime persistence proof.

## Published 0.1.1 And Installed Baseline Record

Exact-candidate rehearsal
[32703066998](https://github.com/kzahel/atpiano/actions/runs/32703066998)
and tagged
[32707274179](https://github.com/kzahel/atpiano/actions/runs/32707274179)
passed from commit `66a82e2d4d87795c79ef286cb5f9709adb13e6c2`. The
automatic finalizer selected the corrected Tauri v2 updater filename, created
the exact two-target metadata, reconciled GitHub digests, attested the release,
and published without manual recovery. The public macOS files are:

- `Atpiano_0.1.1_aarch64.dmg`: 575,149,993 bytes, SHA-256
  `0cb3e9ea3c5528c76a6ef177700e80b3381881e50d2dfac5a938035c3392ccde`;
- `Atpiano.app.tar.gz`: 584,017,257 bytes, SHA-256
  `01985b8f1c94dbc6a13e22eef96aaddf03ae8deca7cc9186381888f080804e8c`;
  and
- `Atpiano.app.tar.gz.sig`: 404 bytes, SHA-256
  `366ea0e5c6976eb140ff59e5de9c113ef1c50d3e935c9cc654d6eb96e17664ee`.

Before publication, the exact public `0.1.0` DMG was installed in
`/Applications`. Developer ID, notarization, stapling, and version `0.1.0`
were independently reverified. Through the published dialog, the maintainer
acknowledged the displayed education/research-only and absent-upstream-license
notice and downloaded the model directly from upstream. Relaunch selected the
external runtime, and the frontend generated a retained 12-note, three-measure
score through the pinned runtime. Its current MusicXML SHA-256 is
`93eb41e1988d6e592db971aa26f9601338865099fb62e75f46744fd9b052d58a`.

The pre-update evidence freezes the installation-ID hash
`e7a100200ebdd87edc5bd784428e8e5632dc82f85270566df76e6dd96086e04f`,
acknowledgement hash
`b24f7e911e1a43178db0e05a6ade39f9dc17067898724ea37259c073cc4080cd`,
checkpoint hash
`7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`,
and support-manifest hash
`7b20d437348f900c5d59fcc1a8706e12994644fa9f8e259fb99bc47f005ec041`.
Production now offers signed `0.1.1` to this App and returns HTTP 204 to
`0.1.1`.

## Tart Installed Update Acceptance Record

A claimed macOS 26.2 arm64 Tart appliance began without Atpiano or application
data. Its guest-agent administration, resident semantics, and target-local
input paths passed with outer input prohibited. Tart framebuffer captures were
used only to inspect WKWebView pixels that the guest Quartz capture omitted.

The appliance downloaded the exact public `0.1.0` DMG and verified SHA-256
`704b1623c5cfdc55b206ed2aa067aa22d931f0078549515c56266a0037720edd`.
The installed App reported `0.1.0` and passed strict code-signature,
notarized-Developer-ID, Gatekeeper, and stapler validation. Its published
dialog displayed the absent-upstream-license, education/research-only,
noncommercial, no-redistribution, local-code-execution, and byte-count notice.
Download remained gated by its initially unchecked acknowledgement.

After acknowledgement, direct acquisition installed the 389,829,880-byte
checkpoint and approximately 1.3 GB external runtime. Relaunch passed that
runtime to the sidecar. Importing the App's 42-second packaged fixture produced
a retained 151-note session and a two-part, 12-measure score. Before update,
the score producer recorded application `0.1.0`; its MusicXML SHA-256 was
`a70be72d666dc535d7a8f8d4217c63710612fec97053ccce9de8995f3d169dc7`.

The pre-update external-state hashes were:

- installation ID:
  `fd34198438a04a61355bff693dcbc8f98c395f382499b66c88c72a2e34e24d3e`;
- acknowledgement:
  `45f89450dc2e1133cf5da91b008221d2beba4107d2204dc618608fa2c6f5cf4e`;
- active-runtime record:
  `8abcfd60b1def3d01b97f3dc0a9041a199ed9b6fdb47feb870b2f455aa6bd5ee`;
- checkpoint:
  `7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`;
- runtime manifest:
  `90a94c99863d7e64f3eb91c735fd5f30dccbc232327ab1f7cd5365803e532cb1`;
  and
- support manifest:
  `7b20d437348f900c5d59fcc1a8706e12994644fa9f8e259fb99bc47f005ec041`.

The in-app updater detected `0.1.1`, visibly downloaded the signed 557 MiB
payload, replaced the App, and relaunched. The installed App reported `0.1.1`
and again passed strict signing, notarized-Developer-ID, Gatekeeper, and stapler
validation. Exactly one new App/sidecar pair remained. Every external-state
hash above and the retained session, events, MIDI, pre-update score record, and
MusicXML hashes were unchanged immediately after replacement.

The retained score opened without a notice or model download. **Refresh score**
then produced a new record whose producer application is `0.1.1`, checkpoint is
the same exact SHA-256, and MusicXML remains byte-identical at the hash above.
The manual updater check reported **Atpiano is up to date**. A normal quit left
no App, sidecar, or model-worker orphan. The temporary source fixture was
removed, and the appliance was suspended before its exclusive claim was
released.
