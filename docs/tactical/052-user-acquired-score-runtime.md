# 052 — User-Acquired Desktop Score Runtime

Topics: `desktop-score-runtime-footprint`, `public-desktop-release`,
`performance-to-notation`

Status: **implementation active as a proof-of-concept prerequisite for the
first public desktop tag.** The external asset contract, transactional native
controller, shared consent/management dialog, and macOS arm64 score-support
package are implemented. The Windows x64 score-support package is also built
and audited under x64-on-ARM64 emulation. A real acknowledged model
acquisition, installed score validation, complete Windows application, and
both signed update campaigns remain. Dependency cleanup is explicitly
deferred.

## Goal

Ship signed macOS arm64 and Windows x86_64 Atpiano applications that contain no
MIDI2ScoreTransformer repository or checkpoint, but can visibly offer, acquire,
validate, activate, use, and remove the exact upstream research runtime after
an explicit education/research-use acknowledgement. The macOS application is
notarized; the Windows installer is Authenticode-signed.

This tactical ends when clean installed applications on both operating systems
can acquire the runtime directly from the pinned upstream locations, relaunch
into `score_available=true`, generate matching accepted retained scores,
preserve that capability through their signed `0.1.0 -> 0.1.1` updater paths,
and return safely to the score-free state after removal. Tactical
[`051-signed-macos-update-lane.md`](051-signed-macos-update-lane.md) continues
to own the macOS signing/update lane. Tactical
[`053-windows-desktop-release-lane.md`](053-windows-desktop-release-lane.md)
owns Windows packaging, signing, `machine-control` acceptance, and updater
parity. The public-release topic coordinates one two-platform tag.

## Entry Evidence

- `uv run atpiano setup-midi2score` already clones upstream commit
  `115432bda16ca16e0fec2e9465788f2ba369971f`, downloads the v0.0.1
  389,829,880-byte checkpoint, verifies SHA-256
  `7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`,
  and builds an ignored internal Python 3.11 environment.
- That command performs no disclosure or acknowledgement. It is an internal
  developer setup path and must not become the public desktop installer.
- The upstream repository and checkpoint release still have no explicit
  source/checkpoint license notice. The paper record is CC BY 4.0, but that
  does not establish the rights for the linked code or weights.
- A 2026-08-23 GitHub metadata/root inspection also found no detected license
  or root license file for the pinned `ScoreTransformer` and
  `amtevaluation.github.io` forks. The custom `music21` fork has a root
  `LICENSE`, but its exact pinned commit and obligations still require review.
  The current requirements import the two unlicensed forks even though prior
  tracing suggests their evaluation paths may be removable from inference.
- The maintainer accepts those helper dependencies as a bounded noncommercial
  proof-of-concept risk for the first release. Their removal and license
  follow-up are later work, not a reason to delay this tactical. This decision
  does not claim that noncommercial use or a future takedown promise grants a
  license.
- The accepted internal App proves that the complete runtime can generate the
  expected MusicXML and alignment on macOS arm64. It labels the runtime
  `internal_only=true`, `public_distribution=false`, and
  `license.status=provisional-unconfirmed`.
- The adapter itself is deliberately CPU-only: it loads the checkpoint with
  `map_location="cpu"`, moves the model to CPU, and records `device=cpu`.
  Windows x64 dependency resolution and packaged output parity remain to be
  proven; GPU support is not required.
- The native Windows x64 application core, Basic Pitch ONNX CPU path, Transkun
  CPU path, production frontend, storage, and unpackaged server already pass.
  The configured Windows 11 ARM64 `machine-control` testbed is ready and can run
  the x64 package under OS-supported emulation, but that is not native x64
  timing evidence.
- The ordinary signed candidate rejects every internal score-runtime asset and
  reports `score_available=false`. Its updater, graceful sidecar shutdown,
  install blockers, stable installation UUID, external workspace, and signed
  `0.1.0` artifact rehearsal are already accepted.
