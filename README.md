# atpiano

Atpiano is an experimental acoustic-piano transcription and performance-review
workspace. It listens to a nearby piano, turns the captured audio into
timestamped note events, and presents the performance through synchronized
audio, a piano roll, a keyboard, and optional engraved notation.

The v3 shared React workspace is the primary application. Model selection,
streaming behavior, correction, notation quality, and deployment remain active
research concerns, supported by reproducible benchmarks and retained evidence.

## Project Boundary

Atpiano owns:

- timestamped audio capture or ingestion from a local microphone or a remote
  phone;
- acoustic-piano transcription;
- reconciliation of overlapping or revised model output; and
- a normalized, timestamped note-event stream.

The v3 workspace consumes that stream through an explicit runtime boundary and
keeps the source audio sample clock authoritative. The same contracts are
intended to support future hosted and desktop runtimes without coupling the
musical views to one execution backend.

The reproducible foundation is a deterministic live-replay benchmark. It
replays aligned recordings at wall-clock cadence, exercises models as if audio
were arriving live, and reports both transcription quality and
capture-to-event latency. Local browser microphone capture uses the same
pipeline; phone capture remains future work.

## Project Status

The v3 `workbench-v3` application is the authoritative user-facing version.
The v1 and v2 applications were prototypes. Their standalone interfaces remain
runnable as compatibility surfaces, regression oracles, and implementation
evidence. New product work should target v3 unless a task explicitly concerns
an earlier prototype.

The project is still in discovery. Python, Spotify Basic Pitch, and Transkun
are research choices rather than permanent selections. A deterministic
MIDI-derived fixture, untouched offline reference, wall-clock replay
benchmark, and local browser live-transcription workspace are runnable on
Apple Silicon. The ordinary locked environment, automated regression lanes,
production frontend build, and Basic Pitch offline and rolling TFLite paths
are also validated on x86_64 Linux. Native PortAudio capture, the optional
Transkun-corrected lane, and a complete shared-workbench replay are validated
there as well. Chrome's fake-microphone path exposed slow correction blocking
capture and exceeding the old Stop timeout. Model work is now isolated from
durable PCM ingest, Stop promptly enters background settlement, and correction
defaults to a measured capability profile or conservative after-Stop mode.
The Linux rerun now confirms continuous ingest, responsive Basic Pitch under a
saturated isolated Transkun worker, sub-second Stop acknowledgement, reload
reattachment, and complete checksummed settlement. This host's measured
two-thread CPU profile selects after-Stop correction. A consentful human
browser-microphone review, a multi-hour real-model soak, and Linux latency
parity have not been validated. The internal score runtime installs, and score
alignment now reconciles generated score attacks to source events with an
explicit monotonic exact-pitch pass instead of assuming generated token
positions retain source identity. The corrected contract passes the retained
public two-minute session that exposed the defect.

Current direction and research questions live in [`docs/topics/`](docs/topics/README.md).
Acoustic-model benchmarking, live browser transcription, and downstream
performance-to-notation conversion have separate owners there.

## Authoritative Performance Workspace (v3)

Install the corrected-note Python dependencies and the pinned frontend
dependencies, then launch the primary local application:

```text
uv sync --extra corrected
npm ci --prefix app
uv run atpiano workbench-v3
```

The command builds and opens the v3 React application, using
`results/workbench-v3/` as its local workspace by default. Select **New
session**, start the microphone, and use **Stop & settle** when finished. The
workspace keeps active capture distinct from the selected historical session
and provides synchronized recorded-audio playback, provisional and corrected
notes, piano-roll and keyboard inspection, session history, artifacts, and
recoverable deletion.

Engraved score snapshots are optional and isolated from capture. To enable the
current internal score experiment, install its runtime once:

```text
uv run atpiano setup-midi2score
```

That integration has no confirmed upstream license and is for private internal
experimentation only. Capture, playback, the piano roll, keyboard, and exports
remain usable without it. See
[`docs/r3-interaction-review.md`](docs/r3-interaction-review.md) for the
accepted v3 interaction contract and deterministic replay command.

## Development Validation

From a fresh clone, install the locked Python and frontend dependencies and
run the complete unattended gate:

```text
uv sync --frozen
npm ci --prefix app
uv run atpiano migration-regression
npm run build --prefix app
```

