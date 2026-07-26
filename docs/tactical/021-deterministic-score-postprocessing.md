# 021 — Deterministic Score Post-Processing

Topic: performance-to-notation

Status: planned on 2026-07-26; implementation has not started. Build on
Tactical 020's implemented shared score component and exact pinned-artifact
reader identity.

## Motivation

MIDI2ScoreTransformer produces useful score structure, but a structurally valid
MusicXML file can still contain deterministic readability failures that do not
justify model retraining.

Retained session `20260726T142937-d49ef33ca321` is the first concrete example:

- the performer played the BWV 853 fugue and expected its conventional
  D-sharp-minor spelling with six sharps;
- the model selected the enharmonic six-flat signature;
- the model selected 3/4 rather than the source score's 4/4;
- the opening subject was assigned to the second part; and
- the pinned upstream detokenizer unconditionally gave that part a bass clef,
  producing as many as four ledger lines where a treble clef would be
  substantially easier to read.

The snapshot contains 272 input notes and 281 pitched MusicXML elements, so it
passes the existing note-expansion plausibility gate. Its lower part contains
107 pitched elements from MIDI 41 through 71. Forty-three are at or above
middle C and 28 are at or above E4. Measures 1 through 9 are consistently in
treble-clef territory, while later measures descend far enough that changing
the entire part to treble clef would merely move the readability failure.

The screenshot supplied during review remains outside Git:

```text
filename:
Screenshot 2026-07-26 at 4.32.43 PM-sd.png
SHA-256:
4908bbef49c59fd5173662aa5e7de96ca5a164ec9646c1eb49073d88c73bbf7d
dimensions: 1024 x 401
```

This evidence separates three concerns:

- wrong meter and possibly wrong hand/staff assignment are model-inference
  errors;
- a high passage forced through a permanently bass-clef second part is a
  deterministic score-construction defect; and
- enharmonic key choice is not identifiable from sounding pitch alone, so a
  user preference or reference-score identity must be allowed to resolve it.

This tactical addresses the latter two concerns. It does not claim to repair
meter, quantization, hand assignment, or voice inference.

## Existing Intermediate Representation

The model does not write XML text directly. The current adapter already has
the required semantic boundary:

```text
committed performance MIDI
            |
            v
MIDI2ScoreTransformer compound-token output
            |
            v
music21 Score from MultistreamTokenizer.detokenize_mxl
            |
            v
upstream score_utils.postprocess_score
            |
            v
source alignment + MusicXML serialization
            |
            v
OSMD renderer
```

The compound output predicts offset, duration, downbeat, pitch, accidental,
key signature, voice, stem, and hand streams. Clef is not a predicted stream.
The upstream detokenizer inserts treble clef for Part 1 and bass clef for Part
2 regardless of their note ranges.

The `music21.Score` is currently process-local rather than a durable artifact.
MusicXML remains the canonical persisted score interchange. The new pipeline
should therefore transform a deep copy of the semantic score before
serialization and retain a pre-atpiano baseline MusicXML artifact for
inspection and rollback. It does not need to persist Python objects or model
tensors.

## Product Outcome

Every new inferred score receives a deterministic, versioned post-processing
pass before it becomes the default readable interpretation:

1. preserve the baseline score after upstream structural cleanup;
2. assign stable note identities shared by all derived variants;
3. apply any explicit enharmonic-spelling recipe;
4. optimize clefs over stable musical spans;
5. recompute accidental display state;
6. serialize and validate a derived MusicXML artifact; and
7. publish that derived artifact only when invariants and readability checks
   pass.

Automatic clef cleanup is the default. The score UI offers an
**Enharmonic key** action only when a safe pitch-preserving alternative exists.
That action creates and selects another exact score variant without rerunning
the transformer.

The baseline remains downloadable as diagnostic evidence. A failed transform
never destroys or overwrites it.

## Score-Variant Contract

A score variant is a deterministic interpretation of one exact inferred
snapshot. Its identity includes:

- workspace, session, transcription run, and commit sample;
- baseline MusicXML and alignment hashes;
- post-processor name and version;
- normalized post-processing options;
- explicit key override, if any;
- clef-policy version and cost parameters; and
- resulting MusicXML and alignment hashes.

