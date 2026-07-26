import { useEffect, useMemo, useRef, useState } from "react";

import { formatClock, noteName } from "../lib/format.js";
import { pianoLayout } from "../lib/piano-layout.js";
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
      <label className="inspection-control">
        <span>
          Inspect source time
          <output>{formatClock(sample, session.sample_rate_hz)}</output>
        </span>
        <input
          type="range"
          min={0}
          max={session.source_frame_count}
          value={sample}
          step={Math.max(1, Math.round(session.sample_rate_hz / 100))}
          onChange={(event) => onInspect(Number(event.currentTarget.value))}
        />
      </label>
      {inspectionSample !== null && (
        <button className="text-button" type="button" onClick={() => onInspect(null)}>
          Follow latest attack
        </button>
      )}
    </section>
  );
}

function PianoRoll({
  events,
  session,
  horizon,
  onInspect,
}: {
  readonly events: readonly EventRevision[];
  readonly session: Session;
  readonly horizon: Horizon | undefined;
  readonly onInspect: (sample: number) => void;
}) {
  const total = Math.max(1, session.source_frame_count);
  const notes = events.filter(
    (event) => event.kind === "note" && event.pitch !== null,
  );
  const pedals = events.filter((event) => event.kind !== "note");
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
            const end = note.offset_sample ?? total;
            return (
              <i
                key={`${note.event_id}:${note.revision}`}
                className={`roll-note ${note.lifecycle}`}
                title={`${noteName(note.pitch!)} at ${formatClock(note.onset_sample, session.sample_rate_hz)}`}
                style={{
                  left: `${(note.onset_sample / total) * 100}%`,
                  width: `${Math.max(0.35, ((end - note.onset_sample) / total) * 100)}%`,
                  top: `${((108 - note.pitch!) / 87) * 100}%`,
                }}
              />
            );
          })}
          {horizon && (
            <i
              className="commit-line"
              style={{ left: `${(horizon.commit_sample / total) * 100}%` }}
            />
          )}
        </div>
        <div className="pedal-track">
          <span>SUSTAIN</span>
          {pedals.map((pedal) => (
            <i
              key={`${pedal.event_id}:${pedal.revision}`}
              style={{
                left: `${(pedal.onset_sample / total) * 100}%`,
                width: `${(((pedal.offset_sample ?? total) - pedal.onset_sample) / total) * 100}%`,
              }}
            />
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
  events,
  session,
  scoreStatus,
  scoreAvailable,
  scoreXml,
  scoreXmlError,
  onGenerate,
}: {
  readonly events: readonly EventRevision[];
  readonly session: Session;
  readonly scoreStatus: string | null;
  readonly scoreAvailable: boolean;
  readonly scoreXml: string | undefined;
  readonly scoreXmlError: Error | null;
  readonly onGenerate: () => void;
}) {
  const notes = events
    .filter(
      (event) =>
        event.kind === "note" &&
        event.pitch !== null &&
        event.lifecycle === "committed",
    )
    .slice(0, 14);
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
          {scoreStatus === "complete" ? "Refresh score" : "Render committed score"}
        </button>
      </div>
      <p className={`score-state ${scoreStatus ?? "idle"}`}>
        {!scoreAvailable
          ? "Score runtime is not installed. Capture and review remain available."
          : scoreStatus === "running"
            ? "Rendering the frozen committed prefix…"
            : scoreStatus === "failed"
              ? "Score rendering failed. Your performance is still safe."
              : scoreStatus === "complete"
                ? "Score snapshot is current for the committed horizon."
                : "Only closed corrected notes enter this snapshot."}
      </p>
      {scoreXml ? (
        <MusicXmlScore xml={scoreXml} />
      ) : (
        <div className="score-paper" aria-label="Orientation preview of committed notes">
          <div className="staff-lines" aria-hidden="true" />
          <strong className="treble-clef" aria-hidden="true">𝄞</strong>
          {notes.map((note, index) => (
            <i
              key={note.event_id}
              className="score-note"
              style={{
                left: `${13 + index * (78 / Math.max(1, notes.length))}%`,
                bottom: `${34 + ((note.pitch! - 48) % 18) * 2.2}%`,
              }}
            >
              ●
            </i>
          ))}
          {!notes.length && <span>Corrected notes will appear here.</span>}
        </div>
      )}
      {scoreXmlError && (
        <p className="score-render-error" role="status">
          The notation preview could not load. The MusicXML download remains
          available.
        </p>
      )}
      <small>
        Snapshot target · {session.display_name ?? session.session_id}
      </small>
    </section>
  );
}

function MusicXmlScore({ xml }: { readonly xml: string }) {
  const target = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = target.current;
    if (!container) return;
    let cancelled = false;
    let renderer: { clear(): void } | null = null;
    setError(null);
    void import("opensheetmusicdisplay")
      .then(async ({ OpenSheetMusicDisplay }) => {
        if (cancelled) return;
        const next = new OpenSheetMusicDisplay(container, {
          autoResize: true,
          backend: "svg",
          drawTitle: false,
          drawingParameters: "compacttight",
        });
        renderer = next;
        await next.load(xml);
        if (!cancelled) next.render();
      })
      .catch(() => {
        if (!cancelled) setError("Notation rendering failed.");
      });
    return () => {
      cancelled = true;
      renderer?.clear();
      container.replaceChildren();
    };
  }, [xml]);

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
  readonly onInspect: (sample: number | null) => void;
  readonly onGenerateScore: () => void;
}) {
  return (
    <div className="performance-views">
      {showScore && (
        <ScorePreview
          events={events}
          session={session}
          scoreStatus={scoreStatus}
          scoreAvailable={scoreAvailable}
          scoreXml={scoreXml}
          scoreXmlError={scoreXmlError}
          onGenerate={onGenerateScore}
        />
      )}
      {showRoll && (
        <PianoRoll
          events={events}
          session={session}
          horizon={horizon}
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
