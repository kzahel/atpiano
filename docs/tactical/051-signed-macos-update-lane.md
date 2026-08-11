# 051 — Signed macOS Update Lane

Topic: public-desktop-release

Status: **active at binary-publication hold. The source repository and CI lane
are public with no declared Atpiano source license. The release lane, desktop
updater, and complete LGPL media candidate passed signed/notarized installed
acceptance on 2026-08-11. The published `0.1.0 -> 0.1.1` campaign requires
explicit approval.**

## Outcome

Turn the accepted R5 Tauri boundary into Atpiano's first repeatable signed
macOS arm64 release lane, then prove one real installed signed update from
`0.1.0` to `0.1.1` through the production update service.

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
- Keep the ordinary release score-free. Do not stage, archive, attest, or
  publish MIDI2ScoreTransformer source or checkpoint.
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
   stapling, and the absence of forbidden score assets.
6. Write `SHA256SUMS`, attach GitHub artifact attestations for distributable
   files, and publish only from the successful finalizer after approval.

The workflow must not inherit the canary's five-target requirement. Its
validator consumes Atpiano's explicit supported target/artifact declaration.

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
  identity, model-pack identity/hash, and stable installation identity.

Before `downloadAndInstall`, the application must prove that no capture is
requesting, warming, recording, or stopping; no session or import is settling;
and no score job is running. After successful replacement, normal Tauri exit
must gracefully stop and reap the Python sidecar before relaunch. Installation
failures retain the running application and recovery action.

## Stage 4 — Installed Acceptance Campaign

After the publication hold is approved:

1. Freeze the exact `desktop-v0.1.0` DMG, hashes, workflow, commit, update
   metadata, and macOS testbed identity.
2. Install its App from the DMG, launch it, and complete a representative
   Atpiano flow.
3. Publish a `desktop-v0.1.1` successor with an unmistakable visible change.
4. Discover, download, install, and relaunch the successor through the
   production `/atpiano` route.
5. Verify all component identities, workspace/session persistence, score-free
   sidecar function, unchanged installation UUID, and zero orphan processes.
6. Inspect redacted shared-server requests for startup, manual discovery, and
   relaunched startup, and retain an evidence document comparable to the
   canary record.

## Publication Hold

Stop before activating the product configuration on the shared production
server, pushing the first release tag, or publishing the first release.
Repository visibility has a separate preflight and approval boundary. Present:

- proposed version and tag;
- complete public artifact set;
- exact product route and JSON configuration;
- signing/notarization rehearsal commands and results;
- public-tree/history and distribution-license preflight;
- exact remaining risks and manual steps.

## Validation

- Existing Python, frontend, contract, Rust, and packaging tests remain green.
- Focused updater policy, schedule, state, identity, and lifecycle tests pass.
- Configuration and draft-finalization tests reject version drift, unexpected
  targets, missing artifacts, absent signatures/digests, and forbidden score
  content.
- The staged and final App audits reconcile all files and bytes, validate all
  Mach-O architectures/load paths/signatures, and remain immutable after use.
- CI proves signed artifact construction; only Stage 4 proves installed
  old-to-new update behavior.

## Rollback

The release workflow, product configuration, updater plugin, and desktop-only
UI are additive. Hosted web operation and its refresh notice remain
independent. Removing the updater configuration and desktop composition
returns to the accepted R5 boundary without migrating or deleting the external
workspace. Draft GitHub Releases and an unactivated product JSON are not
eligible for production update checks.

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

Source visibility and the fail-closed CI rehearsal are complete. The remaining
gate is approval to upload the eight macOS/updater Actions secrets, activate
the production product configuration, push the first release tag, publish the
binary release, and run the real installed `0.1.0 -> 0.1.1` campaign.