Derive `variant_id` from a canonical hash of the baseline identity,
post-processor version, and options. Repeating the same request is idempotent.
Changing a cost constant or spelling policy produces a different variant
rather than silently changing an old artifact.

One possible retained layout is:

```text
score/snapshots/<H_commit>/
  baseline/
    score.musicxml
    alignment.json
  variants/
    <variant-id>/
      score.musicxml
      alignment.json
      manifest.json
  manifest.json
```

The exact layout may follow the application-core artifact store when Tactical
017 lands, but these identities and immutability rules must remain stable.
Existing snapshots with `score.musicxml` at the snapshot root remain readable
without migration and are treated as baseline-only snapshots.

`score/current.json` may identify the preferred default variant for workspace
preview, but it must not redefine the identity of a score already pinned by
Tactical 020's reader. Publishing or selecting another variant appears as a
new score artifact; it does not mutate the reader's bytes.

## Stable Note Identity And Alignment

Post-processing must not weaken Tactical 018's source-to-score contract.

Assign final MusicXML note IDs once after upstream structural cleanup and
before creating variant copies. The transforms in this tactical preserve:

- note and chord membership;
- MIDI pitch;
- score onset and duration;
- tie segmentation;
- part and voice assignment;
- source event mapping; and
- MusicXML note ID.

Each variant receives an alignment artifact whose MusicXML hash names that
exact variant. The alignment rows may otherwise remain equivalent. Run the
existing alignment validator against every serialized result instead of
assuming an in-memory transform preserved identity.

If a later transform moves notes between staves, changes voices, merges
chords, or rewrites ties, it is outside this tactical and must regenerate and
validate the affected semantic mappings explicitly.

## Automatic Clef Optimization

### Boundary

The first pass chooses only ordinary treble (`G2`) and bass (`F4`) clefs for
each existing piano part. It does not move notes between parts or voices.

Candidate switch positions are measure boundaries. That is sufficient for the
retained BWV 853 failure and keeps the first result easy to inspect. Mid-measure
changes may be considered later at rest or beat boundaries only after
independent readability evidence.

Empty measures inherit the active clef and do not create switch candidates.
Tied notes crossing a boundary do not receive a clef change in the middle of
their tie unless a later policy explicitly supports and validates it.

### Cost

For each part and measure, calculate both candidate-clef costs from semantic
note positions:

- zero cost for noteheads on or within the five-line staff;
- increasing cost for each required ledger line;
- a stronger penalty for three or more ledger lines;
- every pitch in a chord contributes;
- a clef-change penalty discourages flicker;
- a small preservation cost favors the existing clef when alternatives are
  effectively tied; and
- optional minimum-span evidence prevents a one-measure switch with negligible
  gain.

Use dynamic programming over measures and clef state to minimize total note,
change, and preservation cost. `music21.clef.bestClef` may supply a transparent
per-span candidate or cross-check, but its average-pitch decision is not the
final policy because it has no sequence-wide change penalty.

The manifest records:

- baseline and derived ledger-line cost;
- maximum ledger lines required by one notehead;
- noteheads requiring at least two and at least three ledger lines;
- selected clef spans;
- number of inserted clef changes; and
- any unresolved readability warning.

Publish the derived variant only when it preserves semantic invariants and
does not increase ledger-line cost. If the result still exceeds a versioned
review threshold, retain it with `needs_review` rather than presenting it as
unconditionally repaired.

### Ordering

Clef optimization runs after any enharmonic respelling. Enharmonic notes share
a sounding pitch but can occupy adjacent diatonic staff positions, so using
the final spelling is required for an exact ledger-line calculation.

## Enharmonic Key Variant

### Meaning

The action is a notation respelling, not transposition:

- sounding and MIDI pitches do not change;
- score time, duration, part, voice, stem, and ties do not change; and
- the target key signature and every affected note spelling change together.

Changing only MusicXML `<fifths>` is invalid because MusicXML notes retain
explicit step and alteration values. The transform operates on `music21`
pitch objects and serializes a complete new score variant.

### First eligibility rule

