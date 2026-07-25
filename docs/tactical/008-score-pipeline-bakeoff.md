# 008 — Score Pipeline Bakeoff Against The Ivory Oracle

Topic: performance-to-notation

Status: complete. A local cascade produced the first sight-readable score for
the golden-reference take. No component is adopted yet; the leading candidate
has an unresolved license.

## Motivation

The user restated the product goal without ambiguity: legible engraved sheet
music that can be sight read back. Lead sheets, chord approximations, and piano
rolls do not satisfy it. Ivory produced exactly that from the reference WAV,
while the local Partitura converter produced an unreadable tie forest.

The open question was where the gap lives. Two hypotheses were plausible:
weak note detection, or a missing score-inference layer. This slice decomposes
the gap by holding the input fixed and swapping one stage at a time.

The reference pair is now fixed in [`oracle/`](../../oracle/README.md).

## Method

All rows consume the same 34.688-second reference WAV
(`3d747d65…f6f47`). Engravings are rendered by the same MuseScore 4 binary so
the comparison isolates score semantics rather than engraver quality.

| Row | Notes | Score inference |
|---|---|---|
| 1 | Basic Pitch 0.4.0 (existing) | Partitura (existing baseline) |
| 2 | Basic Pitch 0.4.0 | MuseScore 4 MIDI import |
| 3 | Transkun 2.0.1 | MuseScore 4 MIDI import |
| 4 | Transkun 2.0.1 | MuseScore import, given the oracle's tempo and meter |
| 5 | Transkun 2.0.1 | MIDI2ScoreTransformer v0.0.1 |

Artifacts are under the ignored `results/score-bakeoff/` directory.

## Note-detection result

Swapping the acoustic model changes the octave-error rate directly. Both
outputs come from the same WAV:

```text
model         notes  range  dur_med  dur_p95  octave-sync pairs  sub-s restarts  pedal CC
basic-pitch     133  45-76    0.627    1.875                 17              37         0
transkun         80  47-76    1.153    3.632                  2              11        30
```

"Octave-sync pairs" counts note pairs exactly 12 semitones apart whose onsets
fall within 30 ms — the reported failure mode. It falls from 17 to 2. Transkun
also emits 30 sustain-pedal control changes, which the project has never had.

This supports the model-class explanation over decoder tuning. It is one
unaligned take, so it is comparative evidence, not precision or recall. The
proposed inharmonicity/envelope octave veto was not implemented; the user
correctly objected that it is unlikely to survive pedal and dense texture, and
the model swap addresses the same failure without a heuristic.

## Score-inference result

MusicXML structure for the same reference take:

```text
converter                    ties  notes  measures  voices
Partitura (row 1 baseline)     20    143        14      10
MIDI2ScoreTransformer (row 5)   1     82         8       5
Ivory oracle                  few      -    8 + 1/8 pickup   -
```

Row 5 is the first local output the user's stated goal can be applied to. It
selects A major, matching the oracle. It separates hands cleanly, uses one tie,
and produces eight measures, matching the oracle's measure count.

Row 5 received **no oracle-derived hints**. Transkun consumed the raw WAV, and
MIDI2ScoreTransformer consumed Transkun's unmodified MIDI. Tempo, meter, key,
downbeat, quantization grid, hand assignment, and voicing were all inferred.
The oracle's tempo and meter were supplied only to row 4, which is a separate
diagnostic and did not feed row 5.

It differs from the oracle in ways that are visible and worth recording:

- 4/4 rather than the oracle's 6/8 with a one-eighth pickup;
- no tempo marking, chord symbols, or arpeggiate marks; and
- some thirty-second-note flourishes where the oracle reads as eighths.

Rows 2 and 3 establish that MuseScore's default MIDI import is not sufficient
by itself: both remain tie forests, and MuseScore estimated 163 and 90 BPM.

Row 4 is the most diagnostic negative result. Supplying the oracle's own tempo
and meter to MuseScore fixes the *structure* — it produces eight measures of
6/8 at the correct tempo — but the engraving is still unreadable, full of
thirty-seconds, sixty-fourths, and spurious tuplets. A single constant tempo
cannot absorb rubato, so notes drift off the grid and the quantizer represents
the drift literally. A correct tempo estimate is therefore not enough; a
time-varying beat map or a learned quantizer is required.

## Beat evidence

Beat This! 1.1.0 ran on the same WAV and produced 26 beats over 34.688 s. Its
first beat is 1.72 s and Transkun's first onset is 1.7125 s. Its mean
inter-beat interval implies about 47 BPM, matching the oracle's marked
`quarter = 47`, and 8 bars of 6/8 at that tempo plus a one-eighth pickup spans
31.3 s against 31.6 s of actual playing.

That agreement is at the aggregate level only. Individual beat spacings range
from 0.14 s to 3.0 s, so the emitted beat sequence is not a usable grid for
this free improvisation. Treat the tempo agreement as corroboration of the
oracle's reading, not as a working beat tracker for this material.

## Integration constraints found

MIDI2ScoreTransformer runs, but not cleanly:

- the GitHub repository publishes **no license**, which blocks adoption under
  the project's own dependency rules;
- the released `MIDI2ScoreTF.ckpt` (389,829,880 bytes, SHA-256
  `7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638`) is a
  pickled Lightning checkpoint that requires `weights_only=False` or an
  explicit `add_safe_globals([MyModelConfig])`;
- its pickled config predates current `transformers`; 4.44.2 works, while
  current releases fail on `_attn_implementation_internal` and
  `_experts_implementation_internal`;
- **the MPS backend silently produces an empty score.** The same checkpoint and
  input on CPU produce 82 notes. Any adoption must pin CPU or validate MPS
  output against a known result; and
- it requires a forked `music21`, `score_transformer`, `muster`, and a
  MuseScore binary path.

Transkun installs from PyPI under MIT, but needs `setuptools<81` because it
imports `pkg_resources`.

Wall-clock cost of the whole offline cascade on the 34.688-second take, Apple
M4 Pro, CPU only, each figure including interpreter start and model load:

```text
Transkun, cold first run          18.9 s
Transkun, warm rerun               5.5 s   (byte-identical output)
MIDI2ScoreTransformer              4.0 s
cascade total, warm                9.5 s   for 34.688 s of audio
```

The warm cascade is roughly 3.6 times faster than real time. The cold Transkun
figure is a one-time cache and compilation cost, not steady-state throughput.
This is offline batch cost only and says nothing about live latency; the score
model consumes a complete performance by construction.

## What this does not establish

- One unaligned take with no reference score. Readability is the user's
  subjective judgment, and the Ivory MusicXML is still paywalled, so no
  note-level or MV2H/MUSTER comparison against the oracle is possible.
- No claim about Transkun's precision or recall; only the octave-pair and
  restart counts changed measurably.
- Nothing about live transcription. This cascade is offline and the score model
  consumes a complete performance.

## Recommended next work

1. Resolve the MIDI2ScoreTransformer license, by asking the authors or by
   treating the approach as a design to reimplement rather than a dependency.
2. Add Transkun behind the existing offline model-adapter boundary. It is MIT,
   pip-installable, reduces the reported octave failure, and supplies the first
   pedal evidence in the project.
3. Score the cascade on ASAP, where aligned performance MIDI and MusicXML
   exist, so the notation layer gets a real metric instead of one subjective
   take.
4. Feed ground-truth MIDI and Transkun MIDI through the same converter to
   separate remaining detection error from remaining notation error.
5. Only then revisit meter and pickup selection, which is the largest visible
   remaining difference from the oracle.
