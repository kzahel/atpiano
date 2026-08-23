import { AudioPlayback } from "./audio-playback.js";
import { formatClock, noteName } from "../lib/format.js";
import { noteDisplaySegments } from "../lib/note-display.js";
import { pedalDisplaySegment } from "../lib/pedal-display.js";
import {
  type ScoreAlignment,
} from "../lib/score-alignment.js";
import { MusicXmlScore } from "./musicxml-score.js";
import { PianoKeyboard } from "./piano-keyboard.js";
import type {
  EventRevision,
  Horizon,
  ScoreFreshness,
  ScoreProducerProvenance,
  ScoreVariant,
  Session,
} from "../runtime/atpiano-runtime.js";
import { usePlaybackStore } from "../state/playback-store.js";
import { useWorkspaceStore } from "../state/workspace-store.js";

function PianoRoll({
  events,
  session,
  horizon,
  inspectionSample,
  onInspect,
}: {
  readonly events: readonly EventRevision[];
  readonly session: Session;
  readonly horizon: Horizon | undefined;
  readonly inspectionSample: number | null;
  readonly onInspect: (sample: number) => void;
}) {
  const total = Math.max(1, session.source_frame_count);
  const notes = events.filter(
    (event) => event.kind === "note" && event.pitch !== null,
  );
  const pedalLanes = [
    { kind: "sustain", label: "Sustain" },
    { kind: "soft-pedal", label: "Soft" },
  ] as const;
  return (
    <section className="view-card roll-card">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Source-sample timeline</p>
          <h3>Piano roll</h3>
        </div>
        <div className="legend">
          <span><i className="legend-dot provisional" /> live estimate</span>
          <span><i className="legend-dot committed" /> settled</span>
          <span><i className="legend-line" /> settled through</span>
        </div>
      </div>
      <div
        className="roll-stage"
        role="img"
        aria-label={`${notes.length} note events over ${formatClock(total, session.sample_rate_hz)}`}
        onClick={(event) => {
          const bounds = event.currentTarget.getBoundingClientRect();
          onInspect(
            Math.round(((event.clientX - bounds.left) / bounds.width) * total),
          );
        }}
      >
        <div className="octave-labels" aria-hidden="true">
          {[8, 7, 6, 5, 4, 3, 2, 1].map((octave) => <span key={octave}>C{octave}</span>)}
        </div>
        <div className="roll-grid">
          {notes.map((note) => {
            const display = noteDisplaySegments(
              note,
              horizon,
              session.sample_rate_hz,
            );
            if (!display) return null;
            return (
              <span key={`${note.event_id}:${note.revision}`}>
                <i
                  className={`roll-note ${note.lifecycle}`}
                  title={`${noteName(note.pitch!)} at ${formatClock(note.onset_sample, session.sample_rate_hz)}`}
                  style={{
                    left: `${(display.solidStart / total) * 100}%`,
                    width: `${Math.max(0.35, ((display.solidEnd - display.solidStart) / total) * 100)}%`,
                    top: `${((108 - note.pitch!) / 87) * 100}%`,
                  }}
                />
                {display.tailStart !== null && display.tailEnd !== null && (
                  <i
                    className={`roll-note-tail ${note.lifecycle}`}
                    style={{
                      left: `${(display.tailStart / total) * 100}%`,
                      width: `${((display.tailEnd - display.tailStart) / total) * 100}%`,
                      top: `${((108 - note.pitch!) / 87) * 100}%`,
                    }}
                  />
                )}
              </span>
            );
          })}
          {horizon && (
            <i
              className="commit-line"
              style={{ left: `${(horizon.commit_sample / total) * 100}%` }}
            />
          )}
          {inspectionSample !== null && (
            <i
              className="roll-playhead"
              aria-hidden="true"
              style={{
                left: `${(
                  (Math.max(0, Math.min(total, inspectionSample)) / total) *
                  100
                ).toFixed(4)}%`,
              }}
            />
          )}
        </div>
        <div
          className="pedal-panel"
          aria-label="Model-estimated pedal gestures"
        >
          {pedalLanes.map((lane) => (
            <div className={`pedal-lane ${lane.kind}`} key={lane.kind}>
              <span className="pedal-label">
                {lane.label}
                <small>inferred</small>
              </span>
              <div className="pedal-gestures">
                {events
                  .filter((event) => event.kind === lane.kind)
                  .map((pedal) => {
                    const display = pedalDisplaySegment(
                      pedal,
                      horizon,
                      total,
                      session.sample_rate_hz,
                    );
                    if (!display) return null;
                    const suspect = display.suspectLongEstimate;
                    const description = `${lane.label} pedal estimate from ${formatClock(
                      display.start,
                      session.sample_rate_hz,
                    )} to ${formatClock(
                      display.end,
                      session.sample_rate_hz,
                    )}${suspect ? "; unusually long, verify against the performance" : ""}`;
                    return (
                      <i
                        aria-label={description}
                        className={suspect ? "suspect" : undefined}
                        key={`${pedal.event_id}:${pedal.revision}`}
                        title={description}
                        style={{
                          left: `${(display.start / total) * 100}%`,
                          width: `${Math.max(
                            0.25,
                            ((display.end - display.start) / total) * 100,
                          )}%`,
                        }}
                      />
                    );
                  })}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="timeline-axis">
        <span>00:00</span>
        <span>{formatClock(total / 2, session.sample_rate_hz)}</span>
        <span>{formatClock(total, session.sample_rate_hz)}</span>
      </div>
    </section>
  );
}

function ScorePreview({
  session,
  scoreStatus,
  scoreErrorMessage,
  scoreAvailable,
  scoreXml,
  scoreXmlError,
  scoreAlignment,
  scoreAlignmentError,
  scoreFreshness,
  scoreProducer,
  scoreHorizonSample,
  scoreVariants,
  selectedScoreVariant,
  scoreVariantBusy,
  inspectionSample,
  onGenerate,
  onEnableScoreGeneration,
  onOpenReader,
  onSelectScoreVariant,
  onCreateAutomaticVariant,
  onCreateEnharmonicVariant,
}: {
  readonly session: Session;
  readonly scoreStatus: string | null;
  readonly scoreErrorMessage: string | null;
  readonly scoreAvailable: boolean;
  readonly scoreXml: string | undefined;
  readonly scoreXmlError: Error | null;
  readonly scoreAlignment: ScoreAlignment | undefined;
  readonly scoreAlignmentError: Error | null;
  readonly scoreFreshness: ScoreFreshness | null;
  readonly scoreProducer: ScoreProducerProvenance | null;
  readonly scoreHorizonSample: number | undefined;
  readonly scoreVariants: readonly ScoreVariant[];
  readonly selectedScoreVariant: ScoreVariant | undefined;
  readonly scoreVariantBusy: boolean;
  readonly inspectionSample: number | null;
  readonly onGenerate: () => void;
  readonly onEnableScoreGeneration?: () => void;
  readonly onOpenReader: () => void;
  readonly onSelectScoreVariant: (variant: ScoreVariant) => void;
  readonly onCreateAutomaticVariant: () => void;
  readonly onCreateEnharmonicVariant: () => void;
}) {
  const playbackStatus = usePlaybackStore((state) => state.status);
  const scoreFollow = usePlaybackStore((state) => state.scoreFollow);
  const followScore = usePlaybackStore((state) => state.followScore);
  const freshnessAdvisory = (() => {
    if (!scoreFreshness || scoreFreshness.reason === "current") return null;
    const snapshotRevision = scoreFreshness.snapshot_pipeline_revision;
    switch (scoreFreshness.reason) {
      case "alignment-schema-unsupported":
        return "This score uses legacy cursor metadata. Refresh score to generate the current playback mapping.";
      case "legacy-provenance-missing":
        return "This score predates revision tracking. Refresh score to record its current producer provenance.";
      case "pipeline-outdated":
        return `This score was generated with pipeline r${snapshotRevision}; r${scoreFreshness.current_pipeline_revision} is current. Refresh score to apply the current score pipeline.`;
      case "pipeline-newer":
        return `This score was generated with newer pipeline r${snapshotRevision}; this application provides r${scoreFreshness.current_pipeline_revision}.`;
      case "producer-schema-unsupported":
        return "This score's producer revision is not supported. Refresh score to publish current provenance.";
    }
  })();
  const revisionLabel = scoreProducer
    ? `Score revision · r${scoreProducer.pipeline_revision} · ${scoreFreshness?.status ?? "unclassified"}`
    : scoreFreshness
      ? `Score revision · untracked · ${scoreFreshness.status}`
      : null;
  const revisionDetail = scoreProducer
    ? [
        `pipeline ${scoreProducer.pipeline_fingerprint}`,
        scoreProducer.application_revision
          ? `Atpiano ${scoreProducer.application_revision}${scoreProducer.application_dirty ? " (dirty)" : ""}`
          : `Atpiano ${scoreProducer.application_version}`,
      ].join(" · ")
    : undefined;
  const selectedVariantDescription = (() => {
    if (!selectedScoreVariant) return null;
    switch (selectedScoreVariant.role) {
      case "baseline":
        return "Original model notation, kept unchanged for comparison.";
      case "automatic":
        return "Same notes and key spelling, with clef changes that reduce ledger lines.";
      case "enharmonic":
        return "Same sounding pitches, respelled in the selected enharmonic key.";
    }
  })();
  return (
    <section className="view-card score-card">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Stable notation snapshot</p>
          <h3>Committed score</h3>
        </div>
        <div className="score-heading-actions">
          {scoreXml && (
            <button
              className="button small secondary"
              type="button"
              onClick={onOpenReader}
            >
              Open score reader
            </button>
          )}
          {!scoreAvailable && onEnableScoreGeneration
            ? (
              <button
                className="button small"
                type="button"
                onClick={onEnableScoreGeneration}
              >
                Enable score generation
              </button>
            )
            : (
              <button
                className="button small"
                type="button"
                disabled={!scoreAvailable || scoreStatus === "running"}
                onClick={onGenerate}
              >
                {scoreXml ? "Refresh score" : "Render committed score"}
              </button>
            )}
        </div>
      </div>
      <p className={`score-state ${scoreStatus ?? "idle"}`}>
        {!scoreAvailable
          ? "Score runtime is not installed. Capture and review remain available."
          : scoreStatus === "running"
            ? "Rendering the frozen committed prefix…"
            : scoreStatus === "failed"
              ? scoreErrorMessage ??
                "Score rendering failed. Your performance is still safe."
              : scoreXml && scoreHorizonSample !== undefined
                ? `Generated score through ${formatClock(scoreHorizonSample, session.sample_rate_hz)}.`
                : "Only closed corrected notes enter this snapshot."}
      </p>
      <p className="score-not-live">
        Generated on request from a frozen corrected prefix. This is not a
        live-note view.
      </p>
      {scoreXml && scoreVariants.length > 0 && (
        <div className="score-engraving-controls">
          <label>
            <span>Notation version</span>
            <select
              value={selectedScoreVariant?.score_variant_id ?? ""}
              disabled={scoreVariantBusy}
              onChange={(event) => {
                const variant = scoreVariants.find(
                  (candidate) =>
                    candidate.score_variant_id === event.currentTarget.value,
                );
                if (variant) onSelectScoreVariant(variant);
              }}
            >
              {scoreVariants.map((variant) => (
                <option
                  key={variant.score_variant_id}
                  value={variant.score_variant_id}
                >
                  {variant.label}
                </option>
              ))}
            </select>
          </label>
          {selectedScoreVariant?.available_enharmonic_fifths !== null &&
            selectedScoreVariant?.available_enharmonic_fifths !== undefined && (
              <button
                className="button small secondary"
                type="button"
                disabled={scoreVariantBusy}
                onClick={onCreateEnharmonicVariant}
              >
                Use {
                  selectedScoreVariant.available_enharmonic_label
                    ?.split(" — ")[0]
                    .toLowerCase() ?? "alternative spelling"
                }
              </button>
            )}
          {selectedScoreVariant?.role === "baseline" &&
            !scoreVariants.some((variant) => variant.role === "automatic") && (
              <button
                className="button small secondary"
                type="button"
                disabled={scoreVariantBusy}
                onClick={onCreateAutomaticVariant}
              >
                Apply automatic clefs
              </button>
            )}
          {selectedVariantDescription && (
            <p className="score-variant-description">
              {selectedVariantDescription}
            </p>
          )}
        </div>
      )}
      {selectedScoreVariant?.needs_review && (
        <p className="score-render-warning" role="status">
          Automatic clefs reduced ledger lines, but one or more passages still
          merit engraving review.
        </p>
      )}
      {freshnessAdvisory && (
        <p className="score-render-warning" role="status">
          {freshnessAdvisory}
        </p>
      )}
      {scoreXml ? (
        <div className="score-playback-frame">
          <MusicXmlScore
            xml={scoreXml}
            alignment={scoreAlignment}
            inspectionSample={inspectionSample}
            scoreHorizonSample={scoreHorizonSample}
          />
          {scoreAlignment &&
            playbackStatus === "playing" &&
            scoreFollow === "detached" && (
              <button
                className="score-follow-playback"
                type="button"
                onClick={followScore}
              >
                <span aria-hidden="true">↳</span>
                Follow playback
              </button>
            )}
        </div>
      ) : (
        <div className="score-empty">
          <strong>No generated score snapshot</strong>
          <span>
            Choose Render committed score to create notation from the current
            corrected horizon.
          </span>
        </div>
      )}
      {scoreXmlError && (
        <p className="score-render-error" role="status">
          The notation preview could not load. The MusicXML download remains
          available.
        </p>
      )}
      {scoreAlignmentError &&
        scoreFreshness?.reason !== "alignment-schema-unsupported" && (
        <p className="score-render-error" role="status">
          The score remains readable, but its playback cursor could not load.
        </p>
      )}
      {revisionLabel && (
        <small className="score-provenance" title={revisionDetail}>
          {revisionLabel}
        </small>
      )}
      <small>
        Snapshot target · {session.display_name ?? session.session_id}
      </small>
    </section>
  );
}

export function PerformanceViews({
  session,
  events,
  horizon,
  showRoll,
  showKeyboard,
  showScore,
  scoreStatus,
  scoreErrorMessage,
  scoreAvailable,
  scoreXml,
  scoreXmlError,
  scoreAlignment,
  scoreAlignmentError,
  scoreFreshness,
  scoreProducer,
  scoreHorizonSample,
  scoreVariants,
  selectedScoreVariant,
  scoreVariantBusy,
  audioUnavailableReason,
  onGenerateScore,
  onEnableScoreGeneration,
  onOpenScoreReader,
  onSelectScoreVariant,
  onCreateAutomaticVariant,
  onCreateEnharmonicVariant,
}: {
  readonly session: Session;
  readonly events: readonly EventRevision[];
  readonly horizon: Horizon | undefined;
  readonly showRoll: boolean;
  readonly showKeyboard: boolean;
  readonly showScore: boolean;
  readonly scoreStatus: string | null;
  readonly scoreErrorMessage: string | null;
  readonly scoreAvailable: boolean;
  readonly scoreXml: string | undefined;
  readonly scoreXmlError: Error | null;
  readonly scoreAlignment: ScoreAlignment | undefined;
  readonly scoreAlignmentError: Error | null;
  readonly scoreFreshness: ScoreFreshness | null;
  readonly scoreProducer: ScoreProducerProvenance | null;
  readonly scoreHorizonSample: number | undefined;
  readonly scoreVariants: readonly ScoreVariant[];
  readonly selectedScoreVariant: ScoreVariant | undefined;
  readonly scoreVariantBusy: boolean;
  readonly audioUnavailableReason: string;
  readonly onGenerateScore: () => void;
  readonly onEnableScoreGeneration?: () => void;
  readonly onOpenScoreReader: () => void;
  readonly onSelectScoreVariant: (variant: ScoreVariant) => void;
  readonly onCreateAutomaticVariant: () => void;
  readonly onCreateEnharmonicVariant: () => void;
}) {
  const inspectionSample = useWorkspaceStore(
    (state) => state.inspectionSample,
  );
  const onInspect = useWorkspaceStore((state) => state.setInspectionSample);
  return (
    <div className="performance-views">
      <AudioPlayback unavailableReason={audioUnavailableReason} />
      {showScore && (
        <ScorePreview
          session={session}
          scoreStatus={scoreStatus}
          scoreErrorMessage={scoreErrorMessage}
          scoreAvailable={scoreAvailable}
          scoreXml={scoreXml}
          scoreXmlError={scoreXmlError}
          scoreAlignment={scoreAlignment}
          scoreAlignmentError={scoreAlignmentError}
          scoreFreshness={scoreFreshness}
          scoreProducer={scoreProducer}
          scoreHorizonSample={scoreHorizonSample}
          scoreVariants={scoreVariants}
          selectedScoreVariant={selectedScoreVariant}
          scoreVariantBusy={scoreVariantBusy}
          inspectionSample={inspectionSample}
          onGenerate={onGenerateScore}
          onEnableScoreGeneration={onEnableScoreGeneration}
          onOpenReader={onOpenScoreReader}
          onSelectScoreVariant={onSelectScoreVariant}
          onCreateAutomaticVariant={onCreateAutomaticVariant}
          onCreateEnharmonicVariant={onCreateEnharmonicVariant}
        />
      )}
      {showRoll && (
        <PianoRoll
          events={events}
          session={session}
          horizon={horizon}
          inspectionSample={inspectionSample}
          onInspect={onInspect}
        />
      )}
      {showKeyboard && (
        <PianoKeyboard
          events={events}
          inspectionSample={inspectionSample}
        />
      )}
    </div>
  );
}
