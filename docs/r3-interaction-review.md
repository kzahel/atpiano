# R3 Interaction And Frontend Review

Status: mandatory human review ready on 2026-07-26. Phase 3 implementation is
complete; Phase 4 must not begin until this review is explicitly accepted or
revised.

This packet reviews the shared React application while its visual hierarchy,
controls, and session mental model are still inexpensive to change. The
Python application-service extraction is deliberately not part of this
review.

## Launch The Review

From the repository root, install the corrected inference extra once:

```text
uv sync --extra corrected
```

Launch a deterministic 42-second replay through the new application and the
real local engine:

```text
uv run atpiano workbench-v3 \
  --workspace results/workbench-v3-r3 \
  --port 8002 \
  --replay results/musical-loop-validation/input.json \
  --no-wait \
  --minimum-free-gib 0
```

The command builds the pinned application, opens it in the default browser,
runs the replay without wall-clock delay, and keeps the local review server
available. Use a fresh workspace path for an empty first-run review.

For the physical microphone review:

```text
uv run atpiano workbench-v3 \
  --workspace results/workbench-v3-microphone \
  --port 8002
```

Select **New session**, choose **Start microphone**, grant browser permission,
play the desired material, then choose **Stop & settle**. Physical microphone
capture is intentionally a consenting human lane and was not opened during
the unattended pass.

## Interaction Map

| UI state | Durable effect | Important target rule |
| --- | --- | --- |
| New session | none until capture starts | history remains unchanged |
| Fixture replay | creates one replay session | returned capture selects only its own session |
| Start microphone | creates one active capture | PCM and Stop retain capture/session IDs |
| Select history | changes only the viewed session | an active capture continues on its original target |
| Render or refresh score | starts a job at the selected commit horizon | failure does not replace capture or session review |
| Download export | resolves one selected-session artifact | filename and checksum remain visible |
| Delete session | moves a confirmed historical session to recoverable trash | active sessions are not offered deletion |

The left rail distinguishes unpersisted **New**, recent history, and the active
recording. The main header names the selected performance. If history is
selected during capture, a persistent banner points back to the live
performance without silently changing selection.

## Review Walkthrough

1. Start with the deterministic replay command and inspect the newest session.
2. Toggle Piano roll, Keyboard, and Score independently.
3. Click the roll and move the exact-time keyboard inspection control.
4. Render the committed score and confirm real engraved notation appears.
5. Download MusicXML, MIDI, event history, or audio from the artifact list.
6. Enter New and confirm this alone does not add a history item.
7. Return to history, attempt Delete, and inspect the explicit recoverable
   confirmation before cancelling or accepting it.
8. Run the microphone command, verify permission/requesting/recording/settling
   states, and select an older session while capture continues.
9. Narrow the browser to a phone-sized width and confirm the session identity,
   controls, metrics, and views remain legible without page-level horizontal
   overflow.

Review the terminology, information hierarchy, control grouping, session
mental model, usefulness of the three performance views, responsive behavior,
and whether this still feels like a piano workbench rather than an
administration dashboard.

## Intentional Differences From V2

- New, selected history, and active capture are explicit instead of sharing
  one server-global current-session concept.
- A persistent history rail replaces silent newest-session selection.
- Status and source-sample evidence are summarized above the musical views.
- Score, roll, and keyboard are independently visible cards. MusicXML is
  rendered by the same pinned OSMD version, now loaded locally as a lazy
  application chunk rather than from a public CDN.
- Checksummed artifacts share one selected-session export panel rather than
  several unqualified download links.
- The visual treatment is a focused dark piano workspace, but the engine,
  source clock, corrected/provisional distinction, score pipeline, and stored
  session formats are retained.
- The React application talks only to `AtpianoRuntime`. The current-local
  provider still composes the retained v2 engine; moving that engine behind
  framework-independent Python services is Phase 4.

## Automated And Golden Evidence

The unattended real-engine run used
`results/workbench-v3-phase3/20260726T110313-3689eac9fb42` and the same frozen
musical WAV as the accepted v2 product run:

```text
audio SHA-256:
0eab5d787cb482735dc840daaed2abfb6d00ad6ff7a7058fdd217522905aaa89
source timeline:
2,016,000 frames at 48,000 Hz (42 seconds)
append history:
946 revisions
latest committed result:
152 notes and 12 pedal intervals
committed MIDI SHA-256:
bf7de6c88ef84b04b1dd7b2632810fe88b0f86e38768063bc641960f787003a0
```

The source timeline, counts, and committed MIDI are exact matches for
`results/workbench-v2-product-validation`. Append-history bytes intentionally
differ because session IDs and emission timestamps are run-specific.

The real browser consumed the explicit local APIs, displayed all 152 notes,
completed and polled a score job, downloaded the resulting MusicXML through
its artifact access handle, and rendered it as SVG. Automated tests also
cover score failure isolation.

The final `uv run atpiano migration-regression` passed at
`results/migration-regression/20260726T111635Z/report.json`: 78 Python tests,
the retained JavaScript suites, 14 application tests, contract drift,
TypeScript, dependency audit, Ruff, JavaScript syntax, and whitespace all
passed. The dependency audit found zero vulnerabilities.

Orientation screenshots are ignored runtime evidence rather than repository
source:

- `results/r3-interaction-review/desktop.png`
- `results/r3-interaction-review/mobile.png`

The browser pass used 1440×1000 and 390×844 viewports. Both had no alert,
connection error, or page-level horizontal overflow. Screenshots orient the
review; the live application is authoritative.

## Decision Requested

Please respond with either:

- **R3 accepted** — Phase 4 may open; or
- requested changes — Phase 3 remains open and the feedback is resolved
  before any Python application-service extraction.