- The current Tauri supervisor looks only for
  `Contents/Resources/desktop-runtime/score-runtime`, and its React runtime
  fixes the loopback URL and bearer credential at application bootstrap.
  Activation therefore requires a normal relaunch rather than a sidecar
  hot-swap.

## User-Visible Outcome

When score generation is unavailable in a Tauri desktop build, the score card
offers **Enable score generation** instead of only stating that the runtime is
missing. Hosted web and fixture compositions do not show that action.

The action opens one accessible modal with:

- the model name and research purpose;
- the explicit statement that upstream source and weights currently have no
  confirmed license;
- the boundary **for education or research use only**;
- the statement that Atpiano neither includes nor licenses the assets and that
  the notice is not a grant of permission;
- direct links to the user-acquired MIDI2ScoreTransformer repository, the
  checkpoint release, paper, and tracked Atpiano acquisition record;
- the exact expected checkpoint download size and a measured total installed
  space estimate;
- the statement that downloaded Python source will run locally on the device;
- an unchecked acknowledgement; and
- **Cancel** and disabled-until-acknowledged **Download research model**
  actions.

The proposed core copy is:

> MIDI2ScoreTransformer is an optional research model. Its upstream source and
> checkpoint do not currently include an explicit license. Atpiano does not
> include or license those assets. If you have the right to use them, Atpiano
> can download the exact upstream files for education or research use only and
> run them locally on this device. Do not use them commercially or redistribute
> them.

The acknowledgement label is:

> I understand this notice and want to download the optional research model.

Final acceptance includes a rendered-copy review. The implementation may make
the wording clearer, but it must not imply that Atpiano, the paper's CC BY 4.0
notice, or clicking the checkbox grants rights to upstream source or weights.

After acknowledgement, the same surface reports source/checkpoint progress,
verification, local installation, and bounded errors. Successful installation
offers **Relaunch to enable scores**. Once active, a desktop settings/details
surface reports the runtime contract, upstream commit, checkpoint hash,
accepted notice version, installed size, and **Remove research model**.

## Frozen Product Boundaries

- Support the signed macOS arm64 and Windows x86_64 desktop compositions. Keep
  the acquisition state machine, schemas, notice, and UI shared; allow only
  platform-specific support-layer manifests, paths, packaging, and process
  mechanics.
- Do not add acquisition to the hosted family service, browser app, CLI startup,
  or generic Python API.
- Do not download anything before explicit acknowledgement.
- Do not ship, mirror, cache on Atpiano infrastructure, attach to a GitHub
  Release, attest, or include in corresponding sources the
  MIDI2ScoreTransformer repository or checkpoint. The pinned Python support
  environment may provisionally retain ScoreTransformer and MUSTER.
- Do not run `git`, `uv`, `pip`, package build isolation, or a compiler on the
  user's machine.
- Do not derive, strip, quantize, or reserialize the checkpoint. Acquire and
  validate the exact upstream release asset.
- Do not treat the acknowledgement as telemetry, an account entitlement, or a
  remote authorization check. It stays on the device.
- Do not make score installation a prerequisite for capture, transcription,
  playback, piano roll, keyboard, existing MusicXML, alignment, or export.
- Do not publish a release or activate the update route inside this tactical.

## Phase 0 — Time-Boxed Support Inventory

Before application work, inventory the complete measured inference path:

1. pinned MIDI2ScoreTransformer source;
2. released checkpoint;
3. custom `music21`, `ScoreTransformer`, and `muster` forks;
4. PyTorch, Transformers, Lightning, Pretty MIDI, and all imported transitive
   distributions;
5. Atpiano adapter/postprocessor code; and
6. any data, font, binary, or native library loaded during retained inference.

For every component, record version/commit, acquisition URL, SHA-256 or tree
hash, installed bytes, actual inference use, detected license, and available
notices. This is an inventory and reproducibility step, not an attempt to
resolve every research dependency before publishing the proof of concept.

