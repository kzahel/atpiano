# R4 Python Core And Storage Review

Status: ready for human review on 2026-07-27. Phase 5 remains blocked until
the user explicitly accepts both application parity and the compact-retention
default.

## What Changed

This is primarily an architectural refactor, not a new transcription
algorithm or React redesign. The former HTTP-server composition delegated
catalog, history, capture ownership, Stop settlement, score jobs, artifact
access, recoverable deletion, and storage lifecycle to framework-independent
Python services. Microphone and deterministic replay now enter the same
sample-indexed capture service. Filesystem, model, replay, score-process, and
FFmpeg details live behind local adapters.

The storage slice is intentionally observable but still opt-in. New sessions
started with `--compact-recordings` publish and completely decode-check a
128 kbps MP3, record its checksum and source-sample mapping, and only then
retire their WAV segments. Any encoder, decode, probe, publication, or
model-read-cursor failure preserves usable WAV. Existing sessions are read
without migration. The ordinary shared service still keeps WAV plus MP3.

## One Launch Command

From the repository root, launch an isolated compact review workspace:

```bash
uv run atpiano workbench-v3 \
  --workspace results/r4-python-core-review \
  --port 8014 \
  --replay results/musical-loop-validation/input.json \
  --repeat 2 \
  --no-wait \
  --correction-mode after-stop \
  --compact-recordings
```

The browser opens at `http://127.0.0.1:8014/`. The deterministic source is
84 seconds over two continuous-clock repetitions. Stop the server with
Control-C after review. Reusing the command adds another explicitly marked
Phase 4 session; it does not rewrite the prior one.

## Ten-Minute Parity Check

1. Let the replay settle. Select its history entry and confirm that Stop,
   settling, the final timeline, corrected keyboard state, and artifacts are
   coherent.
2. Play and scrub near the start, the 42-second repeat boundary, and the end.
   The audio playhead, roll, and detected keyboard should move together.
3. Request a score. Confirm that its status is tied to the selected session
   and that either MusicXML renders or the existing explicit empty/failure
   explanation appears.
4. Click New, permit the microphone, play for several seconds, and Stop.
   While it settles, select the replay session and confirm that selection does
   not retarget the active capture or its score/artifact work.
5. Inspect MIDI, revision JSONL, recording, and score artifacts as applicable.
6. Create or select a disposable session and exercise recoverable deletion.
7. In the existing shared workspace, open historical session
   `20260726T182929-52b73ce06223`. Confirm that its segmented WAV source still
   plays and that opening it did not create an `application.json` marker or
   remove its WAV.
8. To see failure preservation without sabotaging local FFmpeg, run:

   ```bash
   uv run pytest tests/test_application_storage.py \
     -k 'encoder_failure or decode_verification_failure' -vv
   ```

   Both cases must finish with raw WAV retained and compaction explicitly
   incomplete.

## Behavior Comparison

| Behavior | Frozen/Phase 3 expectation | Phase 4 result |
| --- | --- | --- |
| New, history, selection | Explicit selected and active IDs | Same contract; service-owned targets |
| Microphone and replay | Sample-indexed PCM, common session engine | Common application capture boundary |
| Stop | Prompt settling, reattachable completion | Same behavior; service-owned settlement |
| Timeline and keyboard | Source-clock synchronized | Runtime contract unchanged |
| Score | Frozen session and commit horizon | Service-owned frozen target |
| Artifacts | Session-addressed and range-readable | Centralized classification and access |
| Delete | Recoverable, guarded for active work | Service-owned guard and trash operation |
| Historical formats | Read without migration | Unmarked session trees are untouched |
| Ordinary recording | Retained WAV plus playback MP3 | Still the default in the shared service |
| Compact review mode | Not previously available | Verified MP3, then raw retirement |

There is no intentional wire-contract or React interaction change. The
Python suite, shared-runtime tests, contract drift check, typecheck, and
production build all pass. R4 is still important because tests cannot decide
whether the experience feels intact or whether lossy MP3-only retention is
the right local default.

