# Performance To Notation

Topic: performance-to-notation

Status: integrated prototype. Partitura produces traceable MusicXML,
OpenSheetMusicDisplay renders it in the local workbench, and a manual
two-input Ivory comparison is ready for user review. These are experimental
choices, not a permanent consumer stack.

## Scope And Boundary

This topic owns conversion of timestamped piano notes into readable common
music notation:

- beat, downbeat, tempo, pickup, and meter hypotheses;
- key signature, local key, and enharmonic spelling;
- quantization, rests, ties, tuplets, staff, hand, and voice assignment;
- recognition of score-level gestures such as rolled chords and grace notes;
- sustain-pedal notation when the input supplies credible pedal events;
- an inspectable notation interchange artifact; and
- browser rendering and comparison of alternative interpretations.

This belongs to the separate visualization and analysis consumer described in
the project boundary, not to the atpiano acoustic-transcription service. The
consumer must accept both normalized atpiano events and direct MIDI. Direct
MIDI must not pass through an acoustic model.

The source performance remains authoritative. A score is one editable,
versioned interpretation of it, not a replacement for the source note times.

## Product Question

Can a pianist get a score that is pleasant enough to read, while still being
able to see and correct uncertain musical assumptions rather than receiving
opaque, falsely precise notation?

Rendering conventional notation glyphs is a mature problem. Inferring the
musical structure that chooses those glyphs is the difficult problem. A useful
system must therefore keep these stages distinct:

```text
performance notes and pedal
          |
          v
tempo / beat / downbeat hypotheses
          |
          v
meter and key segments
          |
          v
quantization and staff / voice assignment
          |
          v
spelling, ties, tuplets, gestures, pedal
          |
          v
MusicXML score + source-event mapping
          |
          v
browser renderer
```

Each inferred layer should record the algorithm and parameters used,
confidence or alternatives where meaningful, and any user override. Every
score note should map back to one or more source note-event identities.

## Interchange And Glyph Decision