Use the already-proven isolated macOS Python 3.11 environment as the first
signed support-layer reference, removing only the MIDI2ScoreTransformer
repository, checkpoint, mutable caches, development launchers, and
internal-only manifest. Resolve and freeze an equivalent inference-only
Windows x64 Python 3.11 support layer and prove matching retained output before
it enters the Windows installer. Retain the pinned ScoreTransformer and MUSTER
packages provisionally and record their missing license metadata in both public
dependency inventories. Do not spend this slice consolidating onto Python 3.10,
removing eager evaluation imports, minimizing the environments, or adding
native Windows ARM64 packages.

Stop only for an explicit upstream prohibition, a direct maintainer objection,
or a technical/security failure that makes the package unsafe to publish.
Otherwise record the limitation and proceed. The education/research wording
remains a product boundary and must not be described as an upstream license.

This phase freezes the expected source archive bytes. Use a commit-addressed
upstream HTTPS archive rather than `git clone`; hash the downloaded archive and
the normalized extracted tree. If GitHub later changes archive bytes at the
same URL, the client fails closed until a signed Atpiano update changes the
contract.

## Phase 1 — Versioned Acquisition Contracts

Add a tracked `desktop-score/acquisition.json` source document with schema
`atpiano.score-acquisition.v1`. Desktop staging copies it into the signed
runtime and the bundle audit reconciles it byte-for-byte.

Required fields include:

- acquisition-contract ID and notice version;
- the MIDI2ScoreTransformer repository URL, exact commit, source-archive URL,
  archive SHA-256, normalized tree SHA-256, expected bytes, and extracted
  bounds;
- checkpoint release page, direct URL, SHA-256, and expected bytes;
- allowed schemes, hosts, redirect hosts, and path prefixes;
- signed score-support-layer ID and manifest hash;
- compatible score-runtime schema, score-pipeline revision/fingerprint, App
  version range, exact platform/architecture support-layer identity, and CPU
  execution policy;
- minimum free bytes, maximum download bytes, maximum expanded bytes, maximum
  entry count, and forbidden archive entry types; and
- the exact notice/link identifiers rendered by the client.

Define two mutable documents outside the App:

- `atpiano.score-acknowledgement.v1`: local acceptance receipt with notice,
  contract, App version, UTC time, URLs, and hashes but no personal or stable
  installation identity; and
- `atpiano.score-runtime-installation.v1`: active runtime manifest with exact
  asset/support identities, installed paths and sizes, validation time, and
  compatibility fields.

Parse and validate all three schemas on the native side with unknown fields
rejected. The Python `inspect_score_runtime` boundary consumes only an already
validated installation and retains independent source/checkpoint checks before
reporting capability.

## Phase 2 — Transactional Native Acquisition

Implement acquisition in the Tauri composition. The native boundary owns
networking, filesystem publication, progress, cancellation, and removal. The
Python sidecar never receives a general downloader or arbitrary URL.

Use:

```text
app_data_dir()/score-runtimes/.staging/<operation-id>/
app_data_dir()/score-runtimes/<acquisition-contract-id>/
app_config_dir()/score-runtime.json
```

The native operation must:

1. accept the exact current notice/contract acknowledgement;
2. prove there is no concurrent acquisition, removal, update installation,
   capture, settlement/import, or score job;
3. check free space against the maximum staged plus final footprint;
4. create a new private staging directory with no unresolved symlink target;
5. download only allowlisted HTTPS assets with bounded redirects, timeouts,
   byte limits, cancellation, and no credentials;
6. stream each SHA-256 while writing a temporary file and reject mismatches;
7. extract the source archive with traversal, absolute-path, symlink, hardlink,
   device, entry-count, and expanded-byte defenses;
