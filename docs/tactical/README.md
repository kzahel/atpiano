# Implementation Tactical Docs

Bounded implementation plans and execution records live here.

Use zero-padded numeric prefixes for new tactical docs: `000-topic.md`,
`001-next-topic.md`, and so on. Keep one active implementation slice per doc
and add every tactical to this index. A completed tactical is retained as an
execution record; continuing status and direction belong in the relevant
[`../topics/`](../topics/README.md) document.

| Doc | Status | Purpose |
|---|---|---|
| [`000-live-replay-benchmark.md`](000-live-replay-benchmark.md) | Complete | Deterministic MIDI/audio smoke test, Basic Pitch reference, live replay, scoring, artifact review, and file-producing microphone adapter |
| [`001-browser-capture-workbench.md`](001-browser-capture-workbench.md) | Complete | Local browser microphone recording, file submission, background transcription, and automatic run review |
| [`002-performance-notation-spikes.md`](002-performance-notation-spikes.md) | Complete | Traceable Partitura/MusicXML score, editable OSMD view, and two-phase Ivory oracle import |
| [`003-live-browser-transcription-spike.md`](003-live-browser-transcription-spike.md) | Complete | Sample-indexed browser transport, rolling Basic Pitch, and exact full-file backfill landed; its first duration-oriented evaluator was rejected in subjective review |
| [`004-noise-gated-onset-display.md`](004-noise-gated-onset-display.md) | Complete | The room gate and onset-only display are more legible; subjective review exposes stock Basic Pitch frame-derived and harmonic re-onsets during held chords |
| [`005-strict-onset-decoder-spike.md`](005-strict-onset-decoder-spike.md) | Complete | Strict Basic Pitch onset-head decoding at 0.6 reduces held-chord clutter while preserving the fixture; no ungrounded refractory or attack-novelty filter was selected |
| [`006-live-confidence-display-controls.md`](006-live-confidence-display-controls.md) | Complete | Raw/grouped staff controls, configurable chord distance, and optional onset-score labels add diagnostic visibility without changing recognition |
| [`007-live-timing-rhythm-guides.md`](007-live-timing-rhythm-guides.md) | Complete | Source-onset timing labels and preset-based rough rhythm glyphs expose performance spacing without changing transcription |
| [`008-score-pipeline-bakeoff.md`](008-score-pipeline-bakeoff.md) | Complete | Fixed golden-reference comparison isolated both transcription and score-inference gains and produced the first sight-readable local score |
| [`009-three-phase-unbounded-sessions.md`](009-three-phase-unbounded-sessions.md) | Plan sketch | Separate v2 live app with deterministic WAV bring-up, bounded-memory indefinite sessions, trailing Transkun correction, and progressive engraving |
| [`010-corrected-note-workbench-v2.md`](010-corrected-note-workbench-v2.md) | Complete | Separate corrected-note app, aligned and target-piano loop replay, bounded sessions, trailing Transkun commit, pedal, indexed review, and MIDI/JSONL export; engraving excluded |
| [`011-pitch-verification-views.md`](011-pitch-verification-views.md) | Complete | Independently toggleable piano roll and exact-pitch keyboard views with aligned octave landmarks and source-time inspection |
