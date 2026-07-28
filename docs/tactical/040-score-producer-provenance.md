# 040 — Score Producer Provenance

Topic: performance-to-notation

Status: **complete and live on 2026-07-28.**

## Motivation

Retained session `20260726T134843-17b0729ad6ca` renders its MusicXML but the
current browser rejects its playback cursor. The snapshot is not missing
alignment metadata: it contains `atpiano.score-alignment.v1`, whose first
rows demonstrate the source-identity shift that v2 later corrected. The
existing fallback says only that the cursor could not load, so the user
cannot distinguish a legacy incompatible score from corrupt content or a
transient fetch failure.

Score snapshots already retain generation time, artifact hashes, alignment
schema, postprocessor version, upstream model commit, and checkpoint hash in
separate places. They do not retain the exact Atpiano producer code or one
explicit compatibility revision. The top-level snapshot and adapter schemas
may remain structurally valid across a behavior correction, so schema names
alone cannot answer whether a refresh would apply newer score logic.

## Contract

Every newly generated score snapshot records one
`atpiano.score-producer.v1` block containing:

- a positive, manually bumped score-pipeline revision;
- a SHA-256 fingerprint of the Atpiano source files that produce and validate
  score artifacts;
- the Atpiano package version, Git revision when available, and whether the
  source worktree had tracked changes;
- the adapter, alignment, and postprocessor revisions; and
- the exact upstream model commit and checkpoint SHA-256 when a pinned runtime
  performed the generation.

The pipeline revision changes only when score output, alignment compatibility,
or another refresh-relevant producer behavior changes. Ordinary UI or
unrelated application commits do not make every retained score stale. The
source fingerprint and Git state provide exact diagnostic identity without
being used as a compatibility promise.

The existing score-variant page exposes snapshot-level producer provenance
and one backend-computed freshness result:

- `current`: the snapshot has the current pipeline revision;
- `older-compatible`: the snapshot has an earlier tracked revision but its
  published alignment contract remains supported;
- `incompatible`: the alignment or producer revision cannot be consumed
  safely by the current application; or
- `legacy-unknown`: the score predates producer tracking but remains
  structurally compatible.

The result also records a stable reason, current and snapshot pipeline
revisions, and whether refresh is recommended. A producer revision newer than
the running application is incompatible but does not recommend regenerating
with the older producer.

## User-Visible Outcome

- The score card identifies the retained snapshot as pipeline `rN` and current,
  or as an untracked legacy score.
- An older compatible score remains readable and receives a refresh advisory.
- A score with v1 cursor alignment says that it uses legacy cursor metadata
  and that **Refresh score** will generate the current mapping.
- A genuine alignment fetch, hash, or parse failure retains the generic
  degraded cursor message.
- Refreshing a score publishes current provenance without modifying source
  audio, corrected events, or the frozen commit horizon.

## Invariants

- Historical snapshot bytes are never silently relabeled with current
  provenance.
- Missing or malformed provenance degrades to a bounded freshness state and
  never hides otherwise plausible MusicXML.
- Compatibility is decided from explicit pipeline and artifact schemas, not
  generation timestamps or Git commit ordering.
- A dirty source tree is reported rather than disguised as its clean HEAD.
- Fixture/injected score runners do not claim to have used the pinned model
  runtime.
- Score variants inherit the snapshot producer; selecting or deriving an
  engraving variant does not pretend to rerun the model.

## Validation

- Focused snapshot tests verify complete producer metadata, stable
  fingerprints, dirty/revision handling, and omission of model claims for an
  injected runner.
- Repository/API tests classify current, older-compatible, incompatible v1,
  future, malformed, and untracked v2 snapshots.
- Frontend tests verify revision labels, the legacy-cursor refresh message,
  and isolation of unrelated alignment failures.
- Generated OpenAPI/TypeScript contracts, Python tests, Ruff, TypeScript,
  frontend tests, production build, migration regression, and Git whitespace
  pass.
- If the shared macOS service is active, restart it and verify the public
  homepage and protected capability API.

## Execution Record

New snapshots now publish score-pipeline revision `2`. Their producer block
hashes the six tracked Atpiano source modules that select source events, write
transformer MIDI, generate and reconcile MusicXML, validate alignment, and
derive variants. It also records Atpiano version, Git revision, tracked-dirty
state, adapter/alignment/postprocessor revisions, execution mode, and the
pinned upstream commit and checkpoint when those assets actually ran.

The local repository adapter classifies the selected snapshot once and
publishes that result with its score variants. It recognizes current r2,
older compatible positive revisions, newer-than-application revisions,
untracked v2 artifacts, unsupported producer records, and unsupported
alignment schemas. It never modifies a retained manifest. The shared React
score card shows the revision and status, gives a specific refresh instruction
for legacy cursor metadata, and preserves the generic degraded message for
unrelated alignment failures. The pinned score reader gives the same specific
legacy explanation when its exact alignment artifact is v1.

Focused validation passed with 28 Python snapshot/repository/API tests and 29
React application tests. The complete migration regression passed at
`results/migration-regression/20260728T122307Z/report.json`: 217 Python tests,
88 Vitest tests, six TypeScript Node tests, generated-contract parity,
TypeScript, zero high-severity npm audit findings, Ruff, retained JavaScript
syntax, and Git whitespace all passed. The production Vite build passed with
only the existing OpenSheetMusicDisplay chunk-size advisory.

A real pinned-runtime generation over a disposable copy of retained session
`20260726T134843-17b0729ad6ca` produced r2 provenance with Atpiano source
fingerprint
`783f52b88c55481ffe8db259e4c34a35e3a721784a2baaee12b59ec90d4ef0b2`,
upstream commit `115432bda16ca16e0fec2e9465788f2ba369971f`, and checkpoint
SHA-256
`7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`.
Its v2 alignment retained 71 exact-pitch mappings, 15 unmatched source notes,
15 inserted score elements, and classified current. The original retained
snapshot remained unchanged and classified `incompatible` for
`alignment-schema-unsupported`, with refresh recommended.

The already-active authenticated share service restarted onto
`assets/index-MInMg0mS.js`. The exact public session URL returned HTTP 200,
and anonymous capability access remained protected with HTTP 401.