Use [MusicXML 4.0](https://www.w3.org/2021/06/musicxml40/) as the first
canonical score artifact. It is a widely supported open interchange format,
can be inspected independently of the browser, and can be opened in full
notation editors such as MuseScore.

Do not make the converter choose raw font glyphs. It should express musical
semantics. For example, a short upward roll that belongs to one chord becomes
MusicXML's
[`<arpeggiate direction="up">`](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/arpeggiate/).
The renderer then selects the wavy-line glyph and lays it out. MusicXML can
also name a [SMuFL glyph on otherwise unsupported
notations](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/other-notation/),
but that is an escape hatch, not the normal representation.

[SMuFL 1.4](https://www.w3.org/2021/03/smufl14/) standardizes music-font
glyph names and code points. It solves interoperability between notation
fonts; it does not decide whether the performance contained an arpeggio,
trill, grace note, or ordinary asynchronous chord.

Keep source time in seconds or samples beside score time in divisions and
beats. Quantization must never destroy the timings needed for playback,
comparison, or a later reinterpretation.

## Current Prototype

[`002-performance-notation-spikes.md`](../tactical/002-performance-notation-spikes.md)
is the completed execution record. Every completed offline prediction now
produces a versioned notation manifest and MusicXML. Existing workbench runs
are upgraded lazily when first opened.

The manifest records the exact prediction hash, hypotheses, user selections,
source timing, quantized timing, source-to-score identity mapping, converter
version, warnings, and MusicXML hash. Regenerating with different controls
retains a hash-addressed variant instead of overwriting the earlier
interpretation.

The browser displays:

- ranked key and tempo evidence;
- editable tempo, meter, first beat, key, grid, and hand split;
- the selected beat grid against the unquantized piano roll;
- a two-hand rendered score and MusicXML download; and
- two independent hosted-oracle score lanes.

Partitura 1.9.0 is the first transparent Python converter.
OpenSheetMusicDisplay 1.9.9 is the first browser renderer, loaded from a
pinned CDN URL with subresource integrity. The converter and renderer are
replaceable artifact consumers, not permanent product commitments.

### Two-phase paid oracle

The first black-box comparison uses [Ivory](https://ivory-app.com/). The user
runs two separate jobs:

1. original WAV to MusicXML, which tests Ivory's complete acoustic and score
   pipeline; and
2. atpiano prediction MIDI to MusicXML, which holds detected notes and
   performance timing fixed and tests its notation decisions.

The workbench provides exact WAV and MIDI downloads, opens Ivory in another
tab, and imports each unedited MusicXML result into its own lane. It never
uploads a recording automatically or handles an account, payment, or
credential. Each import records its lane, filename, time, hash, service, and
structural summary and retains older hash-addressed imports.

Ivory was selected because its official site currently accepts solo-piano WAV
and standard MIDI, exports MusicXML, and advertises quantization and hand
separation. Its price and interface are external facts and must be reviewed
again before treating it as a durable dependency. It is an oracle for
comparison, not a service dependency.

## Renderer Options

Research reviewed on 2026-07-24:

| Candidate | Strength | Important limit | Proposed role |
|---|---|---|---|
| [OpenSheetMusicDisplay](https://github.com/opensheetmusicdisplay/opensheetmusicdisplay) | Turnkey browser MusicXML renderer, TypeScript, SVG, BSD-3-Clause, and useful note coloring | It is a renderer rather than an editor; some advanced pedal and cross-staff notation is limited | Leading interactive debug-UI candidate |
| [Verovio](https://github.com/rism-digital/verovio) | Mature C++/WebAssembly/JavaScript engraver, SVG output, MusicXML import, SMuFL, LGPL | Its native data model is MEI, so MusicXML is converted on import and parity must be tested | Leading engraving and renderer comparison |
| [VexFlow](https://github.com/0xfe/vexflow) | Flexible lower-level browser notation primitives | The application must create and position measures and symbols itself | Defer unless custom editing needs justify the layout work |
| [MuseScore](https://github.com/musescore/MuseScore) | Full GPL score editor with mature MIDI import and MusicXML/PDF/SVG workflows | Too large and copyleft to embed casually; command-line behavior needs version-specific verification | External reference/oracle and manual correction tool |

OSMD was selected for the first integrated experiment because it renders
MusicXML directly in the existing browser without adding a JavaScript build
system. Verovio remains the next renderer comparator only if the same
MusicXML demonstrates a concrete engraving or interaction problem. MuseScore
remains a useful independent editor and visual reference.

## Performance-To-Score Options

No single current library cleanly solves expressive piano performance to
publishable notation. The promising lanes have different roles:

| Candidate | What it supplies | Constraint | Proposed role |
|---|---|---|---|
| [MuseScore MIDI import](https://github.com/musescore/MuseScore/tree/deprecated_master/src/importexport/midi/internal/midiimport) | Mature beat, meter, quantization, tuplet, swing, voice, clef, key, and hand heuristics | Primarily an application workflow, and the linked source layout is from its deprecated branch | Practical quality reference |
| [Partitura](https://github.com/CPJKU/partitura) | Apache-2.0 Python score/performance representation, MusicXML/MIDI/MEI I/O, spelling, key, voice separation, and note-array-to-score utilities | Its current `estimate_time` path inserts a default 4/4 rather than inferring meter | Leading transparent Python baseline |
| [music21](https://www.music21.org/music21docs/) | Broad symbolic analysis, several key algorithms, MIDI quantization, and MusicXML export | Its documented `bestTimeSignature` fits already quantized durations and does not solve performance-meter inference | Cross-check and analysis toolbox |
| [MIDI2ScoreTransformer](https://github.com/TimFelixBeyer/MIDI2ScoreTransformer) | Recent end-to-end piano performance-MIDI-to-score research with a released checkpoint | Custom forks, MuseScore, data preparation, and an unconfirmed repository license make reuse risky | Isolated research bakeoff only |
| Audio beat tools such as [madmom](https://github.com/CPJKU/madmom) | Additional onset, beat, and downbeat evidence from the recording | Old runtime; shipped model weights have non-commercial terms; direct MIDI has no audio | Optional comparator, never a required path |

The score consumer should work from symbolic notes first. Audio-assisted beat
evidence can be compared when acoustic input is available, but it cannot be
required because the same consumer must support direct MIDI.

## Structure Inference

### Tempo, beat, and meter

Tempo estimation alone is insufficient. Expressive timing creates tempo
octave ambiguities, while a time signature additionally needs downbeat,
accent, phrase, and grouping evidence. A pickup can shift every later bar if
the first downbeat is guessed incorrectly.

Maintain ranked hypotheses such as:

- tempo curve or piecewise-stable tempo;
- beat phase and downbeat phase;
- simple versus compound subdivision;
- time-signature segments; and
- pickup duration.

The UI should expose tempo, time signature, first downbeat, pickup, swing, and
triplet overrides. It should show the proposed grid against the original
piano roll before committing to notation.

### Key and pitch spelling

A pitch-class profile is a useful candidate generator, not a sufficient score
speller. Rank global and local key candidates, then use melodic and harmonic
context to choose enharmonic spellings. Keep confidence and runner-up keys,
and allow key changes and a user override.

### Quantization, hands, and voices

Quantization should minimize both timing residuals and notation complexity.
The latter includes excessive ties, rests, tuplets, voice crossings, and short
values. Hand/staff separation and voice assignment are related but distinct:
two simultaneous voices may belong to one hand, and hands can cross.

The first transparent baseline should compare:

- a simple beat-grid dynamic program with an explicit complexity cost;
- Partitura's spelling and voice tools;
- music21's default MIDI quantization; and
- MuseScore's imported result as a pragmatic reference.

### Rolled chords and other gestures

Do not label every fast run as an arpeggio. A rolled-chord candidate should
start from a near-coincident note cluster and consider:

- nonzero onset spread rather than exact simultaneity;
- mostly monotonic pitch order and roll direction;
- shared harmonic role and substantial note overlap;
- common or pedal-supported release behavior; and
- the size of the cluster relative to the local beat.

Grace notes, trills, ornaments, and melodic arpeggios need separate
classifiers. The score should retain the source onset residuals even after a
cluster is represented as one notated chord with an arpeggiate mark.

## First Target-Piano Evidence

The first real workbench take is documented in
[`acoustic-transcription-latency-quality.md`](acoustic-transcription-latency-quality.md).
Its Basic Pitch output is a useful unscored renderer fixture: 133 notes over
34.688 seconds, with pitch 45 through 76.

A duration-and-velocity-weighted pitch-class profile ranked A major first with
correlation 0.906. `pretty_midi` estimated 165.621 BPM; the prototype selected
its half-time interpretation, 82.811 BPM. Partitura's independent time
estimator proposed 191.505 BPM with numerator 24, which the prototype retained
as diagnostic evidence and rejected.

The generated score uses A major, 82.811 BPM, an explicit 4/4 default, a first
beat at the first onset, sixteenth-note quantization, and a middle-C hand
split. Its 133 source notes became 161 pitched MusicXML note elements across
two parts and 11 measures because notes split across notation boundaries are
tied. Nine transparent rolled-chord candidates received arpeggiate marks.
Every source note retains its original timing and mapping.

The take has no reference score or MIDI. It can support subjective readability
review, not key, beat, meter, or transcription-accuracy claims. The two Ivory
results have not yet been supplied, so the comparison lanes correctly remain
empty and guided.

## Recommended Direction

The next step is human comparison, not another converter:

1. listen to the target take while reviewing the piano roll and local score;
2. adjust the visible tempo, first beat, meter, grid, key, and split until the
   interpretation is coherent;
3. import Ivory's unedited WAV result into the audio lane;
4. import its unedited atpiano-MIDI result into the MIDI lane; and
5. identify errors shared by all lanes versus errors introduced by acoustic
   detection or local notation.

That evidence should select the next bounded slice. Likely candidates are
better beat/downbeat and pickup inference, improved hand/voice assignment, or
semantic alignment of the three MusicXML results. Compare Verovio, MuseScore,
music21, or MIDI2ScoreTransformer only for a concrete observed gap.

## Evidence To Require

- MusicXML validates and opens independently in MuseScore.
- Every score note can be traced to source event identities and original time.
- Alternative renderer output is compared on the same MusicXML bytes.
- Beat/downbeat, meter, key, staff, voice, and quantization are scored
  separately where references exist.
- Readability review includes ties, tuplets, rests, hand crossings, rolled
  chords, pickups, rubato, repeated notes, dense chords, and pedal.
- Dataset, checkpoint, score, MIDI, and generated artifacts remain outside Git
  with source, license, version, and hash recorded.

## Known Gaps And Open Questions

- Is the first goal a quick readable lead sheet, a faithful piano grand staff,
  or an editable draft for MuseScore?
- Should the UI eventually require explicit meter/downbeat confirmation
  instead of generating immediately from its visible 4/4 default?
- Does the first imported score expose an engraving gap that warrants a
  Verovio comparison?
- How much voice and hand correction is acceptable before automatic output
  stops feeling useful?
- Should pedal first appear as conventional Ped./* markings, brackets, or only
  as a piano-roll overlay until pedal inference improves?
- How should a first beat later than the earliest note become a true pickup
  instead of clamping early notes to score time zero?
- Should the next comparison align measures and source notes automatically,
  or is side-by-side listening sufficient for the first qualitative review?
