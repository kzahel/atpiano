# 016 — Shared React Application

Master phase: 3. Shared React application

Topic: multi-tenant-hybrid-service-architecture

Topic: session-workspace-management

Status: implementation revised after R3 exposed live-event range, horizon
presentation, and misleading score-placeholder defects. The fixes are
validated. Pathological score expansion and missing session-addressed URLs
were subsequently corrected. Stop progress and automatic post-settle score
generation are now implemented. Inferred sustain and soft-pedal gestures are
also distinct after a merged lane misreported a long soft-pedal false positive
as stuck sustain. The revisions await explicit R3 re-review. Phase 4 must not
start before that decision.

## Entry Evidence

- R2 was explicitly accepted by the user on 2026-07-26 after the terminology
  revision in `3b53285` and review update in `9f8dd16`.
- Phase 2 contracts, fixture runtime, explicit local routes, generated
  TypeScript, and regression evidence are complete.
- `uv run atpiano migration-regression` passes 78 Python tests, retained
  JavaScript suites, contract drift, TypeScript checks, dependency audit,
  Ruff, syntax, and whitespace lanes.
- The v1 and framework-free v2 applications remain independent regression
  oracles.

## User-Visible Outcome

Add a separately runnable React/TypeScript/Vite application that preserves
the useful corrected-note workbench while making session ownership explicit.
The first screen must read as a piano-performance workspace rather than a
generic administration dashboard.

The application supports deterministic fixture replay and physical microphone
capture through `AtpianoRuntime`. It separates the selected session from the
active capture, offers an unpersisted New state and history, and keeps the
timeline, keyboard, score, artifacts, and recoverable delete addressed to the
selected session.

## Invariants

- Musical time remains source-sample-derived.
- Runtime calls always name workspace, session, capture, job, and artifact
  targets.
- Changing the selected session cannot redirect capture, Stop, score, delete,
  or a late response.
- Runtime-owned remote state uses TanStack Query. Zustand owns only
  client-local selection, view preferences, and capture state.
- Capture transitions are explicit and reject stale completions.
- UI components import `AtpianoRuntime`, not endpoint paths, Tauri APIs,
  filesystem paths, or browser transport details.
- Fixture and local providers implement the same runtime interface.
- v1 and v2 commands, assets, routes, and session files remain runnable and
  readable.

## Exact Implementation Scope

### 1. Application shell and state

- Add pinned React, React DOM, Vite, TanStack Query, and Zustand dependencies.
- Add a responsive application shell, error boundary, accessible status
  regions, and deterministic fixture composition.
- Implement an explicit capture machine covering idle, requesting, warming,
  recording, stopping, and failed states.
- Keep selected workspace/session, New intent, view toggles, follow-head, and
  inspection position as small client-owned state.

### 2. Session workspace

- Load workspace and newest-first session history through queries.
- Distinguish New, selected historical, and active recording presentation.
- Keep active capture visible while a different historical session is
  selected.
- Confirm recoverable delete and disable it for active or job-owned targets.
- Invalidate only affected explicit query keys after mutations.

### 3. Performance views

- Render independently toggleable piano roll, 88-key keyboard, and score
  panels.
- Show provisional versus committed notes, source horizons, pedal events,
  visible range, and exact inspection time.
- Expose checksummed artifact downloads and score-job state without allowing a
  score failure to break capture or historical review.
- Preserve useful status, empty, loading, failure, and narrow-screen states.

### 4. Runtime providers and launch path

- Extend the deterministic fixture provider only where a real UI consumer
  requires observable behavior.
- Add a current-local provider that contains ordinary HTTP, replay, score,
  artifact, WebSocket, microphone, PCM, and Stop transport composition.
- Keep endpoint strings out of React components.
- Add an independently runnable `workbench-v3` command serving the built
  application over the retained local engine, including deterministic replay
  arguments and microphone mode.

### 5. Validation and review evidence

- Unit-test the capture reducer, selection/late-result guards, view state, and
  runtime adapters.
- Component-test New/history/delete, session selection, toggles, errors, and
  score isolation.
- Run the golden replay through the new application and compare normalized
  local engine output with the Phase 1 baseline within its declared
  tolerances.
- Keep migration regression green and prepare the live R3 review commands,
  intentional differences, screenshots for orientation, and interaction
  checklist.

## Explicit Exclusions

- No Python application-service extraction; that is Phase 4.
- No Tauri APIs, sidecar protocol, packaging, or updater.
- No hosted authentication, database, object storage, worker deployment,
  collaboration, or sync.
- No visual marketing site, server-side rendering, routing framework, or
  general design-system project.
- No model, decoder, reconciliation, score-quality, or latency-policy changes.
- No permanent delete, session rename, continuation, or resumption.
- No removal of v1, v2, or their compatibility routes.
- No public MIDI2ScoreTransformer operation or distribution.

## Automated Validation

- `npm run typecheck --prefix app`
- `npm test --prefix app`
- `npm run build --prefix app`
- focused Python server/CLI tests for the v3 launch surface
- fixture-provider and local-provider contract tests
- golden replay comparison through the local engine
- `uv run atpiano migration-regression`

