# 014 — Freeze Migration Baseline

Master phase: 1. Freeze and characterize

Topic: multi-tenant-hybrid-service-architecture

Status: in progress on 2026-07-26.

## Entry Evidence

- The accepted program and gates are recorded in
  [`013-hybrid-product-migration-master.md`](013-hybrid-product-migration-master.md).
- The supported v1 `workbench` and v2 `workbench-v2` commands are documented
  in the repository README.
- The clean repository baseline passes 50 Python tests on the current macOS
  arm64 development environment.
- The aligned 42-second musical fixture, retained target-piano recording
  facts, corrected replay engine, exports, and internal score-snapshot path
  already have completed tactical evidence.

## User-Visible Outcome

There is no new product shell in this phase. A maintainer gets one documented
command that validates the migration baseline and writes a machine-readable
report. The report and tracked fixtures identify which v1 and v2 behavior the
new product must preserve, which evidence is manual or machine-dependent, and
which proof-of-concept behavior is deliberately not frozen.

## Invariants

- The v1 and v2 commands, frontends, artifact layouts, and current aliases
  remain runnable and readable.
- The audio sample clock remains the only musical-event timeline.
- Deterministic fixtures exercise the same session engine used by capture.
- Model checkpoints, generated audio, sessions, and score artifacts remain
  outside Git.
- Normalized evidence freezes public behavior without freezing volatile
  timestamps, local paths, ports, disk availability, or implementation
  serialization accidents.

## Exact Implementation Scope

1. Record the supported commands, dependency groups, platform constraints,
   runtime assets, model/checkpoint manifests, manual lanes, and known
   proof-of-concept limits.
2. Add deterministic characterization for:
   - the aligned musical input manifest and reference structure;
   - v1 configuration, capture job, restart, artifact, and route behavior;
   - v2 configuration, replay/microphone session, Stop, restart recovery,
     event-range, horizon, export, score, and artifact behavior; and
   - preservation of source-sample coordinates and explicit IDs.
3. Check in normalized route and product fixtures whose dynamic fields are
   intentionally removed or replaced by stable markers.
4. Add one migration-regression command that runs Python, JavaScript, lint,
   syntax, and whitespace lanes and writes a JSON report under ignored
   `results/`.
5. Add a concise behavior inventory and R1 evidence handoff.

## Explicit Exclusions

- No React, TypeScript runtime, Tauri, hosted service, account, or sync work.
- No session catalog, history UI, deletion, or framework extraction.
- No model retuning, schema redesign, artifact migration, or compatibility
  route removal.
- No automatic microphone activation, real checkpoint download, long soak,
  or unresolved score-runtime installation.
- No claim that an unaligned acoustic recording is ground truth.

## Migration And Compatibility

Characterization adds tests and evidence around existing behavior. It may add
read-only helpers needed to normalize reports, but it does not change product
routes or session semantics. Discovered defects are recorded for a later
bounded slice unless they prevent reproducible baseline collection.

The current unqualified v2 session, event, score, and artifact routes are
explicitly treated as compatibility behavior, not the durable Phase 2
contract.

## Automated Validation

- `uv run atpiano migration-regression`
- focused baseline fixture and route-characterization tests
- existing repository-wide Python and JavaScript tests
- Ruff, JavaScript syntax, and Git whitespace checks

The regression command must return nonzero when a required lane fails and
must distinguish skipped manual, optional-model, and licensed lanes from
passing automated evidence.

## Manual Validation

The report links short instructions for:

- v1 and v2 physical microphone Start/Stop;
- v2 aligned replay with optional Basic Pitch and Transkun lanes;
- internal score generation when the isolated runtime exists; and
- retained target-piano playback and subjective comparison.

No microphone is opened by the automated command.

## Human Review Packet

R1 receives:

- a one-page behavior inventory;
- the exact regression command and latest result;
- discrepancies or ambiguities found;
- proposed deliberate non-parity; and
- the bounded Phase 2 tactical proposed from this evidence.

R1 is an evidence handoff unless characterization exposes an ambiguous useful
behavior or a product decision that must be resolved before contracts freeze.

## Rollback Or Disable Path

All phase output is additive. Reverting the tactical's implementation commits
removes the regression command, fixtures, and documentation without changing
either application or existing artifacts.

## Execution Record

In progress. Append commit IDs, validation results, baseline hashes,
discrepancies, and the R1 disposition as the slice lands.
