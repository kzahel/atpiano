# 044 — Score Reliability Harness

Topic: performance-to-notation

Status: **planned on 2026-07-28.**

## Goal

Turn the retained-score checks used during Tacticals 035 and 043 into one
explicit, slow validation command. The command must exercise real current
recordings through visible Playwright browsers and keep the Python score
producer's MIDI-tick ordering contract aligned with the TypeScript consumer.

This is a cleanup and confidence-building slice. It does not change notation
semantics, regenerate scores, or become part of the ordinary fast migration
gate.

## Motivation

Two retained scores exposed different producer/browser tick-order mismatches.
Both MusicXML artifacts were readable and both server-side alignments were
valid, but the browser rejected their playback cursors. Ad hoc retained-score
audits found the defects and eventually exercised all nine current recordings
in Chromium and WebKit.

That evidence is useful but not yet repeatable from the repository. The
project needs:

1. a durable cross-language timing corpus that fails before Python and
   TypeScript ordering semantics drift; and
2. a deliberate end-to-end browser command that proves current retained
   scores still engrave, navigate, and move a cursor in the deployed
   application.

## Command Shape

Add an operator command with an explicit expensive browser lane:

```text
uv run atpiano validate-scores \
  --workspace results/workbench-v3 \
  --base-url https://atpiano.graehlarts.com \
  --browser chromium \
  --browser webkit \
  --headed
```

A fast structural-only form should remain available:

```text
uv run atpiano validate-scores \
  --workspace results/workbench-v3 \
  --structural-only
```

The browser lane is opt-in, slow, and locally initiated. It must not silently
join `migration-regression`, production startup, score generation, or an
ordinary service restart.

## Inventory Contract

The command freezes one read-only inventory at startup:

- every complete, non-trashed session in the selected workspace;
- its selected score variant and exact artifact IDs;
- current MusicXML and alignment hashes;
- sample rate, note count, score horizon, and producer freshness; and
- first, middle, and last mapped cursor attacks when alignment is available.

Sessions without a current score are reported as `missing`, not skipped.
Malformed, incompatible, or untracked snapshots retain their exact
classification. An active score job or a current-pointer change during the
run must produce an explicit unstable-target result rather than mixing two
snapshots.

The validator is read-only. It must not start score jobs, select variants,
rename sessions, or change annotations.

## Structural Lane

For every frozen target:

1. resolve the session and artifacts through the ordinary application
   boundary;
2. verify catalog byte counts and SHA-256 values;
3. parse MusicXML and require a partwise score with pitched content;
4. parse alignment and verify its source session, selected MusicXML hash,
   schema, mapping descriptor, source ordering, and score monotonicity;
5. confirm the current producer freshness classification; and
6. retain summary counts for notes, mapped attacks, unmatched source notes,
   inserted score elements, measures, parts, and reader pages where known.

The lane writes one ignored machine-readable report below:

```text
results/score-validation/<timestamp>/report.json
```

Use schema `atpiano.score-validation-report.v1`. Record command arguments,
application revision and dirty state, target origin, client build identity,
browser names and versions, per-session durations, exact failures, and final
operator-session revocation.

## Headed Browser Lane

Use Playwright-managed Chromium and WebKit as development-only dependencies.
Their browser downloads remain outside Git and the production application.
Document the one-time installation command and fail with a direct acquisition
instruction when a requested engine is absent.

Run the requested engines sequentially by default so the operator can observe
the visible windows and so several large OSMD documents do not compete for
memory. Use a fresh page for each frozen session.

For each engine and session:

1. open the real session URL through `--base-url`;
2. require HTTP 200 and the expected selected session;
3. require inline OSMD SVG output and no score, alignment, or page exception;
4. seek the shared playback scrubber to the first, middle, and last mapped
   attacks and require `cursorImg-0` to become visible at each;
5. open the artifact-pinned score reader;
6. require every OSMD reader page to exist and exercise first/next/last page
   navigation without losing the selected score or playback state; and
7. capture console errors, uncaught exceptions, failed requests, and a
   screenshot on failure.