8. verify the normalized tree and required file allowlist;
9. assemble a runtime using only the signed support layer and verified acquired
   assets;
10. run bounded import and retained score-smoke validation without network;
11. write and fsync the installation manifest and acknowledgement receipt;
12. atomically rename the complete runtime and then replace the active pointer;
    and
13. delete or quarantine stale staging data without touching a previous valid
    installation.

Expose native status, acquire, cancel, remove, and prepare-relaunch commands
plus bounded progress events. The UI must not supply URLs, paths, hashes,
commands, or manifest contents; it may select only the acquisition action for
the contract embedded in the signed App.

A request failure, checksum mismatch, disk exhaustion, extraction rejection,
validation failure, cancellation, App quit, or native panic must leave the old
active runtime unchanged. Logs and UI errors contain no local username, home
path, installation ID, token, cookie, or arbitrary upstream response body.

## Phase 3 — Sidecar Selection And Safe Relaunch

Change the supervisor from the immutable bundled `score-runtime` path to the
active external runtime selected by the native validator. Pass no score path
when the active document is missing, stale, incompatible, or invalid.

Preserve these startup properties:

- the App reaches its ordinary score-free workspace even when all external
  runtime files are corrupt or unreadable;
- the sidecar independently validates schema, source commit/tree, checkpoint
  hash, support-layer ID, pipeline compatibility, and CPU execution;
- only a complete match produces `score_available=true`;
- capability details distinguish `not-installed`, `incompatible`, `invalid`,
  and `available` without exposing private paths; and
- all runtime caches and generated outputs stay outside the App and acquired
  immutable asset directory.

Do not hot-swap the current React `DesktopRuntime`: its loopback URL and bearer
token are fixed at bootstrap. After install or removal, reuse the updater's
idle-state blockers and graceful sidecar shutdown, then relaunch the App.
Failure before relaunch leaves the current sidecar alive. Failure after a
prepared shutdown must reuse the existing sidecar recovery behavior.

## Phase 4 — Shared React Dialog And Management UI

Extend the desktop bootstrap with a narrow score-runtime manager rather than
adding acquisition methods to the generic hosted runtime. The score view uses
that manager only when the composition is Tauri desktop.

Implement and test:

- unavailable score call to action;
- disclosure dialog and unchecked acknowledgement;
- links opened through a bounded desktop/browser mechanism;
- exact download/installed-size copy from the signed contract;
- progress by source, checkpoint, verification, and installation;
- cancellation before publication;
- bounded retry and offline errors;
- relaunch activation with current busy reason;
- installed provenance/details;
- incompatible-runtime recovery; and
- removal confirmation that explicitly preserves sessions and generated
  artifacts.

The modal traps focus, restores focus to its invoking control, closes with
Escape only before an irreversible operation, uses a real checkbox/label, and
announces progress and errors without repeated live-region noise. Download
does not begin merely because the score view, modal, or details section opens.

## Phase 5 — Packaging And Public-Content Gates

Extend desktop staging and release validation so each exact signed application
may contain the tracked acquisition controller, contract, and its provisionally
accepted platform support layer while continuing to reject acquired model
assets.

The audit must:

- reconcile all support-layer packages, native files, provenance, known
  license status, available notices, architectures, load paths, entitlements,
  and bytes. Allow ScoreTransformer and MUSTER only as exact inventoried
  provisional dependencies;
- forbid the MIDI2ScoreTransformer repository, `MIDI2ScoreTF.ckpt`, the
  checkpoint hash, internal score manifests, `.git`, acquisition staging,
  acknowledgement, and active-runtime files from the App, DMG, updater
  archive, GitHub Release, attestations, and media corresponding-source
  archive;
- verify every acquisition URL is upstream HTTPS and absent from the updater
  product configuration;
- confirm the App can run with networking disabled and no acquired runtime;
- confirm ordinary launch never creates the acknowledgement or starts an
  upstream request; and
