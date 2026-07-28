# R5 Desktop Boundary Review

Status: **revised and ready for human export review on 2026-07-28; Phase 6
remains closed.**

This is the Phase 5 walking skeleton: one unsigned macOS arm64 application
containing the shared React workspace, a thin Tauri 2 supervisor, a
self-contained CPython 3.10 runtime, CPU model assets, and relocated media
tools. It proves the application/process/security boundary and the real
golden replay. It is not a signed installer or the complete local desktop
product.

## Launch

The build is currently available at:

```text
app/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/Atpiano.app
```

From the repository root, the ordinary launch action is:

```text
open app/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/Atpiano.app
```

The terminal fallback, with Python development overrides explicitly removed,
is:

```text
env -u PYTHONHOME -u PYTHONPATH -u VIRTUAL_ENV \
  -u ATPIANO_BASIC_PITCH_MODEL \
  -u ATPIANO_TRANSKUN_CHECKPOINT \
  -u ATPIANO_TRANSKUN_CONFIG \
  app/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/Atpiano.app/Contents/MacOS/atpiano-desktop
```

The ignored review archive is:

```text
results/desktop-phase5/Atpiano-R5-macos-arm64-unsigned.zip
```

Its SHA-256 is:

```text
ef1fd002e4e82a015fb13f069147840789d3d55ebb5f79541c98f6407f8579f3
```

This build is intentionally unsigned and unnotarized. macOS may require an
explicit local-development override if the app is moved through a channel
that adds quarantine metadata.

## Internal Score Review Addendum

The score-unavailable review result opened Tactical 031. A separate,
internal-only application now exercises the existing score UI with the pinned
MIDI2ScoreTransformer CPU checkpoint:

```text
results/desktop-internal-score/Atpiano-Internal-Score.app
```

Build and launch it from the repository root with:

```text
scripts/build-atpiano-desktop build-internal-score
open results/desktop-internal-score/Atpiano-Internal-Score.app
```

This command intentionally creates no ZIP, DMG, installer, or updater
payload. The app is ignored, unsigned, arm64-only, and restricted to the
current private test. Its manifest records the paper and provisional
checkpoint assumption as CC BY 4.0, the upstream source license as
unconfirmed, and public distribution as false. The ordinary commands and R5
archive continue to exclude and reject the score runtime.

For this review, select or create a settled performance and choose **Render
committed score**. The score should render in the existing workspace and open
in the responsive reader. Capture, review, playback, and export should remain
available if score generation fails.

The user confirmed on 2026-07-28 that score engraving works in this desktop
build. That pass found that the nearby browser-style baseline download
produced no visible desktop file. Tactical 032 removes that duplicate action:
the bottom **Exports** panel now labels **Original model MusicXML** beside
audio, MIDI, event history, score alignment, and the selected score. Web
exports retain ordinary downloads; desktop exports open a native Save As
dialog and stream exact authenticated artifact bytes to the chosen file.

The revised ignored internal app is at the same path. Its current audit
reconciles 32,704 files and 2,361,515,181 installed bytes. The score runtime
and provisional license boundary are unchanged.

## Suggested Review

1. Launch the app. It should open the existing Atpiano performance workspace
   without account or hosted-login UI and show a green **Local engine**
   status.
2. Select the retained 42-second replay in **Recent performances**. Review
   synchronized audio, the piano roll, keyboard, commit horizon, and
   artifacts.
3. Choose **New session** to run the bundled fixture again. Progress should
   advance through preview and after-Stop correction and settle as a new
   completed local session.
4. Quit and reopen the app. Completed sessions should still appear.
5. In the internal score build, render a settled score and inspect its
   notation, synchronized score cursor, and source alignment.
6. Under **Exports**, save **Original model MusicXML** and one audio or MIDI
   artifact. Confirm each Save As dialog and saved file, and verify each
   SHA-256 starts with the prefix displayed by the panel; cancel one dialog
   and confirm no partial file appears.
7. Decide whether this feels like the accepted shared application and whether
   the process, bundle, and capability direction are sound.

The current local application-data workspace already contains two completed
sessions used to demonstrate history across restart. No repository workspace
is used by the desktop shell.

## Verified Behavior

The final pruned archive was extracted below `/tmp` and launched from there
under `env -i` with only `HOME`, `PATH=/usr/bin:/bin`, locale, and temporary
directory values. Process inspection showed:

```text
Atpiano.app/Contents/MacOS/atpiano-desktop
  -> Atpiano.app/Contents/Resources/desktop-runtime/bin/python3
     -I -B -m atpiano.desktop_sidecar
```

No system Python, repository import, `.venv`, `uv`, Homebrew executable path,
or hosted API was used. A post-launch scan and full audit found no bytecode
cache or bundle mutation.

The packaged 42-second fixture completed with:

- 2,016,000 source frames at 48 kHz;
- audio and commit horizons at exactly 2,016,000;
- provisional horizon at 1,968,000;
- pinned Basic Pitch and Transkun hashes and CPU execution;
- 151 final notes in this run;
- 13 retained files, one verified MP3, and zero WAV files;
- 4.719 seconds to cold sidecar readiness;
- 0.086 seconds reported model load, 18.901 seconds commit inference, and
  31.721 seconds total replay settlement; and
- 0.511 seconds for measured app close plus child exit/reap.

CPU inference scheduling causes established run-to-run variation in which
borderline true notes survive. The v2 parity gate therefore checks exact
source, horizons, model hashes, device, and artifacts; bounds event-count
deltas; applies a broad pairwise musical floor; and tightly compares both
paths against the same 198-note golden reference. The final direct-versus-
packaged comparison passed with:

- 1.53% commit-emission and 0.61% export-count deltas;
- 0.010 absolute golden onset-F1 delta;
- 0.012 absolute golden frame-F1 delta;
- 0.027 absolute golden note-plus-offset-F1 delta; and
- 1.99% final-note-count delta.

The ignored machine-readable evidence is:

```text
results/desktop-phase5/bundle-audit.json
results/desktop-phase5/r5-pruned-packaged-report.json
results/desktop-phase5/r5-final-direct-report.json
results/desktop-phase5/r5-pruned-replay-parity.json
```

The internal score build then passed a second real replay:

- 2,016,000-sample audio and commit horizons;
- 151 closed source notes;
- one retained MP3 and zero WAV files;
- 7.61 seconds for score generation;
- 12 measures, two parts, and 152 pitched MusicXML note elements; and
- a valid v2 alignment mapping 131 source notes.

This session-addressed MusicXML result has SHA-256
`21668c49f72563d21383cfbd42f3f0505934576ccbd18dc757b0c60e4731350f`.
The entire 2.36 GB application tree retained SHA-256
`20b8ac3377008c54cb63fc3ec34463c564f7b927563e7792c5e13c130361d792`
across replay and score generation. A real Tauri launch also passed the
post-launch bundle audit after library caches were redirected into mutable
app data.

Its ignored machine-readable evidence is:

```text
results/desktop-internal-score/stage-report.json
results/desktop-internal-score/bundle-audit.json
results/desktop-internal-score/packaged-score-report.json
```

## Failure And Recovery Evidence

An incompatible launch declaring `atpiano.desktop.v999` exited before ready
with status 2 and this bounded, credential-free record:

```json
{"error":"desktop protocol is incompatible","error_type":"ValueError","schema_version":"atpiano.desktop-error.v1"}
```

The automated form is:

```text
uv run pytest -q \
  tests/test_desktop.py::test_sidecar_rejects_incompatible_protocol_without_leaking_token
```

Terminating the live packaged sidecar replaced the application workspace with
the visible **Atpiano needs to restart** failure screen. Quitting and
relaunching started a fresh embedded sidecar and restored both completed
sessions. App close also closes the child's inherited stdin and reaps it;
Rust tests exercise the graceful and forced cleanup state.

## Privilege And Trust Map

The native shell owns only:

- 32 bytes of operating-system random launch secret;
- one child process and its inherited environment/stdin/stdout/stderr;
- the app-data workspace path and packaged resource paths;
- one size-bounded ready record and one authenticated handshake;
- one `desktop_runtime` bootstrap command;
- one bounded `desktop_export_artifact` Save As command; and
- one `desktop-runtime-failed` event.

The main local webview receives only `core:event:allow-listen` and
`core:event:allow-unlisten`. It has no Tauri shell, filesystem, dialog,
updater, tray, menu, image, or remote-origin plugin capability. The CSP loads
the application from bundled assets and permits connections only to Tauri IPC
and loopback HTTP/WebSocket endpoints.

The custom export command is not general filesystem or dialog access. The
webview supplies only one validated sidecar artifact-content path and a safe
suggested basename. Native code chooses no path itself: the operating-system
Save As dialog returns the user-selected destination. Rust then fetches from
the already validated loopback port with its native-held bearer value,
streams the declared length outside IPC, and atomically publishes only a
complete file. The command rejects remote URLs, other loopback endpoints,
path traversal, response-header overflow, transfer encoding, duplicate or
missing lengths, and truncated bodies.

The Python sidecar binds an ephemeral `127.0.0.1` port. HTTP and artifact
requests require the per-launch bearer value. WebSocket upgrades require one
exact token-derived subprotocol. Only `tauri://localhost` receives CORS
access. The token is passed in inherited environment, not arguments or URLs,
and is redacted from bounded failure details.

The React product components know only `AtpianoRuntime`. Tauri detection,
bootstrap, authenticated requests, WebSocket construction, native export, and
bounded artifact blob URLs remain inside desktop composition/runtime files.

## Bundle Inventory

The final audit reconciles 13,586 installed files and every one of
1,044,680,287 installed bytes. The ZIP is 345,419,478 bytes.

