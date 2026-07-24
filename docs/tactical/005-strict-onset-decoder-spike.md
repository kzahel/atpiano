# Strict-Onset Decoder Spike

Topic: live-acoustic-transcription

Status: complete on 2026-07-24.

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

## Implemented Decision

The live rolling adapter now uses `strict-onset-0.6`:

```text
onset threshold:       0.6
frame threshold:       0.3
minimum note length:   127.7 ms
infer_onsets:          false
melodia_trick:         false
```

The untouched full-file/final adapter still uses Spotify Basic Pitch's stock
decoder. This deliberately creates two named lanes: a conservative
onset-first live preview and the original best-available final transcript.

The reusable decoder records the native onset confidence, decoder confidence,
frame confidence, frame bounds, and one of `explicit_onset`,
`inferred_onset`, or `melodia_fallback` for every candidate. Rolling gate
decisions retain that evidence, and the live manifest records the complete
decoder policy.

## Retained-Output Results

The machine-readable study is generated outside Git at
`results/decoder-study-strict-onset/decoder-study.json`. Its SHA-256 for this
execution is:

```text
f244e5ca1fc8c9e7dc5e9f734f695f074264cde008ca78626ffb3c3c933fcbec
```

The full sweep is in the adjacent generated `report.md`. The selection-driving
rows are:

| Case | Stock notes / restarts <1s | Strict 0.6 notes / restarts <1s | 25 ms onset F1 |
|---|---:|---:|---:|
| 19-note fixture | 23 / 2 | 19 / 1 | 1.000 |
| Earlier useful take | 133 / 37 | 81 / 15 | unscored |
| Held-chord A | 214 / 62 | 149 / 38 | unscored |
| Held-chord B | 137 / 38 | 52 / 10 | unscored |

Thresholds 0.6 and 0.7 both recover all 19 fixture onsets with no extras.
Threshold 0.8 misses one fixture onset. The lower 0.6 value is selected to
avoid deleting more unaligned target-piano notes than the aligned evidence
justifies.

The strict decoder retains both fixture E4 attacks 450 ms apart and its dense
chords, octaves, and fifths. This rejects a long refractory period and a
harmonic-interval filter.

## Reattack And Attack-Novelty Decision

No separate same-pitch active-note or reattack policy is selected. Inspection
of several apparent repeated pitches in the held-chord recordings found
strong source-audio attacks at each start, so the retained examples do not
cleanly identify them as false re-onsets. A fixed refractory would delete the
known repeated E4 fixture attacks.

The measured source novelty compares RMS from -180 through -30 ms with RMS
from -20 through +100 ms. A 3 dB requirement preserves all 19 fixture notes,
but retains only 58 of 81 strict-decoded notes in the earlier take. Without
aligned acoustic truth, that 23-note removal is too aggressive to integrate.
Source novelty remains recorded evidence, not a live gate.

This is intentionally conservative: fewer candidates from the strict decoder
are justified; declaring every remaining held-chord response false is not.

## Rolling Real-Model Validation

The selected decoder was replayed through the actual rolling Core ML path, not
only against full-file arrays.

The 34.688-second target take processed 132 windows and produced 83 committed
live identities. The full-file strict decoder produces 81 notes. The prior
stock rolling run produced 140 committed identities, so the selected live lane
is materially less busy while remaining close to its full-file strict
counterpart. This accelerated validation makes no latency claim.

The aligned fixture processed 42 rolling windows and produced 19 committed
identities. It matched 18 of 19 reference onsets at 25 and 50 ms. The missing
note begins at 0.5 seconds and was intentionally suppressed by the live
one-second room-calibration policy; the unmatched estimate is the known
pitch-76 fixture false positive. After excluding the calibration-period
reference, recall is 1.000, precision is 0.947, and F1 is 0.973.

Generated validation artifacts are outside Git:

```text
results/live-strict-onset-validation/validation.json
SHA-256 dee44fa274de39c558f90d885d1497e861b9e86eacf413681eee511a53d4c21f

results/live-strict-onset-fixture-validation/validation.json
SHA-256 45427df04d27df7914eec5f7f9d71b6d6726ce2c0ede4a95092032a3b542d535
```

## Commands

```bash
uv run atpiano decoder-study \
  results/decoder-study-strict-onset \
  fixture=results/offline-final-validation \
  target=results/workbench/20260724T104057-1c108a0915e3/run-20260724T104057-1c108a0915e3 \
  held-a=results/workbench/20260724T140255-dd5a880a8d60/run-20260724T140255-dd5a880a8d60 \
  held-b=results/workbench/20260724T140555-b5d3ffa2e2f3/run-20260724T140555-b5d3ffa2e2f3

uv run pytest
uv run ruff check .
node --check src/atpiano/web/app.js
uv build
git diff --check
```

The rolling validations used `BasicPitchLiveModel` and
`LiveRecognitionProcessor` directly with accelerated, contiguous PCM blocks.
Their generated manifests explicitly mark latency invalid because source
cadence was not wall-clock paced.

## Validation

- synthetic arrays exercise explicit, inferred, and melodia candidate origin;
- the selected policy and candidate evidence are covered at the live-adapter
  boundary;
- the aligned fixture protects repeated strikes and polyphony;
- retained native outputs reproduce the threshold sweep without inference;
- the actual rolling Core ML path was exercised on the fixture and target
  take;
- WebSocket, capture, gate, final-backfill, and decoder regressions pass;
- lint, all tests, JavaScript syntax, package build, and whitespace checks
  pass; and
- exact final transcription remains on its unchanged reference adapter.

## Gaps And Recommended Next Work

The selected policy is ready for another subjective held-chord pass. It is not
yet an accuracy claim for the acoustic piano. The next useful evidence is a
short controlled local recording containing:

1. room silence;
2. isolated soft and loud notes;
3. one chord held without restrikes;
4. repeated same-pitch strikes around 250, 450, and 800 ms apart;
5. real octaves and fifths;
6. low bass and high treble; and
7. the same gestures with sustain pedal.

If strict 0.6 still creates obvious new onsets during the held-only segment,
do not add more ungrounded decoder heuristics. Annotate the controlled clip
and open the piano-specific/onset-specific model bakeoff behind the existing
adapter contract.
