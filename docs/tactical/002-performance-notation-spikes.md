# Integrated Performance Notation Experiment

Topic: performance-to-notation

Status: complete.

## Objective

Make the first notation experiment usable in the existing browser workbench:

1. convert every completed atpiano prediction into an inspectable score;
2. keep every score note traceable to the detected performance event;
3. expose uncertain tempo, beat, meter, key, quantization, and hand decisions;
4. render the score beside the source piano roll; and
5. compare it with a paid piano service given first the original WAV and then
   the atpiano prediction MIDI.

The two oracle inputs separate the service's capabilities:

- **WAV → score** measures its complete acoustic-transcription and notation
  stack; and
- **atpiano MIDI → score** holds the detected pitches and performance timing
  constant, isolating its beat, rhythm, hand, voice, and engraving decisions.

## Bounds

Included:

- Partitura 1.9.0 as the first transparent analysis and conversion baseline;
- versioned hypotheses, selected options, source mapping, and MusicXML;
- a comfortable-tempo heuristic, ranked key profiles, explicit 4/4 meter
  default, quantization choices, and configurable hand split;
- brace-grouped right- and left-hand parts;
- heuristic upward/downward rolled-chord detection and MusicXML arpeggiate
  marks;
- OpenSheetMusicDisplay 1.9.9 in the existing local workbench;
- editable score controls and a beat-grid overlay on the piano roll;
- a manual, consentful Ivory WAV/MIDI workflow;
- durable import and rendering of both unedited Ivory MusicXML results; and
- compact structural summaries for local and oracle scores.

Excluded:

- automatic upload to any third party;
- user account, payment, or credential handling;
- a full notation editor;
- claiming the inferred meter or beat phase is correct;
- acoustic pedal inference;
- automatic semantic alignment between two MusicXML scores;
- phone, LAN, or public serving;
- Verovio and MuseScore renderer output in this first integrated view; and
- a learned performance-to-score model.

## Decisions

### Separate source, hypotheses, and score

The detected note events remain authoritative performance evidence. A notation
variant records:

- the exact `prediction.json` hash;
- ranked key and tempo evidence;
- selected tempo, meter, first beat, key, quantization, and hand split;
- original onset, offset, velocity, and event identity for every note;
- quantized onset/duration and timing residual;
- generated MusicXML note identity, hand, and arpeggio group; and
- converter version, warnings, MusicXML hash, and structural summary.

Changing a control creates a hash-addressed variant. Earlier variants remain
under the ignored run directory, while `notation/current.json` selects the
one shown in the browser.

### Honest initial structure inference

Partitura key estimation and a duration/velocity-weighted Krumhansl profile
provide key evidence. `pretty_midi` supplies an onset-derived tempo estimate;
the default normalizes tempo octaves into a conservative 55–140 BPM band while
preserving the raw estimate and alternatives.

Meter inference is not trusted. The first score says explicitly that 4/4 is a
manual default. Partitura's experimental time estimate is retained as
diagnostic evidence but is rejected when it proposes an unsupported or
implausible meter. The first detected onset is the default first beat; pickup
is not inferred.

The browser makes all of these assumptions visible and editable. The selected
beat grid is drawn over the original, unquantized piano roll.

### Partitura conversion boundary

Partitura produces separate right- and left-hand parts grouped with a piano
brace. This is not yet a single MusicXML piano part with two staves. Its voice
separation, spelling, measure construction, ties, and tuplet sanitization are
used without hiding converter warnings.

The result is serialized as MusicXML with a 4.0 version marker and
well-formedness checked before it is exposed. This is a compatible first
interchange artifact, not evidence of exhaustive MusicXML 4 schema coverage.

### Browser renderer

