# 010 — Corrected-Note Workbench v2

Topic: live-acoustic-transcription

Status: complete on 2026-07-26. This tactical owns the first complete v2
milestone and remains its execution record. The physical microphone audition
and multi-hour real-model soak are explicit follow-up validation, not hidden
claims of this deterministic acceptance.

## Outcome

Build a separate local `atpiano workbench-v2` application that keeps immediate
Basic Pitch feedback, replaces settled spans with a trailing piano-specific
Transkun result, shows pedal, and can capture or replay indefinitely without
session-length growth in RAM or per-tick work.

The milestone is complete when one deterministic source can enter the v2
session engine, appear provisionally in the browser, become corrected and
committed through Lane B, persist in bounded storage, and export for review.
The existing `atpiano workbench` v1 application remains runnable and unchanged.

Readable engraving is not part of this milestone. The committed-note timeline
is useful even if no score-inference lane is available.

## Product Boundary

V2 owns:

- CLI command: `uv run atpiano workbench-v2`;
- default workspace: `results/workbench-v2`;
- frontend assets under a directory separate from `src/atpiano/web`;
- session schema: `atpiano.corrected-session.v1`;
- note-event schema: `atpiano.corrected-note-event.v1`;
- horizon schema: `atpiano.corrected-horizons.v1`; and
- artifact and export formats described below.

V1 keeps its command, frontend, two-minute bound, schemas, final Basic Pitch
pass, job layout, and review behavior. Shared low-level PCM framing, clock,
MIDI, and model utilities are allowed, but every shared-code commit must pass
the v1 test suite.

V2 is loopback-only and local-hosted like v1. Public deployment,
authentication, multi-user serving, and phone/LAN capture are excluded.

## User Experience

The new page has one horizontally seekable piano-roll timeline:

- the newest Basic Pitch onsets are visibly provisional;
- a moving `H_commit` line separates revisable and corrected material;
- Transkun corrections retain a Lane A identity when pitch and onset match;
- unmatched Lane A notes retract without remaining as stable false notes;
- unmatched Lane B notes appear as committed additions;
- committed notes show final pitch, onset, velocity, and a closed or still-open
  duration;
- sustain and soft-pedal intervals appear in their own band;
- only the visible time range is queried and drawn; and
- current horizon lag, source, model state, disk growth, and backpressure are
  visible without opening debug artifacts.

The page supports microphone Start/Stop and server-driven deterministic replay.
Replay is the first acceptance input. Microphone use is final confirmation, not
bring-up.

## Source Contract

Both source adapters deliver the existing versioned, contiguous PCM16 block
contract to one `CorrectedSession` engine:

```text
WAV replay ──┐
             ├─► sample-indexed PCM blocks ─► CorrectedSession
microphone ──┘
```

Replay supports:

- one pass or a declared repetition count;
- optional wall-clock cadence or accelerated validation;
- one continuous source sample clock across repetitions;
- recorded repetition and inserted-silence boundaries; and
- the same session, lane, persistence, horizon, delivery, and export code as
  microphone capture below the source adapter.

The server may start with a replay manifest and repetition count from the CLI
so the live page can be exercised without microphone permission.

## Aligned Musical Fixture

Add `deterministic-musical-loop-v1` without changing the frozen
`deterministic-midi-smoke-v2` fixture. Its exact composition and structural
assertions are owned by tactical 009:

- 16 bars in 4/4 at 96 BPM;
- `C - G/B - Am - F - Dm - G7 - C - C`, repeated with different texture;
- block chords and inversions in the first section;
- low-high-middle-high Alberti bass in the second;
- melody, repeated attacks, pedal changes, and useful register coverage; and
- deterministic MIDI/WAV generation with manifest bar, harmony, and section
  metadata.

The generated audio and MIDI remain outside Git. Code, structure, acquisition
recipe, expected hashes, and tests are tracked.

## Active-State And Persistence Contract

The in-memory working set is independent of session duration:

| State | Bound |
|---|---:|
| source PCM ring | 40 seconds |
| Lane A model/native window cache | most recent 32 windows |
| Lane A materialized identities | newer than `H_commit`, plus open matches |
| Lane B PCM input | one 28-second decode buffer |
| Lane B native output | one decode |
| browser event batch | one requested visible range |
| live delivery recovery | zero RAM backlog; bounded indexed cursor pages |

Persistent layout:

```text
<workspace>/<session-id>/
  session.json
  horizons.jsonl
  audio/000000.wav
  audio/000001.wav
  events/000000.jsonl
  events/000001.jsonl
  event-index.sqlite3
  diagnostics/lane-a/
  diagnostics/lane-b.jsonl
  exports/session.mid
  exports/session.jsonl
```

PCM and event logs are segmented by 60 seconds of source time. SQLite is a
rebuildable range-query index, not the sole evidence store. Review and browser
range queries must open only the relevant segments or indexed rows.

The server never deletes a session automatically. Before accepting audio it
checks available disk space, records disk growth, warns through session state,
and fails explicitly before storage is exhausted. The minimum-free-space
threshold is configurable. Stop closes the current segments and flushes Lane B
without rereading the whole session.

## Lane A Contract

Start from the measured v1 algorithm without changing v1:

- Basic Pitch 0.4.0;
- 1.988-second native window;
- 250 ms hop;
- strict onset-head decoder at 0.6;
- room-calibrated onset-energy gate;
- the existing edge guards; and
- stable provisional identities with explicit revisions and retractions.

Lane A output remains provisional in the v2 product even after its own
short-horizon reconciliation. Its native arrays use a fixed diagnostic window;
older arrays are deleted after their manifest rows record the retention
decision.

`H_prov` is the greatest reliable source sample Lane A has decoded. It is
monotonic and normally remains about one second behind the source head.

## Lane B Contract

Transkun 2.0.1 is an optional v2 dependency, pinned separately so ordinary v1
installation does not acquire PyTorch or its 54 MiB checkpoint. Its code is
MIT-licensed; the checkpoint remains in the external package cache and its
hash is recorded in every session.

Starting parameters:

- maximum trailing audio: 28 seconds;
- scheduler hop: 4 seconds;
- right guard: 4 seconds until the 2-second alternative passes parity;
- minimum real context before the first ordinary decode: 16 seconds; and
- CPU as the known-good reference provider.

The adapter invokes Transkun's own `transcribe` path, which uses
`forcedStartPos`, `onsetBound`, and `mergeIncompleteEvent` inside its
overlapping 16-second segmentation. V2 then reconciles overlapping outer
decodes by committing only the newly settled onset band.

`H_commit` is the end of that band and never regresses. For each band:

1. match Lane B notes to active Lane A identities by pitch and onset distance;
2. revise and commit matched identities;
3. retract unmatched Lane A identities whose onsets are inside the band;
4. create committed identities for unmatched Lane B notes; and
5. append every decision before pruning its in-memory identity.

Pitch and onset are immutable after `H_commit`. A note crossing the commit
boundary is emitted with an open offset and closed by a later decode; its tail
may change while the offset remains newer than `H_commit`. A boundary note
must never be duplicated merely because two outer decodes observe it.

Negative Transkun event pitches `-64` and `-67` become sustain and soft-pedal
interval events. They are not coerced into piano notes.

On Stop, Lane B decodes only the bounded tail with deterministic right padding,
closes any remaining open events explicitly, and advances `H_commit` to the
source head. It never runs a growing full-session pass.

If Lane B falls behind:

1. report lag without hiding provisional material;
2. increase the scheduler hop up to a recorded maximum;
3. reduce the trailing buffer only under an explicit recorded degraded mode;
4. retain PCM and normalized provisional history on disk; and
5. never grow the in-memory Lane A history or drop accepted source audio.

## Event And Query Contract

Every event has:

- global append sequence;
- session and stable event identity;
- revision;
- lane (`preview` or `commit`);
- lifecycle (`provisional`, `committed`, or `retracted`);
- pitch or pedal controller;
- onset sample;
- nullable offset sample and offset state (`open` or `closed`);
- velocity and native confidence where available;
- source and emission timestamps; and
- the commit band and model decode that produced it.

Browser queries use source-sample ranges plus an optional event-sequence
cursor. The server returns the latest materialized revision for visible
identities and any new lifecycle records needed for animation. Query cost is
proportional to the visible span, not session age.

The MIDI export contains only latest committed notes and pedal intervals. The
JSONL export preserves the full append-only revision history. Neither export
loads PCM into memory.

## Commit Sequence

Each numbered step should land as a coherent commit and update this tactical
with tests and evidence:

1. **Plan and boundary.** Add tactical 010 and link it from living docs.
2. **Musical fixture.** Generate the aligned MIDI/WAV pair and structural
   tests without changing the frozen smoke fixture.
3. **Session foundation.** Add v2 schemas, PCM ring, segmented audio/event
   storage, indexed queries, horizons, and deterministic replay.
4. **Bounded preview.** Add Lane A behind `CorrectedSession`, fixed native
   retention, provisional event persistence, and accelerated long-loop tests.
5. **Trailing commit.** Add the optional Transkun adapter, band reconciliation,
   pedal, open-tail handling, tail flush, parity tests, and lag evidence.
6. **Separate web app.** Add the v2 server, microphone adapter, replay controls,
   virtualized canvas timeline, horizon status, and range-query tests.
7. **Review and export.** Add seek/reload recovery, MIDI/JSONL export, storage
   warnings, and stopped-session review.
8. **Validation record.** Run v1 regression, aligned single/loop replay,
   golden-reference parity, bounded-state longevity, and local-page smoke
   tests; record actual evidence and remaining gaps here.

## Acceptance Gates

### V1 preservation

- the complete existing test suite passes;
- `atpiano workbench` still serves its v1 configuration and assets; and
- a retained v1 session still loads through the existing review path.

### Deterministic correctness

- both generated fixtures reproduce byte-identical MIDI and WAV hashes;
- the musical fixture's progression, chord, Alberti, pedal, and timing
  assertions pass;
- one-pass and repeated playback preserve source-sample continuity; and
- ordinary repetitions have the same aligned scoring distribution within a
  declared tolerance, with loop boundaries reported separately.

### Bounded operation

- a test representing at least eight accelerated hours keeps PCM, active
  identities, native windows, retry delivery, and query results within their
  declared bounds;
- 30-minute and longer representative runs record steady-state RSS, CPU, disk
  growth, horizon lag, and queue high-water marks; and
- review and export do not read the full PCM session into memory.

### Correction quality

- Lane B's finite full-file result is recorded as the control;
- repeated commit bands meet a declared onset/pitch parity threshold against
  that control;
- boundary duplicates, dropped notes, false retractions, and open-tail closure
  are counted;
- pedal intervals survive band boundaries; and
- Lane B replaces the v2 Stop-time final pass only after those gates pass.

### User-facing behavior

- provisional notes are visually distinct from committed notes;
- corrections do not relight an already visible matched note;
- retractions disappear from the materialized timeline;
- the visible timeline can seek an hour-old range without loading the
  intervening session;
- horizon lag and degraded mode are visible; and
- microphone capture uses the same engine after deterministic replay passes.

## Excluded

- engraving, beat inference, meter inference, MusicXML, or Lane C;
- browser-only inference or public hosting;
- authentication, multi-user scheduling, or remote audio;
- model training or fine-tuning;
- automatic deletion or cloud backup; and
- claims of acoustic precision from the unaligned golden-reference WAV.

## Execution Record

### Aligned musical fixture

Implemented `deterministic-musical-loop-v1` on 2026-07-26 without changing the
frozen smoke fixture:

```text
duration: 42.0 s (1.0 s lead, 40.0 s music, 1.0 s tail)
format: mono PCM16 WAV, 48,000 Hz
notes: 198
control intervals: 17 (16 sustain, 1 soft pedal)
MIDI SHA-256:
d24635a3f75d83dd8ff40e9513475dc43064e1dbb29fd836345f2057da0ec7d9
WAV SHA-256:
0eab5d787cb482735dc840daaed2abfb6d00ad6ff7a7058fdd217522905aaa89
```

The generated files are under the ignored
`results/musical-loop-validation/` directory. Focused fixture tests pass
byte-deterministic regeneration plus the declared form, block-chord density,
Alberti order, repeated attacks, register coverage, tempo, meter, sustain,
soft pedal, and WAV format assertions.

### Session and replay foundation

Implemented the model-independent `CorrectedSession` spine on 2026-07-26:

- `atpiano.corrected-session.v1` and monotonic horizon documents;
- a 40-second absolute-sample PCM ring;
- independently readable 60-second PCM16 WAV segments with hashes;
- segmented append-only corrected-event JSONL;
- a rebuildable SQLite range and event-sequence index;
- explicit disk-reserve failure rather than silent audio loss;
- source-boundary evidence; and
- `atpiano replay-v2` with wall-clock or accelerated continuous-clock
  repetition.

An accelerated two-repeat run of the musical fixture produced one contiguous
4,032,000-frame, 84-second source timeline. Its two boundaries were exactly
`[0, 2016000)` and `[2016000, 4032000)`. The audio log closed as a 60-second
segment plus a 24-second tail segment whose frame counts sum to the source
total. Focused tests cover ring eviction and range reads, event revision
materialization, retraction, audio segmentation, horizon monotonicity, replay
continuity, and bounded retention.

No acoustic model is connected in this foundation commit. `replay-v2` at this
point validates source and persistence behavior only; the next execution step
adds bounded Lane A.

### Bounded provisional Lane A

Implemented Lane A on 2026-07-26 with the measured v1 Basic Pitch model,
strict-onset decoder, edge guards, hop, and energy gate while leaving v1 code
paths behaviorally intact. V2 translates Lane A's internally settled notes to
product-level provisional events until Lane B corrects them.

The v2 implementation:

- prepares each model window from the absolute-sample 40-second ring;
- resamples the 48 kHz source to Basic Pitch's native 22.05 kHz boundary;
- preserves stable identities and append-only revisions;
- advances a monotonic `H_prov`;
- retains exactly the most recent 32 native model windows and records every
  eviction; and
- prunes in-memory identities older than `H_commit` or the fixed fallback
  retention window after their event history is durable.

Actual accelerated replay of the 42-second musical fixture produced:

```text
model windows: 161
native windows retained / evicted: 32 / 129
event emissions: 703
distinct preview identities: 196
latest non-retracted identities: 181
H_prov lag at Stop: 1.101 s
onset F1 at 50 ms: 0.860 (163 matches)
onset F1 at 25 ms: 0.850 (161 matches)
note-with-offset F1: 0.274
```

The weak offsets are expected from the onset-first lane and are one reason
Lane B owns settled durations. The ignored run is
`results/workbench-v2-preview/`.

A separate accelerated eight-hour source-clock test uses a low-rate fake model
to test state shape rather than model throughput. Across 480 scheduled windows
it holds the PCM ring to 40 source seconds, native evidence to three configured
windows, and active identities to one configured working-set identity. Actual
RSS, CPU, 48 kHz disk growth, and model-duty evidence still require the later
representative longevity run.

### Trailing commit Lane B

Implemented the optional Transkun 2.0.1 CPU lane on 2026-07-26. Ordinary v1
installation remains free of PyTorch; `uv sync --extra corrected` installs the
pinned v2 dependency. The adapter reads PCM directly, resamples at the model
boundary, invokes Transkun's native overlapping `transcribe` path, and records:

```text
checkpoint SHA-256:
50a80010effc2a59ffcd068a95cd2b29bd7f23a27a3515bc3ccd209c89a3d44c
configuration SHA-256:
d3d989214eb148230ee5df476d994dcde6af595904d3f968f1221d2e3bea5ac6
Transkun: 2.0.1
Torch: 2.13.0
device: CPU
```

The session centrally serializes revision numbers because Lane A and Lane B
can propose a revision for the same stable identity concurrently. Each row
also retains the lane's proposed revision. A focused failure test first
reproduced the uniqueness collision; the indexed store now assigns one global
monotonic revision before appending evidence.

The musical fixture used seven ordinary trailing decodes plus one bounded Stop
tail flush:

```text
buffer / hop / right guard: 28 s / 4 s / 4 s
decode count: 8
inference total / mean / max: 22.455 s / 2.807 s / 3.105 s
compute duty over 42 s of source: 0.535
matched preview identities: 132
preview retractions: 56
commit-only additions: 32
open tails later closed: 26
pending-tail high water / final: 5 / 0
latest committed notes: 147
latest committed pedal intervals: 12
final H_commit lag: 0 s after bounded tail flush
```

An independent full-file Transkun decode over the same finite fixture produced
148 notes and 11 pedal intervals. Treating that result as the stitching
control, not acoustic truth:

```text
rolling/control onset F1 at 50 ms: 0.936
rolling/control onset F1 at 25 ms: 0.936
rolling/control note-with-offset F1: 0.827
matched pedal onsets: 10 / 11
matched pedal offsets within 200 ms: 9 / 10
```

Against the generated reference MIDI, the rolling commit has perfect onset
precision and 0.742 recall, for 0.852 F1 at both 25 and 50 ms. The full-file
control is 0.855 F1. The renderer is synthetic, so this comparison tests
aligned behavior rather than target-piano quality.

The ignored rolling evidence is `results/workbench-v2-corrected-2/`. The first
attempt correctly failed on the cross-lane revision collision and remains
ignored diagnostic evidence. Fake-lane tests separately require stable
identity reuse, unmatched-preview retraction, commit-only addition, sustain
pedal, open-tail closure, final flush, and monotonic commit bands.

One limitation is explicit: the full-file control's predicted soft-pedal
interval lasts almost the entire take, longer than Lane B's 28-second outer
context. The rolling lane closes it when left context expires. This is a
bounded-context disagreement, not hidden parity.

### Separate workbench, indexed review, and export

Implemented the separate `atpiano workbench-v2` product surface on
2026-07-26. It uses its own `src/atpiano/web_v2/` assets, port default,
configuration schema, streaming schema, session workspace, HTTP handler, and
CLI parser branch. The existing `atpiano workbench` command and v1 assets
remain independent.

Both server-driven WAV replay and browser AudioWorklet PCM enter
`CorrectedSession`, attach the same Lane A and Lane B implementations, and
finish through the same bounded tail flush and export writer. A configured
`--replay INPUT_JSON --repeat N` begins without browser microphone permission;
`--no-wait` accelerates the same source-sample schedule. The microphone
adapter never retains a growing browser-side copy of captured PCM.

The browser implements a fixed-size canvas piano roll with 15, 30, 60, or
120-second indexed viewports. It distinguishes provisional and corrected
notes, replaces revisions by stable identity without relighting them, removes
retractions from the materialized view, draws sustain and soft-pedal bands,
marks `H_commit`, follows the source head, and can seek an old range. It also
shows both horizon lags, lane decode state, source duration, received blocks,
PCM disk growth, free-space warnings, and export readiness.