- treat any forbidden asset as a release-blocking failure, not a warning.

The signed support layer may increase App size. Record exact staged, App, DMG,
updater, support-layer, and post-acquisition installed sizes. Do not claim the
feature preserves the current download size until those measurements exist.

## Phase 6 — Automated Validation

### Contract And Python

- Acquisition, acknowledgement, and installation schemas reject drift and
  unknown fields.
- Runtime inspection rejects source, tree, checkpoint, support-layer, pipeline,
  architecture, or manifest mismatch.
- The score adapter runs with networking disabled and writes caches only to
  mutable application data.
- Retained fixtures preserve model-native tokens, plausible MusicXML, exact
  pitch semantics, source alignment, provenance, and bounded failures.
- The existing internal CLI remains explicitly internal; its current README
  warning is sufficient for this proof-of-concept slice.

### Native

- No acceptance means no network or filesystem mutation.
- Invalid URLs, hosts, paths, redirects, content lengths, hashes, archive
  entries, extracted sizes, and runtime manifests fail closed.
- Cancellation, network loss, full disk, interrupted process, and stale staging
  recover without publishing partial state.
- Concurrent acquire/remove/update requests deduplicate or reject cleanly.
- Acquisition and activation blockers cover capture, settlement/import, score
  work, and desktop update installation.
- Active runtime selection survives App updates and rejects incompatible
  releases.
- Removal cannot follow symlinks or escape the exact versioned runtime root.
- Error and log redaction is covered by adversarial fixtures.

### React

- The action appears only in the desktop composition when score capability is
  unavailable.
- The primary action is disabled until acknowledgement and cannot be triggered
  twice.
- Copy, links, size, progress, cancel, retry, relaunch, incompatible, details,
  and removal states render accessibly.
- Hosted, authenticated-family, fixture, and already-available score behavior
  remains unchanged.
- Capture/settlement/update blockers are visible and preserve the current
  operation rather than forcing a relaunch.

### Packaging And Release

- Clean and dirty staging tests retain the score-asset prohibition.
- Bundle inventory and archive scans inspect names, bytes, known hashes, and
  nested archives rather than relying only on paths.
- The complete source, frontend, Rust, packaging, updater, release-validator,
  platform-signature, macOS notarization/Gatekeeper, and immutability gates
  pass.
- Clean macOS arm64 and Windows x86_64 CI builds can construct their
  acquisition-capable score-assets-free applications using no untracked local
  runtime.

## Phase 7 — Installed Acceptance And Update Handoff

Before `desktop-v0.1.0` may be pushed, perform the following visible acceptance
with the exact signed macOS candidate and again with the exact signed Windows
candidate under tactical 053's testbed contract:

1. install from the notarized DMG or signed per-user Windows installer and
   confirm score-free startup;
2. open the score view and confirm no upstream request precedes acceptance;
3. review the final disclosure and cancel once, proving no mutation;
4. acknowledge, download directly from upstream, and retain redacted request
   destinations plus hashes and installed manifest;
5. relaunch and confirm coherent component/runtime identities;
6. import or replay the retained 42-second performance and generate a current
   score, MusicXML, alignment, and provenance;
7. quit normally and prove zero Tauri, Python, FFmpeg, FFprobe, or score worker
   orphan;
8. relaunch offline and generate another score without an acquisition request;
9. inspect the used App and external runtime for bundle immutability and exact
   separation; and
10. remove the research model, relaunch, confirm score-unavailable degradation,
    and verify sessions and existing artifacts remain usable.

Tacticals 051 and 053 then repeat the important path through production on
their respective operating systems:

- publish and install `0.1.0`;
- acquire and exercise the score runtime;
- publish `0.1.1` with an unmistakable visible change but a compatible
  acquisition contract;
- discover, download, install, and relaunch `0.1.1` through the production
  updater route;