## Storage Evidence

| Run | Source | Retained recording | Measured recording rate | Raw retired | Debug/temp after Stop |
| --- | ---: | ---: | ---: | ---: | ---: |
| One hour | 3,612 s | 57,792,812 B | 57,600,809 B/hour | 346,754,684 B | 0 B |
| Three hours | 10,836 s | 173,376,812 B | 57,600,270 B/hour | 1,040,263,964 B | 0 B |

Both runs decoded and compared a 200 ms source range after every repeat
boundary. All 86 one-hour probes and all 258 three-hour probes, including
first and last, correlated `0.904307` with the exact input range. Category
totals reconciled all workspace bytes and open files peaked at 12.

Machine-readable evidence remains untracked at:

- `results/phase4-storage-one-hour-20260727-evidence.json`
- `results/phase4-storage-three-hour-20260727-evidence.json`
- `results/backend-profile-phase4-soak-20260727/backend-profile.json`

The real Transkun soak covered 7,560 source seconds on the M4 Pro. It
completed all 362,880,000 accepted frames, 950 commit decodes, and 32,062
event revisions with zero final commit lag, bounded pending state, SQLite
integrity, and no anonymous temporary files.

## Code Map

```text
app/src/components + app/src/state
                 |
app/src/runtime/atpiano-runtime.ts
                 |
app/src/runtime/local-runtime.ts + HTTP/WebSocket adapter
                 |
src/atpiano/corrected_workbench.py
                 |
src/atpiano/application/
  sessions.py  capture.py  scores.py  storage.py  ports.py
                 |
src/atpiano/adapters/
  local_sessions.py  local_models.py  local_replay.py
  local_scores.py    local_storage.py
                 |
filesystem / SQLite / model workers / score process / FFmpeg
```

The dependency test rejects HTTP, browser, FastAPI, Tauri, or concrete local
adapter imports from `atpiano.application`.

## Exact Validation And Commit Series

- Phase 1: `3aabcda^..0bca270`
- Phase 2: `e2c2b9d^..9f8dd16`
- Phase 3: `a9805fd^..6d35751`
- Phase 4 application extraction: `1ca6032^..fd4f224`
- Slow-host prerequisite details:
  [`022-durable-capture-worker-isolation.md`](tactical/022-durable-capture-worker-isolation.md)
  and
  [`023-backend-capability-degradation.md`](tactical/023-backend-capability-degradation.md)

Final automated results:

- `uv run pytest -q`: 148 passed; one existing third-party deprecation
  warning.
- `npm test --prefix app`: five Node tests plus 46 Vitest tests in 11 files.
- `npm run typecheck --prefix app`: passed.
- `uv run atpiano generate-contracts --check`: passed.
- `npm run build --prefix app`: passed with the existing large-OSMD-chunk
  advisory.
- `uv run atpiano migration-regression --output
  results/migration-regression/phase4-r4-20260727/report.json`: passed.

## Known Differences And Decisions

- Compact retirement is opt-in pending R4; the active shared service keeps
  its safer WAV-plus-MP3 default.
- MP3 is lossy and is not declared the permanent archival or
  retranscription format. Accepting it means new compact sessions no longer
  have lossless WAV after verified settlement.
- Debug retention has a tested service and CLI policy but no new React
  storage-management screen.
- Interrupted arbitrary transcription is preserved and marked failed; it is
  not automatically resumed.
- The same-duration real-model soak ran on macOS. The decisive shorter Linux
  browser/profile checks pass, but a same-duration Linux soak remains a
  host-specific evidence gap.
- A consentful physical microphone action remains human-only.

## Approval

Please answer both:

1. Does the basic application behavior and extracted code direction pass R4?
2. Should verified MP3-only retention become the default for newly created
   local sessions, or should WAV plus MP3 remain the default?

No Phase 5 tactical or Tauri work begins before both decisions are explicit.
