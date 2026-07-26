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
| [`012-committed-score-snapshots.md`](012-committed-score-snapshots.md) | Complete | Internal MIDI2ScoreTransformer snapshots over committed, closed v2 notes with isolated CPU execution and OSMD rendering |
| [`013-hybrid-product-migration-master.md`](013-hybrid-product-migration-master.md) | Master plan | Eight-phase migration tracker for the shared React application, Python core, early Tauri boundary, hosted service, human review gates, and limited sync |
| [`014-freeze-migration-baseline.md`](014-freeze-migration-baseline.md) | Complete | Phase 1 migration baseline, regression command, retained application behavior, golden fixtures, and R1 handoff |
| [`015-contracts-and-structure.md`](015-contracts-and-structure.md) | Complete | Phase 2 versioned contracts, runtime boundary, explicit local session API, dependency structure, and accepted R2 review |
| [`016-shared-react-application.md`](016-shared-react-application.md) | Complete | Phase 3 shared React workspace, local and fixture runtimes, accepted R3 interactions, score isolation, and synchronized playback |
| [`017-python-application-core.md`](017-python-application-core.md) | Planned | Phase 4 framework-independent Python services, thin local adapters, compact ordinary recording, bounded debug retention, and R4 parity gate |
| [`018-score-playback-alignment.md`](018-score-playback-alignment.md) | Complete | Source-event-to-score alignment artifacts, synchronized OSMD playback cursor, and piano-roll playhead |
| [`019-linux-development-validation.md`](019-linux-development-validation.md) | Complete | Fresh-clone x86_64 Linux gates, real model paths, platform-neutral fixes, dependency footprint, and same-process scheduling evidence |
| [`020-responsive-score-reader.md`](020-responsive-score-reader.md) | Implemented | Exact-snapshot responsive score reader with phone, tablet, desktop, page-turn, and fullscreen layouts |
| [`021-deterministic-score-postprocessing.md`](021-deterministic-score-postprocessing.md) | Planned | Versioned `music21` score variants with automatic clef cleanup and pitch-preserving enharmonic key respelling |
| [`022-durable-capture-worker-isolation.md`](022-durable-capture-worker-isolation.md) | Awaiting Linux | Durable PCM ingest, bounded isolated preview/commit workers, prompt Stop, and reattachable settlement |
| [`023-backend-capability-degradation.md`](023-backend-capability-degradation.md) | Awaiting Linux | Measured live, delayed, after-Stop, and unavailable correction modes |