- prove the acknowledgement and external runtime persist unchanged;
- generate a score after update with no upstream reacquisition; and
- retain redacted updater and upstream-acquisition request evidence separately.

Only both signed old-to-new campaigns establish auto-update acceptance for the
score-capable public release.

## Acceptance

- The published App is score-capable but contains no MIDI2ScoreTransformer
  repository or checkpoint.
- No model network request or local receipt exists before explicit consent.
- The rendered dialog accurately communicates education/research-only use,
  absent confirmed upstream licensing, local code execution, size, provenance,
  and non-redistribution.
- Exact upstream assets are downloaded, bounded, hashed, transactionally
  installed outside the App, and independently revalidated by the sidecar.
- Score generation matches retained internal-runtime evidence.
- Failure, cancellation, incompatibility, removal, and absence never impair the
  rest of Atpiano.
- Signed desktop updates preserve a compatible acquired runtime without a new
  download and require new acknowledgement when the notice or asset contract
  changes.
- The exact release artifacts and GitHub evidence pass Windows/macOS signing,
  macOS notarization, updater, recorded-provenance, and
  forbidden-model-content gates.

## Execution Record

Implementation began on 2026-08-23 with the signed-input contract. The tracked
`desktop-score/acquisition.json` fixes notice v1, both exact release targets,
the CPU policy, upstream links, bounded ZIP extraction, and the following
external asset facts:

- commit ZIP: 187,103 bytes, 21 entries, 332,507 expanded bytes, SHA-256
  `42953b3d184807b9e4d18f2b9280e8e7593d5b74890f8d9755187f0e27537cb7`
  and normalized extracted-tree SHA-256
  `86274feed5a9d28c41a314d1ea435fc84e67a053293b281d7b1e9b86da431516`;
- checkpoint: 389,829,880 bytes and the already retained SHA-256
  `7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`;
  and
- combined download copy: 390,016,983 bytes with an intentionally
  conservative 1.5 GB installed estimate and 2.5 GB free-space gate.

The exact commit ZIP was downloaded from GitHub over HTTPS for this
measurement. The checkpoint was not downloaded again; GitHub's release server
confirmed its retained byte count. Strict Pydantic contracts now reject
unknown fields, non-HTTPS or unlisted hosts, inconsistent byte totals,
unsupported target pairs, receipt identity creep, and unsafe active-runtime
paths. The three focused contract tests pass. The platform support-layer
inventory/hash, native transactional downloader, and UI remain active work.

The first native controller now embeds and independently validates that
contract, reports score-runtime status without making a request, and exposes
acknowledged acquire, cancel, and remove commands only to the Tauri
composition. Acquisition uses fixed URLs, HTTPS-only bounded redirects,
content lengths, streaming SHA-256, cancellation, free-space checks, exact ZIP
root/path/type/count/expanded-byte limits, a cross-platform normalized tree
hash, and private same-filesystem staging. It copies only the signed target
support layer, writes the existing score-runtime manifest, publishes the
complete directory before atomically activating its relative pointer, and
rolls back unpublished staging/final data on failure. Removal first validates
the exact contract-relative target and never follows a runtime-root symlink.

Desktop startup now selects only a valid external active record and otherwise
starts score-free. The Python boundary independently rehashes acquired source
and checkpoint assets before exposing score capability. Publication rollback
tracks only the directory and receipt created by the current operation; an
inactive pre-existing runtime is rejected before any download. Desktop update
installation is also rejected while acquisition or removal is active.

The shared React dialog now appears only through the Tauri desktop manager. It
renders the exact notice, unchecked acknowledgement, byte counts, bounded
upstream links, progress/cancel/error states, relaunch, pinned provenance, and
confirmed removal copy. Opening the dialog performs only a native status read.
Download remains disabled without acknowledgement, the signed support layer,
or while capture, settlement, scoring, or update blockers are active. The
score card supplies the unavailable-runtime call to action, while the desktop
release panel retains a persistent management entry after activation.