The regression command writes a machine-readable report below the ignored
`results/migration-regression/` directory. It covers Python and JavaScript
tests, generated-contract drift, TypeScript, the frontend tests, dependency
audit, Ruff, JavaScript syntax, and Git whitespace. The separate production
build is included because it is a Phase 3 acceptance gate but is not currently
part of `migration-regression`.

## Temporary Public Trial

The Pi's live Caddy service proxies `https://atpiano.graehlarts.com` over the
LAN to this Mac. The public upstream is an on-demand macOS `launchd` service:

```text
scripts/share-atpiano-service start
scripts/share-atpiano-service status
scripts/share-atpiano-service logs
```

The service survives a terminal closing, restarts after an unexpected exit,
and retains lifecycle, stdout, and stderr logs under
`~/Library/Logs/atpiano/`. Stdout and stderr use five-file, 5 MiB circular
rotation by default. It is registered directly from this repository, not
installed as a login item, so a reboot leaves it stopped until the explicit
`start` command is run again. Use `restart`, `logs --follow`, or `stop` for
the corresponding lifecycle operations.

Both the service and the lower-level `scripts/share-atpiano` foreground
launcher are intentionally macOS-only and fail with an explicit explanation
on Linux. The foreground launcher remains useful for direct diagnosis.

The URL works only while this Mac and the service are running. The application
binds to this Mac's LAN address; its explicit `--public-origin` option trusts
only the configured HTTPS hostname for browser actions and microphone
WebSockets. Override `ATPIANO_BIND_ADDRESS`, `ATPIANO_PORT`,
`ATPIANO_PUBLIC_ORIGIN`, `ATPIANO_UV`, or `ATPIANO_SERVICE_LOG_DIR` when
registering the service to change its generated launch configuration.
`ATPIANO_SERVICE_LOG_SIZE` and `ATPIANO_SERVICE_LOG_COUNT` adjust rotation.

Machine-dependent microphone, real Transkun, internal score-runtime, and
long-soak lanes remain explicit rather than being counted as unattended
passes. Current Linux evidence and limits are tracked in
[`docs/topics/linux-development-portability.md`](docs/topics/linux-development-portability.md).

## Retained Prototype Workbenches

The following applications document the two prototype generations. They remain
available for compatibility and regression work, but they are not the primary
Atpiano interface and should not receive new product features by default.

### Browser Workbench v1

The v1 browser workbench was the first runnable MVP. Its command, session
artifacts, and review path remain intact. See
[`docs/tactical/009-three-phase-unbounded-sessions.md`](docs/tactical/009-three-phase-unbounded-sessions.md).

Use the pinned Python 3.10 environment:

```text
uv sync
```

Then start the one local server:

```text
uv run atpiano workbench
```

The command opens a browser page. Grant microphone access and press **Start
live recognition**. The page warms the local Basic Pitch model, then asks for
one second of quiet room sound to calibrate an automatic onset-energy gate.
After the status changes to **Listening**, accepted pitches light a
physically proportioned 88-key keyboard and appear from left to right as
onset-first notes on a grand staff. Nearby onsets form one group using a
configurable window that defaults to 80 ms. Source-onset gaps are visible by
default, with absolute source time and raw-onset modes available for closer
diagnosis.

The staff uses a deliberately rough 120 BPM rhythm preset by default. When the
next onset arrives, it revises the preceding mark to the nearest sixteenth,
eighth, quarter, half, or whole glyph. Other fixed-tempo presets and neutral
quarter marks are selectable. These glyphs represent inter-onset spacing, not
detected key duration, tempo inference, meter, or a finished score.

Press **Stop** to flush and hash the exact captured PCM, save the session WAV
and live event history, and automatically run the untouched full-file Basic
Pitch adapter. The completed audio, MIDI, normalized events, native live
windows, noise-gate decisions, timing evidence, final reconciliation, run
report, piano roll, and experimental score appear in the same page. No second
Transcribe action is needed.

The score view shows its tempo, beat, meter, key, quantization, and hand-split
assumptions. Change them and press **Regenerate local score** to retain and
review another interpretation. Score rendering uses a pinned
OpenSheetMusicDisplay bundle from a CDN, so it needs internet access; the
MusicXML artifact remains downloadable if that bundle is unavailable.

