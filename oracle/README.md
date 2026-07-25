# Golden Reference

This directory holds the fixed reference pair used to judge every
audio-to-readable-score experiment. It is the standard the project is trying to
meet, not a generated artifact.

The target is legible engraved sheet music that the performer can sight read
back. Lead sheets, chord-symbol summaries, and piano rolls do not satisfy it.

## Reference input

```text
file: kyle-test-recording.wav
SHA-256:
3d747d653d8f7a30c2e3261c85b8b9207959a7e00e8b009aac5fd969247f6f47
size: 3,330,092 bytes
format: mono PCM16 WAV, 48,000 Hz, 34.688 s
peak: -4.25 dBFS
RMS: -21.94 dBFS
clipped samples: 0
source: browser workbench take on the target acoustic piano, 2026-07-24
identical to workbench job 20260724T104057-1c108a0915e3
content: unrehearsed improvisation ("noodling"), no reference MIDI or score
```

The lossless WAV is captured audio and stays out of Git per the repository
guardrail in [`AGENTS.md`](../AGENTS.md). Restore it from the user's local copy
or from the workbench job above; the hash above identifies the exact bytes.

A tracked lossy copy exists so the reference is reproducible from a clone
alone:

```text
file: kyle-test-recording.mp3
SHA-256:
6ef6f322b943939539a2db35bc5c5ae22d8f0fe8faf4d582fce65d3525a45ae1
size: 834,092 bytes
format: MP3, mono, 48,000 Hz, 192 kbps CBR, 34.688 s
encoder: ffmpeg libmp3lame
derived from: kyle-test-recording.wav
```

**Benchmark results must cite the WAV, not the MP3.** The MP3 is a
convenience copy for listening and for reproducing the reference by ear. Codec
artifacts have not been measured against the lossless control, so any model
run on the MP3 confounds transcription quality with encoding.

## Reference output

```text
file: ivory-score-reference.png
SHA-256:
6a7274e5b3fe65895c0c0dcdb2eabb162f48d0aea12ad089d479e12c4adc4ca7
dimensions: 1024 x 511
service: Ivory (https://ivory-app.com/), free preview tier
date: 2026-07-24
```

Ivory produced this from the reference WAV alone. The user judged it easy to
sight read and an almost exact reproduction of what was played. MusicXML export
was paywalled on the free tier, so only the rendered image exists; structural
note-level comparison against it is not currently possible.

Observable properties of the reference engraving:

- title `kyle test recording`, subtitle `In A`;
- one `Piano` grand staff, three key sharps (A major);
- an explicit `1/8` pickup measure followed by `6/8`;
- tempo mark `quarter = 47`;
- nine measures total across two systems;
- chord symbols above the staff: `G#7#9`, `A`, `G#m`, `A`, `E7`, `A`;
- four arpeggiate (rolled-chord) marks;
- ties used sparingly and only where musically sensible;
- left hand carrying dotted-quarter chord blocks, right hand carrying the
  melodic line, with no visible hand-crossing artifacts.

Those properties are the scoring rubric. A candidate pipeline is compared on
meter and pickup, tempo octave, key and spelling, measure count, tie count,
voice count, hand assignment, and subjective sight-readability.

## Prior local baseline

The repository's Partitura converter was reviewed against this same input on
2026-07-24 and failed: it selected 82.811 BPM with a default 4/4, split notes
across artificial bar lines, and produced an unreadable tie forest. See
[`docs/topics/performance-to-notation.md`](../docs/topics/performance-to-notation.md).

## Candidate results

Generated candidate scores belong in the ignored `results/` tree, not here.
This directory holds only the input and the standard.