Offer the action when all parts share one ordinary global key signature and
an equivalent conventional signature exists within seven flats or sharps.
For a signature with `f` fifths, the first supported alternative has
`f + 12` or `f - 12` fifths when that result is in `[-7, 7]`.

This covers the ordinary pairs:

- seven flats and five sharps;
- six flats and six sharps; and
- five flats and seven sharps.

The BWV 853 variant therefore maps six flats to six sharps while preserving
pitch. The interface should label both signature names when mode is unknown,
for example **Six sharps — F-sharp major / D-sharp minor**. An explicitly
chosen mode may be retained as variant metadata without claiming the model
inferred it.

Disable the first action with a clear explanation for:

- local or conflicting key-signature changes;
- nontraditional key signatures;
- a requested unrelated key that would be a transposition rather than an
  enharmonic respelling; or
- a result requiring an unsupported accidental representation.

### Spelling algorithm and invariants

Shift the diatonic letter name in the direction implied by the enharmonic
signature pair, then calculate the alteration required to preserve the exact
sounding pitch. Apply the same result to all tied segments of one note.

After respelling:

- every pitched element has the same MIDI pitch as the baseline;
- the new signature is present at equivalent score positions in every part;
- tied segments have consistent spelling;
- accidental display state is recalculated in the target key context;
- no unsupported accidental is introduced silently; and
- round-tripping through MusicXML preserves pitch, ID, timing, part, and
  voice.

Do not use `Pitch.getEnharmonic()` blindly per note. An isolated shortest-name
choice can conflict with target-key context and voice-leading. The first
algorithm is intentionally a deterministic transformation between equivalent
global signatures; general contextual pitch spelling remains separate work.

## Application And UI Boundary

The framework-independent score service owns variant generation. The local
HTTP adapter remains thin.

Add a versioned variant request that names:

- exact baseline score artifact ID;
- exact baseline alignment artifact ID;
- target key signature, if requested;
- clef policy (`automatic` in the first slice); and
- idempotent request ID.

The operation may use the existing score-job coordinator, but it must be
distinguishable from full model inference and must never rerun the transformer.
It invokes the isolated semantic-score adapter, publishes a new artifact set,
and returns the exact resulting variant ID.

The score card:

- renders the automatic clef-cleaned variant by default after successful
  generation;
- shows a concise warning when cleanup remains `needs_review`;
- offers the enharmonic alternative only when eligible;
- switches back to the baseline or prior variant without recomputation;
- makes the baseline available as a diagnostic download; and
- never labels an enharmonic respelling as transposition.

Tactical 020's reader pins the selected variant artifact. Creating or selecting
another variant while the reader is open uses its existing **Newer score
available** behavior rather than replacing the displayed score.

## Implementation Slices

### 1. Baseline and variant foundation

- Extract a score-postprocessor boundary from
  `midi2score_adapter.py` after upstream `postprocess_score`.
- Assign stable final note IDs before copying the baseline.
- Serialize and retain a baseline MusicXML and alignment.
- Define the versioned options, manifest, variant hash, and compatibility
  behavior for existing snapshot layouts.
- Add structural invariants that compare baseline and derived `music21`
  scores before serialization.

### 2. Clef-cost engine

- Implement semantic staff-position and ledger-line cost for treble and bass.
- Add measure-level dynamic programming with versioned change and preservation
  penalties.
- Insert selected clefs without changing notes, parts, voices, stems, rests,
  beams, or ties.
- Record before/after readability evidence and `needs_review`.
- Unit-test high, low, crossing, chordal, empty-measure, and tied-note cases.

### 3. Enharmonic variants

- Implement the `f ± 12` eligibility and target naming.
- Transform signatures and pitch spelling together.
- Recalculate accidentals and reject unsupported results.
- Prove pitch, timing, voice, part, tie, and ID invariance after MusicXML
  round-trip.
- Make identical baseline/options requests idempotent.

### 4. Application contract and UI

- Add session-addressed score-variant job contracts and generated client
  types.
- Publish baseline, default automatic, and requested enharmonic artifacts with
  explicit provenance.
- Add the conditional **Enharmonic key** action and variant selection to the
  shared score card.
