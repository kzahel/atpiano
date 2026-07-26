import { useEffect, useMemo, useRef, useState } from "react";
import type {
  OpenSheetMusicDisplay as OsmdRenderer,
} from "opensheetmusicdisplay";

import {
  AudioPlayback,
  type AudioPlaybackSource,
} from "./audio-playback.js";
import { formatClock, noteName } from "../lib/format.js";
import { noteDisplaySegments } from "../lib/note-display.js";
import { pedalDisplaySegment } from "../lib/pedal-display.js";
import { pianoLayout } from "../lib/piano-layout.js";
import {
  moveScoreCursor,
  scoreAttackAtSample,
  type ScoreAlignment,
} from "../lib/score-alignment.js";
import type {
  EventRevision,
  Horizon,
  Session,
} from "../runtime/atpiano-runtime.js";

function activePitches(events: readonly EventRevision[], sample: number): Set<number> {
  return new Set(
    events
      .filter(
        (event) =>
          event.kind === "note" &&
          event.pitch !== null &&
          event.lifecycle !== "retracted" &&
          event.onset_sample <= sample &&
          (event.offset_sample ?? sample) >= sample,
      )
      .map((event) => event.pitch!)
  );
}

function PianoKeyboard({
  events,
  session,
  inspectionSample,
  onInspect,
}: {
  readonly events: readonly EventRevision[];
  readonly session: Session;
  readonly inspectionSample: number | null;
  readonly onInspect: (sample: number | null) => void;
}) {
  const notes = events.filter(
    (event) => event.kind === "note" && event.lifecycle !== "retracted",
  );
  const latest = Math.max(0, ...notes.map((event) => event.onset_sample));
  const sample = inspectionSample ?? latest;
  const sounding = activePitches(notes, sample);
  const layout = useMemo(pianoLayout, []);
  return (
    <section className="view-card keyboard-card">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Exact pitch check</p>
          <h3>Detected keys</h3>
        </div>
        <output>
          {sounding.size
            ? [...sounding].map(noteName).join(" · ")
            : "No keys sounding"}
        </output>
      </div>
      <div
        className="piano-keyboard"
        role="img"
        aria-label={
          sounding.size
            ? `Detected keys ${[...sounding].map(noteName).join(", ")}`
            : "No detected piano keys"
        }
      >
        {layout.map((key) => (
          <i
            key={key.pitch}
            className={`${key.black ? "black" : "white"} ${
              sounding.has(key.pitch) ? "sounding" : ""
            }`}
            style={{
              left: `${key.leftPercent}%`,
              width: `${key.widthPercent}%`,
            }}
            title={noteName(key.pitch)}
          />
        ))}
      </div>
    </section>
  );
}

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
          <span><i className="legend-dot provisional" /> provisional</span>
          <span><i className="legend-dot committed" /> corrected</span>
          <span><i className="legend-line" /> commit horizon</span>
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
  scoreAvailable,
  scoreXml,
  scoreXmlError,
  scoreAlignment,
  scoreAlignmentError,
  scoreHorizonSample,
  inspectionSample,
  onGenerate,
}: {
  readonly session: Session;
  readonly scoreStatus: string | null;
  readonly scoreAvailable: boolean;
  readonly scoreXml: string | undefined;
  readonly scoreXmlError: Error | null;
  readonly scoreAlignment: ScoreAlignment | undefined;
  readonly scoreAlignmentError: Error | null;
  readonly scoreHorizonSample: number | undefined;
  readonly inspectionSample: number | null;
  readonly onGenerate: () => void;
}) {
  return (
    <section className="view-card score-card">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Stable notation snapshot</p>
          <h3>Committed score</h3>
        </div>
        <button
          className="button small"
          type="button"
          disabled={!scoreAvailable || scoreStatus === "running"}
          onClick={onGenerate}
        >
          {scoreXml ? "Refresh score" : "Render committed score"}
        </button>
      </div>
      <p className={`score-state ${scoreStatus ?? "idle"}`}>
        {!scoreAvailable
          ? "Score runtime is not installed. Capture and review remain available."
          : scoreStatus === "running"
            ? "Rendering the frozen committed prefix…"
            : scoreStatus === "failed"
              ? "Score rendering failed. Your performance is still safe."
              : scoreXml && scoreHorizonSample !== undefined
                ? `Generated score through ${formatClock(scoreHorizonSample, session.sample_rate_hz)}.`
                : "Only closed corrected notes enter this snapshot."}
      </p>
      <p className="score-not-live">
        Generated on request from a frozen corrected prefix. This is not a
        live-note view.
      </p>
      {scoreXml ? (
        <MusicXmlScore
          xml={scoreXml}
          alignment={scoreAlignment}
          inspectionSample={inspectionSample}
          scoreHorizonSample={scoreHorizonSample}
        />
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
      {scoreAlignmentError && (
        <p className="score-render-error" role="status">
          The score remains readable, but its playback cursor could not load.
        </p>
      )}
      <small>
        Snapshot target · {session.display_name ?? session.session_id}
      </small>
    </section>
  );
}

function MusicXmlScore({
  xml,
  alignment,
  inspectionSample,
  scoreHorizonSample,
}: {
  readonly xml: string;
  readonly alignment: ScoreAlignment | undefined;
  readonly inspectionSample: number | null;
  readonly scoreHorizonSample: number | undefined;
}) {
  const target = useRef<HTMLDivElement>(null);
  const renderer = useRef<OsmdRenderer | null>(null);
  const priorTargetQuarter = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [renderVersion, setRenderVersion] = useState(0);

  useEffect(() => {
    const container = target.current;
    if (!container) return;
    let cancelled = false;
    let currentRenderer: OsmdRenderer | null = null;
    renderer.current = null;
    priorTargetQuarter.current = null;
    setError(null);
    void import("opensheetmusicdisplay")
      .then(async ({ OpenSheetMusicDisplay }) => {
        if (cancelled) return;
        const next = new OpenSheetMusicDisplay(container, {
          autoResize: true,
          backend: "svg",
          drawTitle: false,
          drawingParameters: "compacttight",
          followCursor: true,
          cursorsOptions: [
            {
              type: 1,
              color: "#2fbe8c",
              alpha: 0.82,
              follow: true,
            },
          ],
        });
        currentRenderer = next;
        await next.load(xml);
        if (!cancelled) {
          next.render();
          next.cursor.SkipInvisibleNotes = true;
          next.cursor.hide();
          renderer.current = next;
          setRenderVersion((value) => value + 1);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Notation rendering failed.");
      });
    return () => {
      cancelled = true;
      if (renderer.current === currentRenderer) renderer.current = null;
      currentRenderer?.clear();
      container.replaceChildren();
    };
  }, [xml]);

  useEffect(() => {
    const cursor = renderer.current?.cursor;
    if (!cursor) return;
    const targetQuarter = scoreAttackAtSample(
      alignment,
      inspectionSample,
      scoreHorizonSample,
    );
    priorTargetQuarter.current = moveScoreCursor(
      cursor,
      targetQuarter,
      priorTargetQuarter.current,
    );
  }, [
    alignment,
    inspectionSample,
    renderVersion,
    scoreHorizonSample,
  ]);

  return (
    <div className="score-paper rendered">
      <div ref={target} aria-label="Rendered committed MusicXML score" />
      {error && <p className="score-render-error" role="status">{error}</p>}
    </div>
  );
}

export function PerformanceViews({
  session,
  events,
  horizon,
  inspectionSample,
  showRoll,
  showKeyboard,
  showScore,
  scoreStatus,
  scoreAvailable,
  scoreXml,
  scoreXmlError,
  scoreAlignment,
  scoreAlignmentError,
  scoreHorizonSample,
  audioSources,
  audioUnavailableReason,
  onInspect,
  onGenerateScore,
}: {
  readonly session: Session;
  readonly events: readonly EventRevision[];
  readonly horizon: Horizon | undefined;
  readonly inspectionSample: number | null;
  readonly showRoll: boolean;
  readonly showKeyboard: boolean;
  readonly showScore: boolean;
  readonly scoreStatus: string | null;
  readonly scoreAvailable: boolean;
  readonly scoreXml: string | undefined;
  readonly scoreXmlError: Error | null;
  readonly scoreAlignment: ScoreAlignment | undefined;
  readonly scoreAlignmentError: Error | null;
  readonly scoreHorizonSample: number | undefined;
  readonly audioSources: readonly AudioPlaybackSource[];
  readonly audioUnavailableReason: string;
  readonly onInspect: (sample: number | null) => void;
  readonly onGenerateScore: () => void;
}) {
  return (
    <div className="performance-views">
      <AudioPlayback
        sources={audioSources}
        totalSamples={session.source_frame_count}
        sampleRateHz={session.sample_rate_hz}
        inspectionSample={inspectionSample}
        onInspect={onInspect}
        unavailableReason={audioUnavailableReason}
      />
      {showScore && (
        <ScorePreview
          session={session}
          scoreStatus={scoreStatus}
          scoreAvailable={scoreAvailable}
          scoreXml={scoreXml}
          scoreXmlError={scoreXmlError}
          scoreAlignment={scoreAlignment}
          scoreAlignmentError={scoreAlignmentError}
          scoreHorizonSample={scoreHorizonSample}
          inspectionSample={inspectionSample}
          onGenerate={onGenerateScore}
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
          session={session}
          inspectionSample={inspectionSample}
          onInspect={onInspect}
        />
      )}
    </div>
  );
}