The command may also support `--headless` for automation, but headed execution
is the acceptance lane. Playwright WebKit is a WebKit compatibility check; it
must not be described as automation of the installed Safari application.
Consentful Safari review remains a separate human lane.

## Authentication And Cleanup

When the target is an authenticated family service, reuse the bounded local
operator authority established by `family-check`:

- issue a short-lived session for an enabled workspace member;
- never print the token or include it in a report, command line, screenshot,
  or browser log;
- pass it only to the isolated browser contexts;
- close every page, context, and browser in `finally`; and
- revoke and verify the operator session even after timeout or interruption.

The public application shell, protected API, Caddy proxy, artifact delivery,
and real production frontend must all remain in the exercised path.

## Cross-Language MIDI-Tick Conformance

Add one generated canonical fixture:

```text
contracts/fixtures/v1/midi-tick-parity.json
```

The fixture records:

- sample rate, ticks per beat, and tempo;
- the producer operation identity
  `mido-second2tick-float-python-half-even-v1`;
- source samples and expected MIDI ticks;
- onset/offset pairs and expected tick durations; and
- colliding note rows with their expected transformer order.

Seed it with both retained failures and boundary cases:

- source sample `3063125`, whose floating conversion lands on the
  ties-to-even-down path;
- source samples `1556525` and `1556530`, whose producer intermediates share
  tick `31131`;
- values immediately below and above a nominal half tick;
- same-tick pitch and duration tie-breaks;
- exact onset/offset sample and event-identity tie-breaks; and
- large valid source positions near the supported session limit.

Python owns fixture generation through the existing generated-contract check.
Python tests verify `midi_tick_at_sample` and source-note ordering against the
checked-in expectations. TypeScript tests consume the same JSON and verify
the browser tick helper, duration key, and complete ordering result.

Do not generate independent Python and TypeScript expectation files. A
deliberate producer conversion change requires an explicit fixture identity
change, a score-pipeline compatibility decision, and retained-score refresh
evidence. Algebraically simplifying the floating-point operation order without
that process is a test failure.

## Failure Semantics

Use stable result categories:

- `missing-score`;
- `artifact-integrity`;
- `musicxml-parse`;
- `alignment-compatibility`;
- `alignment-order`;
- `inline-render`;
- `cursor-movement`;
- `reader-render`;
- `browser-runtime`;
- `target-changed`; and
- `operator-cleanup`.

Continue across independent sessions after a bounded failure. Return a
nonzero command status if any requested session/browser check fails, while
preserving the complete report and failure screenshots.

## Out Of Scope

- subjective sight-readability or musical correctness;
- listening to the captured audio;
- acoustic-model or score-model inference;
- automatic score regeneration;
- installed Safari automation;
- public or CI browser credentials;
- default inclusion in the fast migration gate; and
- static frontend asset continuity across deployments.

Static asset fallback, version polling, reload behavior, and old hashed-asset
retention require a separate deployment tactical because they affect every
application route and open tab, not only scores.

## Implementation Sequence

1. Define and generate the MIDI-tick parity fixture.
2. Move the browser tick conversion into a directly testable pure helper.
3. Add Python and TypeScript conformance tests over the same fixture.
4. Implement read-only inventory, structural checks, and the versioned report.
5. Add the Playwright runner and development-only browser acquisition path.
6. Add local-operator issuance, guaranteed revocation, and failure artifacts.
7. Run the headed lane against every current retained score.
8. Record runtime, browser versions, session/page counts, and observed gaps in
   the continuing notation topic.

## Acceptance

- The generated-contract check detects any fixture drift.
- Python and TypeScript pass every canonical tick and ordering case.
- Synthetic tests prove each stable failure category and a nonzero aggregate
  result.
- Interrupt and timeout tests prove the operator session is revoked.
- The structural lane detects missing, corrupt, incompatible, and changed
  targets without mutation.
- Headed Chromium and WebKit exercise all current retained recordings.
- Every healthy score renders inline and in the reader.
- First, middle, and last mapped attacks expose a visible OSMD cursor.
- A known bad fixture is rejected with its exact session, browser, stage, and
  diagnostic evidence.
- The report contains no credential material.
- The existing frontend, TypeScript, generated-contract, Python, and migration
  regression gates remain green.