The first manual replay exposed a display-only failure: inference and storage
completed with 152 committed notes, but the piano roll remained at its initial
empty drawing. The first empty viewport response had been cached by a key that
advanced only with its history cursor; server-driven replay did not send the
microphone acknowledgement that invalidated that key. The key now includes
the audio head and session status, so source progress and final settlement
both refresh the viewport even when the prior response was empty. The live
viewport requests materialized rows without also scanning append history,
ignores stale responses after a session change, reports its visible note/pedal
count, and displays range-load errors next to the canvas. Its empty overlay
has an explicit `[hidden]` rule so author CSS cannot override the HTML hidden
state. Append-history paging remains available through the same API for
recovery and export.

The event index now maintains one current materialized row per identity in
addition to append-only evidence. This avoids grouping the full revision
history for every browser poll and prevents an older revision from
resurfacing when a corrected onset crosses a viewport edge. Range selection
also includes a note or pedal that begins before the viewport and overlaps it.
Sequence recovery pages are capped at 4,096 rows and visible ranges at 120
seconds, so no session-age-sized delivery retry queue lives in RAM.

Stop streams every event-index row in global sequence order to
`exports/session.jsonl`, then streams latest committed identities into
`exports/session.mid`. MIDI includes note durations plus controllers 64 and
67. Neither export opens session audio. A restart can serve the latest stopped
session, and it upgrades an older v2 event index with the materialized table
once at load.

Focused product validation currently covers:

```text
loopback Host and Origin enforcement
distinct v1 and v2 CLI branches and static assets
microphone WebSocket PCM continuity, Stop, and exports
accelerated two-repeat server-driven WAV replay
bounded range and sequence queries
materialized-only live viewport queries that skip append history
latest-revision viewport crossing and interval overlap
JSONL history order and committed MIDI note/pedal selection
frontend DOM contract and pure timeline materialization/geometry
```

The Sites building workflow was used only to enforce the local application
boundary and validation discipline. This repository has no
`.openai/hosting.json`, and v2 is intentionally loopback-only, so there is no
hosted deployment.

### Final validation and closure

The completed acceptance pass used the actual loopback server and page-facing
replay route, not only lower-level lane calls. It regenerated both fixtures
byte-identically:

```text
frozen smoke WAV:
39217861396c1bb84ddd883a9f10c63f1be8b8c34462676d87b626916452b043
frozen smoke MIDI:
84326c3ce5131b4a475a9bd3205fc289a995182e82cbf51b716e5958d540cf12
musical WAV:
0eab5d787cb482735dc840daaed2abfb6d00ad6ff7a7058fdd217522905aaa89
musical MIDI:
d24635a3f75d83dd8ff40e9513475dc43064e1dbb29fd836345f2057da0ec7d9
```

A one-pass 42-second musical-fixture product run under
`results/workbench-v2-product-validation/` produced 161 preview windows,
retained 32 after 129 evictions, used eight commit decodes, closed all pending
tails, and advanced `H_commit` to all 2,016,000 source frames. Commit inference
used 22.037 seconds. The export contains 946 append-history rows, 152 latest
committed notes, and 12 pedal intervals. Its 622,873-byte JSONL has unique,
strictly increasing sequences 1 through 946; MIDI contains 152 note-on/off
pairs and 24 controller messages.

Against a fresh 148-note finite Transkun control, that page-facing result
scored:

```text
onset F1 at 25 ms: 0.953
onset F1 at 50 ms: 0.953
note-with-offset F1: 0.840
```

Against the aligned generated MIDI it had 1.0 onset precision, 0.768 recall,
and 0.869 F1 at 25 and 50 ms. The offset comparison to the synthetic MIDI is
only 0.183 F1; Transkun's learned acoustic durations do not reproduce the
renderer envelope, so the finite Transkun control remains the stitching
parity oracle for offsets.

This 152-note result differs from the earlier 147-note execution recorded
above even though each remained close to the same 148-note finite control.
Inputs and fixture files are byte deterministic; neural rolling output is
accepted by declared pitch/onset distributions and control parity, not by a
frozen output hash.