Twenty-one Rust tests, Rust Clippy with warnings denied, 17 frontend contract
tests, 109 React/browser tests, 29 focused Python packaging/score tests, frontend
typecheck, and a production web build pass on macOS. Four focused dialog tests
prove no implicit acquisition, the acknowledgement gate, missing-support
failure, bounded link selection, provenance/removal copy, and initial-status
errors.

The macOS arm64 reference support package is now constructed from standalone
CPython 3.11.14, 61 exact registry distributions, and the three commit-pinned
music21, ScoreTransformer, and MUSTER repositories. The universal registry
lock is exact and hash-required; the VCS inventory rejects any commit drift.
`pretty-midi` 0.2.11 has no wheel for this target, so the build host constructs
that exact hash-pinned source distribution. No compiler, package manager, Git,
or network dependency is left for the user's machine. The same registry lock
now builds on Windows x64 as described below.

The staged macOS support package contains 64 distributions, no symbolic links,
and 926,843,098 bytes. Its canonical payload is 926,842,450 bytes with SHA-256
`8f25d0131cfc7b76e8efde1c19f2b8f255823b263003c187bf46b69b560e5bce`.
The complete staged desktop runtime is 1,942,674,133 bytes. An unsigned Tauri
application assembled from that stage is 1,959,847,221 bytes; its updater
archive is 586,901,211 bytes. The package audit finds 34,074 files and no
forbidden model repository, checkpoint, accelerator package, development
package, cache, or internal-score runtime.

Real macOS app inspection found and corrected a manifest-ordering mismatch
between Python staging and Rust validation. After the fix, the packaged dialog
renders the exact education/research-only notice, recognizes the support
package, begins with acknowledgement unchecked and download disabled, and
enables download only after the checkbox is selected. The dialog was cancelled
without starting acquisition and the application quit without an orphan. The
real 390 MB model download, bounded import/model smoke, installed relaunch,
and signed/notarized package have not yet been exercised.

The Windows testbed subsequently built the same support contract with exact
x64 CPython 3.11.14 under Windows 11 ARM64 emulation. The output contains 64
distributions, 196 x64 PE files, 20,621 files total, and 920,228,180 bytes. Its
920,227,529-byte canonical payload hashes to
`4b9c41b350978164a97070bad4d894982b2d454b7ea1d628cabffef4c6461bd1`.
Both import groups and a complete independent repeat audit pass, no temporary
stage remains, and the output contains no main model source or checkpoint.
This validates only the support layer; acquired-model inference and notation
parity remain unproven on Windows.

## Later Todo — Remove Evaluation Helpers

After the proof-of-concept release, stop importing the upstream evaluation
metrics when Atpiano needs only `infer()`. Prove token, MusicXML, and alignment
parity, then remove ScoreTransformer, MUSTER/amtevaluation, and dependencies
reachable only through them from the support environment. Measure the download
and installed-size reduction and ask upstream maintainers for explicit license
terms if either helper remains necessary. This is not required for the first
public build.

## Concern And Takedown Response

This proof-of-concept is free and intended for education/research use, but that
does not itself grant third-party rights. If an upstream maintainer or credible
rights holder objects, preserve the request, stop new publication, unpublish
affected GitHub release assets when appropriate, deactivate the production
update product, and prepare a signed forward release that disables acquisition
and refuses the affected runtime. Update the public notice and provenance
record. Do not promise that removing a release remotely erases already
downloaded copies, and do not silently delete an installed user's files.

## Rollback

The acquisition controller and external runtime are additive. If acquisition
is technically unsafe or an explicit upstream objection arrives before
publication, keep the App score-free, hide the enable action, and continue the
ordinary capture/review experience. If a released application later must
disable the feature, a signed update may refuse to select the external runtime
while leaving it available for explicit user removal; it must not silently
delete user-acquired data or existing score artifacts.
