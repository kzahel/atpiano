# Performance Notation Spikes

Topic: performance-to-notation

Status: proposed. Do not implement until the user selects or amends this
slice.

## Objective

Produce a small, reproducible comparison that separates two decisions:

1. which browser renderer best supports an inspectable piano score; and
2. which deterministic performance-to-score baseline produces the most useful
   starting notation.

The output is decision evidence, not a polished editor or a permanent
conversion engine.

## Why This Slice

Sheet-music glyph rendering is mature, but expressive performance MIDI does
not directly specify beats, measures, hands, voices, or readable durations.
Choosing a renderer and a conversion algorithm at once would make it hard to
tell whether a bad-looking result came from musical inference or engraving.

This slice holds MusicXML constant while comparing renderers, then holds the
fixtures and evaluation view constant while comparing converters.

## Included

- a versioned, inspectable score-result manifest;
- source note identities and original timing retained beside score notes;
- a hand-authored MusicXML 4 piano fixture covering the required notation;
- OSMD and Verovio renderings of identical MusicXML;
- MuseScore as an external open/edit/render reference;
- Partitura, music21, and MuseScore MIDI-import conversion baselines;
- explicit tempo, first downbeat, time-signature, pickup, key, subdivision,
  and quantization overrides;
- a compact browser comparison with synchronized playback, source piano roll,
  beat grid, rendered score, and source-note highlighting;
- machine-readable structural metrics where ground truth exists; and
- a short human readability scorecard.

## Excluded

- acoustic transcription changes;
- a full notation editor;
- automatic correction based on user edits;
- training a score model;
- committing datasets, recordings, MIDI corpora, or generated scores;
- treating key, meter, staff, or voice guesses as ground truth;
- audio-required beat tracking; and
- selecting MIDI2ScoreTransformer as a dependency before its license and
  reproducibility are verified.

## Fixtures

Use the smallest fixtures that reveal the real decisions:

1. **Engraving fixture:** hand-authored MusicXML with piano grand staff,
   pickup, key and time changes, chords, upward/downward arpeggiate marks,
   ties, tuplets, grace notes, dynamics, cross-staff notes, and pedal.
2. **Known-score performance fixture:** deterministic score plus direct MIDI
   with controlled rubato, onset spread, duration variation, velocity, and
   CC64. Strip score metadata before conversion while retaining the score as
   evaluation reference.
3. **Existing synthetic fixture:** the current aligned MIDI-derived benchmark
   for a simple repository-adjacent smoke test.
4. **Target-piano prediction:** the unscored 133-note result from workbench job
   `20260724T104057-1c108a0915e3` for subjective realism.
5. **Optional public pairs:** a tiny checksummed expressive-MIDI/score subset
   only after source and license review; ASAP is a candidate, not an
   acquisition decision.

All generated and acquired artifacts remain outside Git. A tracked manifest
or execution record must identify source, version, license, and SHA-256.

## Artifact Contract Spike

Define a result that preserves:

- source input identity and hash;
- converter and parameter identity;
- ranked tempo/beat/meter and key hypotheses;
- explicit user overrides;
- source event identities and original onset/offset time;
- score note, measure, staff, voice, and MusicXML element identity;
- quantization residual for every mapped note;
- unsupported or discarded source events; and
- canonical MusicXML plus renderer-specific output.

Use MusicXML divisions for score time but never discard source seconds or
samples. Validate MusicXML independently and open it in MuseScore before
accepting a result.

## Spike A: Renderer Bakeoff

Render the exact engraving fixture with:

- OpenSheetMusicDisplay;
- Verovio's JavaScript/WebAssembly toolkit; and
- MuseScore to PDF or SVG as a manual/reference rendering.

Compare:

- piano grand-staff layout and pagination;
- arpeggios, pedal, ties, tuplets, grace notes, and cross-staff notation;
- element identities and reliable note coloring;
- playback cursor and source-note selection;
- resize and long-score behavior;
- generated SVG accessibility and inspectability;
- browser bundle and integration cost; and
- visible discrepancies from MusicXML import.

Decision gate: choose OSMD, Verovio, or retain both behind a tiny renderer
interface. Current recommendation is to start OSMD for interactivity but keep
the bakeoff real because its documented pedal and cross-staff limitations
touch piano use directly.

## Spike B: Deterministic Converter Bakeoff

Feed the same known-score performance and metadata-stripped MIDI into:

1. MuseScore MIDI import with recorded import settings;
2. Partitura note-array-to-score plus explicit beat/meter inputs;
3. music21 MIDI import/quantization; and
4. one deliberately small in-project baseline that snaps to an explicit beat
   grid and charges a visible notation-complexity cost.

Do not compare only final page appearance. Preserve intermediate hypotheses
and score:

- beat and downbeat F1;
- tempo-curve error;
- time-signature, pickup, and key-segment accuracy;
- onset and duration grid error;
- pitch-spelling accuracy;
- staff/hand and voice assignment;
- chord versus rolled-chord classification;
- ties, rests, tuplets, and total notational complexity;
- unmapped, merged, and split source events; and
- subjective readability.

Decision gate: select a transparent baseline and identify the errors that
actually justify more sophisticated inference. Partitura is the current
leading Python candidate; MuseScore is the practical quality reference.

## Spike C: Hypothesis And Override UX

Show the source piano roll and rendered score against one playback clock.
Allow the reviewer to switch or override:

- global or segmented tempo;
- beat phase and first downbeat;
- time signature and pickup;
- straight, swing, or triplet subdivision;
- key signature;
- staff split; and
- rolled-chord interpretation.

Changing one hypothesis should regenerate the result without changing source
event identities. Export both the score and the complete hypothesis/override
record.

Decision gate: determine whether explicit corrections make the transparent
baseline useful enough, and which correction costs dominate.

## Optional Spike D: Learned Conversion

Only if Spike B exposes a meaningful readability ceiling:

1. confirm MIDI2ScoreTransformer's code and checkpoint license in writing;
2. isolate its custom music21 and score-transformer forks;
3. record checkpoint and data provenance;
4. run the same fixtures without special-case cleanup; and
5. compare its source traceability and editability as well as page quality.

If licensing, checkpoint provenance, or deterministic setup remains unclear,
record it as unavailable rather than absorbing the implementation.

## Validation

- schema and MusicXML validation tests;
- deterministic regeneration from the same source and parameters;
- browser syntax, unit, and interaction tests;
- identical MusicXML bytes passed to both renderers;
- independent MuseScore open/render check;
- automated metrics on known-score fixtures;
- human scorecard with screenshots or saved SVG/PDF outside Git; and
- `git diff --check`, repository lint, tests, and package build if code is
  later authorized.

## Completion Evidence

This proposed tactical is complete only when its execution record contains:

- exact commands and environment versions;
- fixture sources, licenses, hashes, and generation parameters;
- side-by-side renderer and converter results;
- measured failures and unsupported constructs;
- the user's preference after reviewing the comparison;
- a selected first implementation boundary or an explicit decision to defer;
  and
- a smaller follow-up tactical for the selected path.