A separate two-repeat product run under
`results/workbench-v2-musical-loop-validation/` used one continuous
4,032,000-sample clock and exact boundaries `[0, 2016000)` and
`[2016000, 4032000)`. The repetitions contained 155 and 156 committed notes.
Their aligned-reference onset F1 values were 0.878 and 0.870, a 0.009
difference within the declared 0.02 distribution tolerance. Direct
repeat-to-repeat onset F1 was 0.939 and note-with-offset F1 was 0.682. The
loop boundary therefore remains a reported context effect, not an assertion
of byte-identical model output.

The user's checksummed 34.688-second target-piano take then ran twice through
the same server under `results/workbench-v2-golden-validation/`. Its
continuous boundaries were exactly `[0, 1665024)` and
`[1665024, 3330048)`. Each repetition materialized 79 committed notes. After
shifting the second source boundary back to zero, all 79 pitch/onset pairs
matched at 50 ms for 1.0 F1; note-with-offset F1 was 0.861. With four seconds
excluded at each artificial edge, all 69 interior onsets still matched and
offset F1 was 0.870. This proves deterministic operational repeatability for
the retained unaligned take, not note accuracy.

The target-piano loop used 271 preview windows and 15 commit decodes totaling
42.524 seconds of CPU model inference over 69.376 seconds of source. It kept
exactly 32 native preview windows, reached seven pending tails, closed all of
them at Stop, and flushed `H_commit` to 3,330,048. The export contains 158
notes, 30 pedal intervals, and 853 history rows.

Stopped-session recovery was exercised in a fresh server process. It reopened
the same manifest and horizons, queried a late 12-second range without reading
earlier PCM, continued a bounded sequence page from cursor 900, and served the
same MIDI and JSONL artifacts.

The two-lane longevity gate represents 30 accelerated source minutes with
fake constant-cost model adapters so it can assert state shape independently
of neural throughput:

```text
source blocks / preview windows / commit decodes: 360 / 1800 / 447
PCM ring: 40.0 source seconds
native windows retained / evicted: 4 / 1796
active preview identities / high water: 12 / 15
pending commit tails / high water: 0 / 1
final provisional / commit lag: 1.0 s / 0.0 s
indexed old-range rows at source seconds 60–75: 5
history recovery page: 128 rows of a 4096-row maximum
in-memory delivery retry rows: 0
RSS before / high water: 105,250,816 / 108,724,224 bytes
CPU / wall time: 0.855 / 0.869 s
tracked session disk: 11,133,846 bytes
```

That low-rate run verifies bounds, not real model performance. At the product
48 kHz source boundary PCM grows linearly by exactly 96,000 bytes per source
second, or 172.8 MB per 30 minutes, before WAV headers. The real 42-second run
confirmed 4,032,000 PCM bytes and a 1.1 MiB event index. The existing separate
eight-hour preview-clock test still holds its ring at 40 seconds, native
evidence at three windows, and active identity set at one.

Lane B now measures full decode wall time in addition to native inference. If
one decode exceeds the four-second source hop, it records degraded mode and
increases the hop once, up to a bounded eight seconds. A focused slow-adapter
test forces and verifies that transition. The browser reports the degraded
hop and its current/high-water WebSocket backlog. Accelerated replay records
source-to-emission latency as unavailable rather than publishing a false
negative latency.

Final regression evidence:

```text
uv run ruff check .                         pass
uv run pytest -q                            47 passed
all tests/js/*.js                           pass
v1 workbench configuration/assets          pass
v1 live WebSocket and stopped review        pass
v2 loopback Host/Origin and PCM continuity  pass
```

No ambient microphone was activated during automated acceptance. The protocol
test sends exact signed PCM16 blocks through the microphone WebSocket and
verifies Stop and exports; the next useful human check is a consentful piano
take in the actual browser. A multi-hour real Transkun soak, pause/reconnect
support, and the previously recorded over-28-second soft-pedal disagreement
remain follow-up evidence. They do not change the completed v2 milestone's
bounded contracts or reintroduce v1 replacement.