- Preserve exact reader pinning, playback cursor alignment, historical
  sessions, deletion rules, and stale-job rejection.
- Keep transform failures local to the requested variant.

### 5. Real-session and regression evidence

- Run the retained BWV 853 session through the actual pipeline.
- Render baseline, automatic, and six-sharp variants through the same pinned
  OSMD version and viewport.
- Inspect the resulting MusicXML independently in MuseScore when available;
  MuseScore is validation evidence, not a runtime dependency.
- Exercise the generated musical fixture and prior readable reference take to
  detect clef over-correction.
- Run focused Python and frontend tests, contract generation, production
  build, and the complete migration regression.

## Automated Acceptance

- A new score snapshot retains an immutable baseline MusicXML and alignment.
- The automatic variant is a deterministic function of baseline hash,
  post-processor version, and normalized options.
- Repeating a variant request returns the same variant identity and bytes.
- Clef cleanup changes only clef semantics and variant provenance.
- Automatic cleanup never increases total ledger-line cost.
- Empty measures, ties, chords, and silent parts do not produce clef flicker.
- Failed cleanup leaves the baseline valid and available.
- An enharmonic variant changes signature and spelling but preserves every
  MIDI pitch, score onset, duration, part, voice, tie, and note ID.
- Alignment validation succeeds independently against every variant's exact
  MusicXML hash.
- Unrelated-key, local-key-change, and unsupported-accidental requests fail
  explicitly rather than masquerading as enharmonic transforms.
- Variant generation does not invoke MIDI2ScoreTransformer.
- Selecting a new variant does not mutate a score already pinned in reader
  mode.
- Existing baseline-only snapshots remain readable and downloadable.
- Missing runtime or variant failure does not affect capture, transcription,
  MIDI export, piano roll, keyboard, or prior scores.

## Retained-Session Acceptance

For session `20260726T142937-d49ef33ca321`:

- the baseline remains byte-identical and records six flats and 3/4;
- the automatic variant uses treble clef for the sustained high opening of the
  lower part and returns to bass clef for the later sustained low passage;
- the chosen sequence materially reduces ledger-line cost without
  measure-by-measure clef flicker;
- the six-sharp variant contains the corresponding D-sharp-minor spelling,
  including D-sharp, A-sharp, and B in the opening subject;
- all 281 pitched MusicXML elements retain their sounding pitches;
- all source alignment rows remain valid against the selected variant;
- OSMD renders every variant without clipping or horizontal page overflow;
  and
- the incorrect 3/4 inference remains unchanged and visible, proving this
  tactical did not silently broaden into meter correction.

## Manual Review

Review the retained score at a readable desktop width and in Tactical 020's
phone or tablet reader:

- compare the opening subject before and after clef cleanup;
- confirm later low notes did not merely acquire excessive ledger lines below
  a permanent treble clef;
- confirm clef changes occur at visually comprehensible boundaries;
- switch between six-flat and six-sharp variants and sight-read both;
- play or seek through the score and confirm cursor alignment remains stable;
  and
- download each exact MusicXML artifact and confirm its identity and label.

Record the chosen clef-cost constants, before/after metrics, variant hashes,
render screenshots, OSMD version, viewport, and subjective result.

## Explicit Exclusions

- No model retraining, fine-tuning, or checkpoint change.
- No automatic meter, tempo, beat, downbeat, pickup, quantization, hand,
  staff, or voice correction.
- No note movement between parts or staves.
- No manual note, stem, voice, beam, tie, rest, or staff editor.
- No arbitrary transposition or general-purpose contextual pitch speller.
- No local-key or modulation editor in the first slice.
- No mid-measure clef changes in the first slice.
- No renderer replacement or pixel-level layout manipulation.
- No mutation of historical baseline or pinned score artifacts.
- No requirement to embed or automate MuseScore.
- No public distribution or hosted operation of MIDI2ScoreTransformer.

## Rollback

The baseline score remains the complete pre-atpiano semantic result. Removing
the default variant pointer, postprocessor invocation, and enharmonic action
restores the existing baseline-only workflow without rerunning inference or
changing recordings, committed MIDI, source events, historical scores, or
alignment evidence.

## Execution Record

No implementation commits yet.