## Manual Validation

- deterministic replay starts from one documented command;
- microphone Start, permission, recording, Stop, and settling are visible;
- New/history/selected/active identity remains understandable;
- timeline, keyboard, and score can be toggled independently;
- historical selection during another active capture does not retarget it;
- recoverable delete is explicit and guarded;
- artifact downloads name the selected session; and
- missing score runtime is isolated and clearly explained.

## Human Review Packet

R3 receives:

- one deterministic replay launch command and one microphone command/action;
- an interaction map for New, history, selected session, and active capture;
- visible timeline, keyboard, score, artifacts, job, empty, and failure states;
- a short list of intentional differences from v2;
- screenshots as orientation plus the live local application;
- automated and golden-replay evidence; and
- the Phase 3 commit range.

The user reviews terminology, hierarchy, controls, session mental model,
visualization usefulness, responsive behavior, and whether this still feels
like the useful piano workbench. Substantive feedback is resolved before
Phase 4.

## Rollback Or Disable Path

The React application and `workbench-v3` launch surface are additive. v1 and
v2 remain the fallback commands and keep their current assets. Reverting the
Phase 3 series removes the new application without migrating session data or
changing established artifacts.

## Execution Record

The implementation series began at `a9805fd` and is:

- `a9805fd` opened Phase 3 after explicit R2 acceptance;
- `5ab177b` built the fixture-driven React workspace;
- `a6fe0ab` connected the shared application to the retained local engine;
- `6509c79` completed score polling, bounded event reads, and runtime feedback;
- `836ce69` covered score failure isolation; and
- `d049fdf` restored actual committed-MusicXML rendering with pinned,
  lazy-loaded OSMD; and
- `8a9a78e` fixed live recognition ranges after the first R3 microphone
  review; and
- `7423159` clipped corrected display at the commit horizon and removed
  synthetic placeholder engraving after follow-up review;
- `f8d096e` rejected and hid pathological score-model note expansion; and
- `f39179a` put the selected session ID in copyable browser URLs; and
- `938a15b` added settling progress and automatic post-capture scoring; and
- `dab105b` separated inferred sustain and soft-pedal gestures and marked
  unusually long estimates for verification.

The real page-facing golden replay is recorded in
[`r3-interaction-review.md`](../r3-interaction-review.md). Its 42-second
source timeline, 946 revisions, 152 committed notes, 12 pedal intervals, and
committed MIDI hash match the accepted v2 product run. Desktop and
narrow-screen browser checks exercised New/history navigation, independent
views, the score job, artifact refresh, and real SVG notation without browser
alerts or page-level horizontal overflow.

The final `uv run atpiano migration-regression` report at
`results/migration-regression/20260726T120958Z/report.json` passed 81 Python
tests, retained JavaScript tests, 27 application tests, contract drift,
TypeScript, dependency audit, Ruff, syntax, and whitespace. Physical
microphone permission and playing remain the explicit human lane at R3. The
implementation range is `a9805fd^..HEAD` at this review handoff. Phase 4
remains closed pending the user's interaction decision.

The first R3 review was not accepted: microphone results appeared only after
Stop. The captured sessions contained final notes, isolating the failure to
the live reader. `8a9a78e` moved the event window and musical-view duration
from the zero-frame Start snapshot to the advancing audio horizon. A real
browser/fake-device pass over the frozen musical WAV displayed 74 notes before
Stop, 55 already corrected, and then settled to 113 final notes. The exact
feedback, cause, validation path, and re-review request are recorded in
[`r3-interaction-review.md`](../r3-interaction-review.md).

Follow-up R3 screenshots showed corrected bars extending beyond `H_commit`
and a synthetic pitch-dot staff that looked like live engraving. `7423159`
clips corrected solids at the commit horizon, restores dashed open-note tails
ending at that boundary, and removes all fake notation. The score panel is
plain text until a real MusicXML artifact exists; real engraving is explicitly
labeled as a frozen generated snapshot rather than a live view.

The two-chord follow-up session had 13 correct score-input MIDI notes but 491
pitched elements in the transformer output. `f8d096e` now fails that score
job before publication and hides existing invalid pointers while retaining
their diagnostic files. `f39179a` adds `?session=<session-id>` selection so a
copied review URL resolves the exact performance.

Further review found no clear progress after Stop and an unnecessary manual
score action. `938a15b` disables Stop immediately, displays exact
commit-to-audio-head progress, and automatically starts scoring once the
settled session and final horizon are available. A real 20.5-second browser
capture moved from 60% settling to a ready rendered score without another
click.

The next screenshot's scrollbar-like **SUSTAIN** bar was a presentation bug
over a known quality limitation. The session contains nine CC64 intervals and
one long CC67 interval, but React had merged both kinds under one sustain
label. `dab105b` restores the separate v2 meanings, labels both lanes as
inferred, gives them distinct capped gesture styling, hatches unusually long
estimates, and clips committed controller intervals at `H_commit`. The
performer identified the long CC67 interval as false; the UI now exposes that
uncertainty without silently discarding controller output.
