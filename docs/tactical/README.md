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
| [`013-hybrid-product-migration-master.md`](013-hybrid-product-migration-master.md) | Master record; Phases 6–8 deferred | Completed shared React, Python-core, and R5 Tauri migration record; packaged desktop, managed hosting, and sync scopes retained as deferred options |
| [`014-freeze-migration-baseline.md`](014-freeze-migration-baseline.md) | Complete | Phase 1 migration baseline, regression command, retained application behavior, golden fixtures, and R1 handoff |
| [`015-contracts-and-structure.md`](015-contracts-and-structure.md) | Complete | Phase 2 versioned contracts, runtime boundary, explicit local session API, dependency structure, and accepted R2 review |
| [`016-shared-react-application.md`](016-shared-react-application.md) | Complete | Phase 3 shared React workspace, local and fixture runtimes, accepted R3 interactions, score isolation, and synchronized playback |
| [`017-python-application-core.md`](017-python-application-core.md) | Complete; R4 accepted | Phase 4 framework-independent Python services, thin local adapters, compact ordinary recording, bounded debug retention, and R4 parity gate |
| [`018-score-playback-alignment.md`](018-score-playback-alignment.md) | Complete | Source-event-to-score alignment artifacts, synchronized OSMD playback cursor, and piano-roll playhead |
| [`019-linux-development-validation.md`](019-linux-development-validation.md) | Complete | Fresh-clone x86_64 Linux gates, real model paths, platform-neutral fixes, dependency footprint, and same-process scheduling evidence |
| [`020-responsive-score-reader.md`](020-responsive-score-reader.md) | Implemented | Exact-snapshot responsive score reader with phone, tablet, desktop, page-turn, and fullscreen layouts |
| [`021-deterministic-score-postprocessing.md`](021-deterministic-score-postprocessing.md) | Implemented | Versioned `music21` score variants with automatic clef cleanup and pitch-preserving enharmonic key respelling |
| [`022-durable-capture-worker-isolation.md`](022-durable-capture-worker-isolation.md) | Implemented; macOS soak passed | Durable PCM ingest, bounded isolated preview/commit workers, prompt Stop, and reattachable settlement; same-duration Linux soak remains a host-specific gap |
| [`023-backend-capability-degradation.md`](023-backend-capability-degradation.md) | Complete | Measured live, delayed, after-Stop, and unavailable correction modes |
| [`024-score-reader-engraving-density.md`](024-score-reader-engraving-density.md) | Implemented | Visible system spacing and meaningful Large, Comfortable, and Compact reader engraving profiles |
| [`025-public-live-caddy.md`](025-public-live-caddy.md) | Implemented | Caddy sharing of the real local React and Python/model application over the LAN through the Pi |
| [`026-empty-score-feedback.md`](026-empty-score-feedback.md) | Implemented | Explicit no-piano-notes score feedback with preserved job-error details in the shared application |
| [`027-mobile-session-navigation.md`](027-mobile-session-navigation.md) | Complete | Touch-friendly off-canvas session history and navigation on narrow screens |
| [`028-score-alignment-reconciliation.md`](028-score-alignment-reconciliation.md) | Complete | Exact-pitch monotonic reconciliation between source events and generated score attacks |
| [`029-durable-macos-share-service.md`](029-durable-macos-share-service.md) | Implemented | On-demand launchd supervision, persistent lifecycle logs, and explicit macOS-only service controls |
| [`030-early-tauri-sidecar-boundary.md`](030-early-tauri-sidecar-boundary.md) | Complete; R5 accepted | Self-contained macOS arm64 Tauri shell, authenticated Python sidecar, CPU model pack, bundle inventory, and R5 gate |
| [`030-idle-model-worker-eviction.md`](030-idle-model-worker-eviction.md) | Implemented | Lazy model loading plus generation-safe worker eviction ten minutes after full capture settlement |
| [`031-internal-desktop-score-runtime.md`](031-internal-desktop-score-runtime.md) | Complete; R5 accepted | Opt-in internal-only macOS desktop score runtime under provisional checkpoint licensing; no distribution artifact |
| [`032-cross-platform-artifact-export.md`](032-cross-platform-artifact-export.md) | Complete; R5 accepted | Shared browser downloads and bounded native desktop Save As export through the runtime boundary |
| [`033-sqlite-family-authentication.md`](033-sqlite-family-authentication.md) | Complete; live | Typed SQLAlchemy/Alembic identity catalog, CLI-created family users, cookie sessions, authenticated FastAPI composition, and minimal React login |
| [`034-authenticated-family-scores.md`](034-authenticated-family-scores.md) | Complete; live | Default score generation and rendering for the authenticated private family service |
| [`035-browser-score-cursor-parity.md`](035-browser-score-cursor-parity.md) | Complete; live | Exact browser parity with producer MIDI rounding and score-cursor ordering |
| [`036-musical-session-workspace-refresh.md`](036-musical-session-workspace-refresh.md) | Complete; live | Sessions homepage, compact performance identity, contextual feedback, editable naming, lazy preview/playback, and keyboard audition |
| [`037-detachable-score-playback.md`](037-detachable-score-playback.md) | Complete; live | Persistent selected-session playback, detachable panel-local score following, reader continuity, and current-attack note highlighting |
| [`038-recording-import.md`](038-recording-import.md) | Complete; live | First-class WAV/MP3 recording import with bounded upload, provenance, shared transcription, and contextual progress/errors |
| [`039-continuous-library-playback.md`](039-continuous-library-playback.md) | Complete; live | One route-independent playback transport, library seeking, first-note cueing, and clickable synchronized opening previews |
| [`040-websocket-runtime-dependency.md`](040-websocket-runtime-dependency.md) | Complete; live | Locked WebSocket protocol support for local, authenticated family, and packaged capture runtimes |
| [`040-score-producer-provenance.md`](040-score-producer-provenance.md) | Complete; live | Durable score-pipeline provenance, compatibility freshness, and actionable legacy-cursor feedback |
| [`041-post-capture-delete-settlement.md`](041-post-capture-delete-settlement.md) | Complete; live | Immediate post-settlement deletion and automatic catalog lifecycle convergence |
| [`042-family-profile-schema-and-ui.md`](042-family-profile-schema-and-ui.md) | Complete; live | Seeded generic group/profile schema, creator-versus-performer attribution, and the profile-first Family UI |
| [`043-browser-midi-float-parity.md`](043-browser-midi-float-parity.md) | Complete; live | Browser parity with the producer's floating-point MIDI tick conversion and Python rounding |
| [`044-score-reliability-harness.md`](044-score-reliability-harness.md) | Complete | Slow headed Chromium/WebKit retained-score audit plus shared Python/TypeScript MIDI-tick conformance fixtures |
| [`045-client-deployment-continuity.md`](045-client-deployment-continuity.md) | Complete; live | Exact asset routing, update polling and recovery, and bounded recent hashed-asset retention |
| [`046-browser-capture-pop-diagnostics.md`](046-browser-capture-pop-diagnostics.md) | Complete; live | Browser, device, AudioWorklet, and delivery diagnostics for retained Android capture discontinuities |
| [`047-live-settling-and-auto-score-recovery.md`](047-live-settling-and-auto-score-recovery.md) | Complete; live | Persistent measured correction profile, visible capability diagnostics, and one bounded final-horizon score retry |
| [`048-overlapping-score-input-notes.md`](048-overlapping-score-input-notes.md) | Complete; live | Unambiguous overlapping same-pitch MIDI channels, bounded score errors, and restored retained-session score generation |
| [`049-native-windows-runtime-baseline.md`](049-native-windows-runtime-baseline.md) | Complete | Native Windows dependency resolution, deterministic CPU model parity, unpackaged server replay, and packaging inventory |
| [`050-native-windows-cuda-parity.md`](050-native-windows-cuda-parity.md) | Complete | Explicit Windows CUDA runtime, fixed Transkun CPU/CUDA parity, and unpackaged CUDA server replay |
| [`051-signed-macos-update-lane.md`](051-signed-macos-update-lane.md) | Complete; signed `0.1.1` update accepted in Tart | Signed and notarized macOS arm64 baseline, credentialed draft-first release lane, desktop updater, and real installed old-to-new acceptance |
| [`052-user-acquired-score-runtime.md`](052-user-acquired-score-runtime.md) | Active; macOS update persistence passed | Shared education/research acknowledgement, direct upstream score-runtime acquisition, external activation/removal, and signed-update persistence |
| [`053-windows-desktop-release-lane.md`](053-windows-desktop-release-lane.md) | Active; signed `0.1.1` published, update proof open | Windows x64 CPU sidecar/package adaptation, signed per-user NSIS lane, machine-control acceptance, and real installed updater proof |
| [`054-public-marketing-site.md`](054-public-marketing-site.md) | Complete; live | Public red/ivory/black product and download site, hosted-interest collection, privacy surface, and Cloudflare deployment |
| [`055-macos-microphone-entitlement-repair.md`](055-macos-microphone-entitlement-repair.md) | Physical development capture passed; release open | Hardened macOS audio-input signing repair, fail-closed release checks, and physical-microphone replacement gate |
| [`056-website-aligned-application-theme.md`](056-website-aligned-application-theme.md) | Complete in source; `0.1.3` prepared | Website-aligned light palette, explicit persistent dark mode, and matching native desktop window chrome |