Use
[OpenSheetMusicDisplay 1.9.9](https://github.com/opensheetmusicdisplay/opensheetmusicdisplay)
for the first interactive renderer. The exact minified bundle URL and SHA-384
subresource integrity value are pinned in the page. OSMD remains an artifact
consumer; it does not own conversion or source data.

This avoids adding a JavaScript build system to the small Python prototype.
It does mean score rendering needs internet access to load the pinned bundle.
MusicXML download and all server-side artifacts remain available without it.

### Paid oracle

Use [Ivory](https://ivory-app.com/) for the first black-box oracle because its
official site accepts solo-piano WAV and standard MIDI up to 15 MB, exports
MusicXML, and advertises smart quantization and hand separation. Pricing
reviewed on 2026-07-24 lists a free 30-second preview and paid full-length
exports.

The workbench never uploads automatically. It provides exact download links,
opens Ivory in another tab, and accepts the two unedited MusicXML exports back
into the local run. Each import records lane, original filename, time, hash,
service, review date, and structural summary. Hash-addressed prior imports are
not deleted.

This boundary avoids silently disclosing a recording, accepting changing terms
on the user's behalf, storing credentials, or coupling the reproducible local
pipeline to an undocumented web API.

## Execution Record

### Local artifacts

The offline adapter now creates notation after its unchanged Basic Pitch MIDI
result. New runs list:

```text
notation/current.json
notation/notation-<options-hash>.json
notation/atpiano-<options-hash>.musicxml
```

Older completed workbench runs are upgraded lazily when their notation API is
first requested. This made the existing target-piano take immediately usable
without rerunning the model.

The workbench adds:

- local notation manifest retrieval and option regeneration;
- two bounded MusicXML import endpoints for the oracle lanes;
- retained imported artifacts under `oracle/`;
- local and oracle score summaries;
- side-by-side OSMD rendering;
- WAV/MIDI download links and the manual Ivory instructions; and
- ordinary handling of browser connection resets during artifact delivery.

The notation consumer remains distinct from acoustic inference: it reads
normalized prediction artifacts and would accept the same note representation
from direct MIDI in a later source adapter.

### Target-piano result

The previously recorded 34.688-second target-piano take generated:

```text
source prediction notes: 133
selected key: A major
key-profile correlation: 0.906
raw onset tempo estimate: 165.621 BPM
selected half-time tempo: 82.811 BPM
selected meter: 4/4 (explicit default)
first beat: 1.729545 s
quantization: sixteenth note
hand split: MIDI 60
score parts: 2
score measures: 11
MusicXML pitched note elements: 161
arpeggiate marks: 9
```

The MusicXML note-element count exceeds the 133 source notes because Partitura
splits notes at measure or notation boundaries and joins them with ties. The
source mapping remains one row per detected note.

Partitura's separate time estimator proposed 191.505 BPM and a numerator of
24. That result is retained as evidence and rejected for the default score. It
reinforces the need for visible controls and human review.

### Real model-path validation

The exact target WAV was run again through the complete adapter after notation
integration:

```text
input SHA-256:
3d747d653d8f7a30c2e3261c85b8b9207959a7e00e8b009aac5fd969247f6f47
prediction MIDI SHA-256:
a106b4d82b0237186c86d6fa228370495db1d027a668d4ae1984898966712e03
Basic Pitch inference: 0.522 s
complete audio-to-notation artifacts: 1.192 s
```

The prediction hash exactly matches the earlier workbench result, establishing
that notation generation did not change acoustic inference.

## Validation

Commands:

```text
uv run ruff check .
uv run pytest -q
node --check src/atpiano/web/app.js
uv build
git diff --check
xmllint --noout <generated MusicXML>
```

Results:

- 17 unit and HTTP integration tests passed;
- notation options produced distinct retained variants;
- source identities survived conversion;
- rolled-chord fixtures produced semantic arpeggiate marks;
- unrelated or malformed XML was rejected;
- both oracle lanes persisted independently;
- traversal, size, content-type, and local-host boundaries remained enforced;
- cancelled response bodies stopped without a traceback;
- the real target-piano model and notation path completed;
- generated MusicXML was well formed; and
- lint, browser syntax, package contents, build, and diff checks passed.

## Known Gaps

- The user has not yet supplied the two Ivory MusicXML exports, so the oracle
  side correctly remains an empty, guided comparison lane.
- Key is only a global hypothesis; modulation is not inferred.
- Meter, downbeat, pickup, swing, and triplet feel require manual review.
- Moving the first beat later than early notes currently clamps those notes to
  score time zero rather than producing a true pickup measure.
- Hand separation is a configurable pitch threshold, not a fingering model.
- Partitura may produce more voices and tied note elements than an engraver
  would choose manually.
- Rolled-chord recognition is a transparent onset/order/overlap heuristic and
  can confuse fast melodic motion.
- Basic Pitch provides no pedal events, so the score cannot yet show credible
  pedal marks.
- OSMD is loaded from a pinned CDN. A later production consumer should vendor
  or bundle the renderer.
- The current comparison reports structural counts and presents the scores to
  the user; it does not yet align oracle measures or score notes
  automatically.
- Verovio, MuseScore, music21, and learned MIDI-to-score conversion remain
  comparators only if the first subjective result exposes a concrete need.

## Recommended Next Work

1. Review the local A-major, 82.811-BPM, 4/4 score against playback.
2. Adjust tempo, first beat, meter, grid, key, or hand split until the local
   interpretation is coherent.
3. Upload the original WAV to Ivory and import its first unedited MusicXML.
4. Upload the atpiano prediction MIDI as a separate Ivory job and import that
   first unedited MusicXML.
5. Record which errors remain in all three lanes before adding another
   renderer, converter, or learned model.

The next implementation should be driven by that comparison. Likely branches
are better beat/downbeat estimation, better hand/voice assignment, or a
semantic MusicXML alignment report; renderer work should wait unless the same
MusicXML demonstrably renders better elsewhere.