The same page supports a consentful two-phase comparison with Ivory:

1. download and submit the original WAV to test Ivory's complete
   audio-to-score pipeline;
2. download and submit the atpiano prediction MIDI in a separate Ivory job to
   test its notation conversion with note detection held constant; and
3. import each unedited MusicXML result into its labeled workbench lane.

The workbench does not upload audio automatically or handle Ivory accounts,
payments, or credentials. Imported oracle scores remain under the ignored
local run directory. Ivory's free preview was observed to block MusicXML
download, so importing its result currently requires a paid plan.

The first target-piano review found the local Partitura score technically
valid but unreadable, while the Ivory preview was easy for the user to sight
read. Treat notation as a diagnostic experiment, not a current product
capability. The v1 workbench therefore emphasizes live pitch onsets and broad
chord shape rather than score notation.

The workbench binds only to `127.0.0.1` and stores generated artifacts under
the ignored `results/workbench` directory by default. Browser takes are
limited to two minutes and the server accepts at most 64 MiB per upload. A
recording has no aligned MIDI, so its quality metrics are explicitly unscored;
the piano roll is for listening and subjective inspection.

The two-minute limit is a prototype resource bound, not a Basic Pitch or audio
API limit. The browser and live processor retain session PCM, and the benchmark
preserves every overlapping native model window before copying it into the
final run. The two latest two-minute evidence jobs each occupy about 274 MiB,
including roughly 117 MiB of live native windows. Raise or remove the limit
only after choosing a longer-session retention and compaction policy.

Live recognition uses sample-indexed PCM16 blocks over a same-origin loopback
WebSocket. The first local target-recording replay measured 0.43-second median
and 1.65-second p95 source-onset-to-server-emission latency. Those are
prototype measurements, not a promise for every note or a substitute for
browser microphone review. Browser clock exchanges and paint acknowledgements
are retained so an actual page session can also report delivery latency.
Notation remains a separate artifact consumer and does not change the
acoustic model output.

### Corrected-note Workbench v2

The v2 application was the corrected-note prototype and still provides the
local engine composed by v3. It keeps immediate Basic Pitch notes provisional,
replaces settled spans with the bounded trailing Transkun lane, shows sustain
and soft pedal, and stores indefinite sessions as segmented audio plus indexed
events. Use the v2 page itself only for compatibility, diagnosis, or regression
work.

Install the optional corrected-note dependencies, generate the musical
fixture, install the isolated internal score runtime once, and open v2 with
server-driven replay:

```text
uv sync --extra corrected
uv run atpiano musical-fixture \
  ../atpiano-artifacts/musical-loop-input
uv run atpiano setup-midi2score
uv run atpiano workbench-v2 \
  --replay ../atpiano-artifacts/musical-loop-input/input.json
```

`setup-midi2score` downloads the pinned upstream source, Python 3.11
dependencies, and 389,829,880-byte checkpoint into the ignored
`results/midi2score-runtime/` directory. This integration is for private
internal experimentation: the upstream repository has no confirmed license.
Skip that setup if only the roll and keyboard are needed.

The page starts the WAV without microphone permission and exercises the same
session, recognition, correction, review, and export paths used by capture.
Use `--repeat N` to loop it on one continuous source sample clock,
`--silence-seconds S` to declare and index a gap between repetitions, or
`--no-wait` for accelerated bring-up. Generated session data defaults to
`results/workbench-v2/`.

The Performance card independently toggles a committed score, piano roll, and
88-key detected-note keyboard. The roll includes an aligned pitch-key gutter
with octave labels. The keyboard follows the latest detected attack by
default; click the roll or move its source-time slider to inspect the exact
pitches sounding at an earlier moment. Amber keys are provisional and mint
keys are corrected.

Press **Render committed score** after corrected notes appear. The server
freezes the current commit horizon, excludes provisional and still-open
notes, and runs MIDI2ScoreTransformer as a bounded background job. The score
states the exact source time it covers and becomes stale, rather than silently
changing, as new notes commit. Refresh only when useful. The MusicXML and
snapshot MIDI remain downloadable if the pinned OSMD browser bundle cannot
load from its CDN.