| Component | Installed bytes | ZIP payload bytes |
|---|---:|---:|
| Python packages | 900,387,579 | 250,865,752 |
| Python runtime and manifests | 38,811,893 | 16,127,284 |
| Media tools | 35,661,472 | 15,625,643 |
| Model pack | 56,680,490 | 50,816,523 |
| Golden fixture | 4,065,233 | 3,428,150 |
| Rust shell plus embedded frontend | 8,795,440 | 3,201,730 |
| App resources and metadata | 278,180 | 272,910 |
| ZIP container overhead | — | 5,081,486 |

Tauri embeds the production frontend in the Rust executable, so those two
installed contributions cannot be split without source-build estimates.

The largest distributions are Torch at 431.8 MB, llvmlite at 129.8 MB,
SciPy at 59.6 MB, NumPy at 40.1 MB, and scikit-learn at 31.3 MB. This is a
large but explained CPU bundle. The audit covers 384 Mach-O files and rejects
escaping dynamic-library references, unsupported architectures, CUDA,
NVIDIA, ROCm, the internal score runtime, dev distributions, removable test
namespaces, anonymous caches, and escaping symlinks.

PyTorch 2.13 imports `torch.testing` and
`torch.testing._internal.logging_tensor` through its ordinary import and
checkpoint chain. The audit therefore classifies the required 5.2 MB,
112-file namespace separately; all other dependency test namespaces are
removed and any survivor fails packaging.

## Code Map

- React composition and components:
  `app/src/main.tsx`, `app/src/app.tsx`, and `app/src/components/`
- Shared provider contract and local adapters:
  `app/src/runtime/atpiano-runtime.ts`,
  `app/src/runtime/local-runtime.ts`
- Desktop runtime adapter:
  `app/src/runtime/desktop-runtime.ts`
- Thin Rust supervisor and capability:
  `app/src-tauri/src/lib.rs`,
  `app/src-tauri/capabilities/default.json`
- Sidecar launch and handshake contracts:
  `src/atpiano/desktop_sidecar.py`, `src/atpiano/desktop.py`
- Framework-independent application core:
  `src/atpiano/application/`
- Local persistence, models, replay, score, and storage adapters:
  `src/atpiano/adapters/`
- Existing HTTP/WebSocket composition with optional desktop auth:
  `src/atpiano/corrected_workbench.py`
- Reproducible runtime/model/media staging and audit:
  `src/atpiano/desktop_packaging.py`,
  `scripts/build-atpiano-desktop`
- Direct/package replay validation:
  `src/atpiano/desktop_validation.py`

## Known Gaps And Deliberate Exclusions

- The app is unsigned, unnotarized, arm64-only, and targets macOS 13 or later.
- There is no DMG, installer, updater, rollback channel, or public release
  process.
- Microphone parity, capture-device permissions, settings, and daily-use
  offline validation belong to Phase 6.
- The current local filesystem catalog remains in use; the planned desktop
  SQLite catalog, repair, and model-pack acquisition UI belong to Phase 6.
- The ordinary build excludes MIDI2ScoreTransformer and its checkpoint
  because distribution rights remain unresolved. The separate internal app
  is provisionally available only for this private review.
- The bundled Homebrew FFmpeg build is GPL-3.0-or-later and its formula
  inventory is recorded. Public distribution requires a deliberate license-
  notice and source-compliance pass.
- Core ML warns that this exact Torch version is newer than its tested range.
  The real model import and replay pass; this warning remains visible evidence
  for future model-runtime selection.
- The CPU bundle is still approximately 1.04 GB installed. Model/runtime
  substitution, quantization, or checkpoint changes require a new parity
  result and are not packaging cleanup.
- Phase 5 does not claim network-disabled microphone use, Windows, Linux,
  Intel Mac, accounts, hosted APIs, collaboration, upload, or sync.

## Commit And Test Record

The Phase 5 implementation series begins at `fc7cad6`; Tactical 030 records
the original R5 series, Tactical 031 records the internal score revision, and
Tactical 032 records the artifact-export revision.

The final gate includes:

- 177 Python tests and Ruff;
- 5 Node contract tests and 49 Vitest tests;
- frontend typecheck and production build;
- 11 Rust lifecycle/security/export tests, formatting, and Clippy with warnings
  denied;
- self-contained staging/import/sidecar smoke;
- final bundle native, dependency, cache, component, and archive audit;
- extracted-archive `env -i` launch and post-launch immutability check; and
- direct-versus-packaged real golden replay parity; plus
- internal packaged replay-to-score, MusicXML/alignment validation, and
  whole-tree immutability; plus
- a rebuilt internal app audit and authenticated, length-checked, atomic
  artifact-streaming tests.

R5 is a human hold. Do not open the complete local-desktop Phase 6 until the
user explicitly accepts this boundary and bundle direction.
