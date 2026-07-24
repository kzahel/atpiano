# Strict-Onset Decoder Spike

Topic: live-acoustic-transcription

Status: accepted on 2026-07-24.

## Observation

The onset-only display is legible, but stock Basic Pitch repeatedly emits new
notes while a chord is held. Its decoder admits notes through three paths:

1. peaks from the learned onset head;
2. inferred onsets derived from changes in frame activation; and
3. the melodia fallback, which converts remaining frame energy to notes.

The live volume gate only separates candidates from the room floor. Sustained
piano resonance is loud, so it cannot establish that a new hammer attack
occurred.

## Objective

Determine whether Basic Pitch's explicit onset head plus a small,
sample-indexed reattack policy can provide useful live pitch attacks without
the held-chord note stream. Select and integrate a live policy only after
comparing retained native outputs; leave the stock exact-final adapter
untouched.

## Included

- a reusable Basic Pitch decoder whose policy is recorded explicitly;
- stock, no-melodia, and strict-onset variants;
- an onset-threshold sweep over retained model probabilities;
- explicit onset-head confidence and origin evidence per decoded candidate;
- same-pitch repeated-start and held-chord clutter metrics;
- a source-audio attack-novelty measurement around each candidate;
- a bounded active-note or reattack policy that preserves genuine repeated
  strikes;
- objective scoring on the 19-note deterministic fixture;
- comparison on the earlier target take and both held-chord sessions;
- live adapter integration only for the selected policy; and
- raw decisions and policy parameters in the live manifest.

## Excluded

- modifying the untouched offline/final Basic Pitch reference;
- generic harmonic suppression by interval;
- claiming removed notes are false without aligned reference;
- training or fine-tuning;
- changing the browser transport, clocks, or display;
- introducing another model in this slice; and
- treating synthetic-fixture quality as acoustic-piano ground truth.

## Experiment Matrix

Decode already-retained full-file and rolling probabilities with:

| Variant | Inferred onsets | Melodia fallback |
|---|---|---|
| stock | yes | yes |
| no-melodia | yes | no |
| strict-onset | no | no |

For strict onset, sweep a small declared threshold set centered on the stock
0.5 threshold. Record:

- total notes and pitch distribution;
- onset precision, recall, and F1 at 25 and 50 ms where reference exists;
- same-pitch re-onsets under 250, 500, and 1,000 ms;
- decoded candidates per held second;
- explicit onset-head confidence;
- pre-attack versus post-attack RMS novelty;
- notes retained from the earlier subjectively useful take; and
- live-to-stock-final additions and removals.

Use the deterministic fixture's repeated E4 strikes 450 ms apart to reject a
refractory policy that merely deletes fast legitimate repetition. Its repeated
chord and true octaves/fifths prevent a harmonic-deduplication shortcut.

## Selection Rule

Prefer strict-onset decoding if it materially reduces held-chord clutter while
retaining acceptable deterministic-fixture onset recall. Add a reattack policy
only if retained evidence separates real fixture reattacks from held-resonance
starts. Favor a measured source attack transition over a long fixed refractory
period.

If no Basic Pitch policy meets both conditions, do not tune indefinitely.
Retain the decoder study as the portable baseline and open the piano-specific
or onset-specific model bakeoff.

## Validation

- decoder unit tests with synthetic activation matrices;
- deterministic output and policy provenance tests;
- fixture objective scoring;
- retained target/held-chord analysis with machine-readable results;
- live WebSocket and final-backfill regression tests;
- a real-model replay through the selected policy;
- lint, all tests, JavaScript syntax, package build, and whitespace checks; and
- exact decisions, commands, results, gaps, and next direction recorded here.