Start the app without `--replay` to use its microphone Start/Stop controls:

```text
uv run atpiano workbench-v2
```

The corrected lane defaults to automatic capability selection. With no
matching local profile it conservatively waits until capture has stopped;
Basic Pitch remains provisional while playing. Measure the fixed musical
fixture on each host and execution configuration before requesting live or
delayed correction:

```text
uv run atpiano profile-backend \
  ../atpiano-artifacts/musical-loop-input/input.json \
  results/backend-profile \
  --commit-device cpu --commit-threads 2
```

This warms one isolated Transkun worker, runs two continuous-clock fixture
repetitions without wall-clock delivery waits, and retains its session,
per-decode evidence, host/model/scheduler identity, and recommendation. Pass
`--correction-mode` to explicitly override the profile when diagnosing a
mode; explicit live correction is not a throughput guarantee.

Only the visible 15–120 second timeline range is queried. After Stop, MIDI
contains the latest committed notes and pedal intervals, while Event history
contains every append-only revision in global sequence order.

## Benchmark Commands

The lower-level commands remain available for reproducible experiments.

Generate a deterministic MIDI-derived WAV and aligned reference:

```text
uv run atpiano fixture ../atpiano-artifacts/smoke-input
```

Generate the longer aligned musical loop used by v2 integration:

```text
uv run atpiano musical-fixture \
  ../atpiano-artifacts/musical-loop-input
```

Exercise the bounded v2 source and segmented-storage foundation without model
inference or microphone input:

```text
uv run atpiano replay-v2 \
  ../atpiano-artifacts/musical-loop-input/input.json \
  ../atpiano-artifacts/workbench-v2-source-check \
  --repeat 2 --no-wait
```

Add `--preview` to run the bounded Basic Pitch provisional lane through the
same v2 session:

```text
uv run atpiano replay-v2 \
  ../atpiano-artifacts/musical-loop-input/input.json \
  ../atpiano-artifacts/workbench-v2-preview-check \
  --no-wait --preview
```

Install the optional corrected-note lane and add `--commit` to replace settled
preview spans with trailing Transkun output:

```text
uv sync --extra corrected
uv run atpiano replay-v2 \
  ../atpiano-artifacts/musical-loop-input/input.json \
  ../atpiano-artifacts/workbench-v2-corrected-check \
  --no-wait --preview --commit
```

Run the untouched Basic Pitch file path:

```text
uv run atpiano offline \
  ../atpiano-artifacts/smoke-input/input.json \
  ../atpiano-artifacts/offline
```

Or replay the same samples at real wall-clock cadence:

```text
uv run atpiano replay \
  ../atpiano-artifacts/smoke-input/input.json \
  ../atpiano-artifacts/replay
```

Review a completed run in the local browser UI:

```text
uv run atpiano review ../atpiano-artifacts/replay
```

The native fixed-duration capture adapter is also retained for instrumentation
experiments:

```text
uv sync --extra capture
uv run atpiano record ../atpiano-artifacts/my-piano --seconds 30
```

The `sounddevice` adapter also needs the host PortAudio shared library. On
Debian or Ubuntu, install the `libportaudio2` package before running `devices`
or `record`.

Generated inputs, checkpoints, recordings, and run results do not belong in
Git. Each run records hashes, runtime/model versions, parameters, stage timing,
native outputs, normalized event revisions, scores, and a compact report.

## Project Map

- [`docs/topics/`](docs/topics/README.md) — focused, living decisions, evidence,
  gaps, and recommended direction
- [`docs/tactical/`](docs/tactical/README.md) — bounded implementation plans and
  execution records
- [`AGENTS.md`](AGENTS.md) — repository guidance for coding agents
- [`topics.md`](topics.md) — commit-series topic string log

## Working Principles

- Measure end-to-end latency from the audio sample clock to emitted note
  events; model inference time alone is not product latency.
- Preserve raw model output and timing evidence so post-processing can be
  compared without rerunning inference.
- Keep source timestamps separate from arrival and display timestamps.
- Treat recent acoustic events as revisable when a model needs future context.
- Compare against an offline/full-context quality ceiling before optimizing a
  streaming path.
- Keep model checkpoints, datasets, recordings, and generated benchmark
  artifacts outside Git.
