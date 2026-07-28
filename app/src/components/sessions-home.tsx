import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { usePlaybackControls } from "./playback-provider.js";
import {
  formatClock,
  formatSessionDate,
  noteName,
  sessionSourceLabel,
} from "../lib/format.js";
import { openingEventPage } from "../lib/opening-event-page.js";
import type {
  EventRevision,
  Session,
} from "../runtime/atpiano-runtime.js";
import { useRuntime } from "../runtime/runtime-context.js";
import { usePlaybackStore } from "../state/playback-store.js";

function useNearViewport(element: HTMLElement | null): boolean {
  const [nearViewport, setNearViewport] = useState(false);

  useEffect(() => {
    if (!element) return;
    if (!("IntersectionObserver" in window)) {
      setNearViewport(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNearViewport(true);
          observer.disconnect();
        }
      },
      { rootMargin: "220px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);

  return nearViewport;
}

function OpeningPhrase({
  notes,
  sampleRateHz,
  playbackSample,
}: {
  readonly notes: readonly EventRevision[];
  readonly sampleRateHz: number;
  readonly playbackSample: number | null;
}) {
  const phrase = useMemo(() => {
    const pitched = notes
      .filter(
        (event) =>
          event.kind === "note" &&
          event.pitch !== null &&
          event.lifecycle !== "retracted",
      )
      .sort(
        (left, right) =>
          left.onset_sample - right.onset_sample ||
          left.pitch! - right.pitch!,
      );
    const first = pitched[0]?.onset_sample;
    if (first === undefined) return null;
    const end = first + sampleRateHz * 8;
    const visible = pitched.filter((event) => event.onset_sample < end);
    const pitches = visible.map((event) => event.pitch!);
    return {
      start: first,
      end,
      minPitch: Math.max(21, Math.min(...pitches) - 2),
      maxPitch: Math.min(108, Math.max(...pitches) + 2),
      notes: visible,
    };
  }, [notes, sampleRateHz]);

  if (!phrase) {
    return <div className="opening-preview empty">No opening notes found</div>;
  }

  const pitchRange = Math.max(1, phrase.maxPitch - phrase.minPitch);
  const sampleRange = phrase.end - phrase.start;
  const playhead =
    playbackSample !== null &&
    playbackSample >= phrase.start &&
    playbackSample <= phrase.end
      ? ((playbackSample - phrase.start) / sampleRange) * 100
      : null;
  return (
    <div
      className="opening-preview"
      role="img"
      aria-label={`Opening phrase with ${phrase.notes.length} notes`}
    >
      {phrase.notes.map((note) => {
        const end = Math.min(
          phrase.end,
          Math.max(
            note.onset_sample + sampleRateHz * 0.09,
            note.offset_sample ?? note.onset_sample + sampleRateHz * 0.22,
          ),
        );
        return (
          <i
            key={`${note.event_id}:${note.revision}`}
            title={noteName(note.pitch!)}
            style={{
              left: `${((note.onset_sample - phrase.start) / sampleRange) * 100}%`,
              top: `${((phrase.maxPitch - note.pitch!) / pitchRange) * 100}%`,
              width: `${Math.max(0.7, ((end - note.onset_sample) / sampleRange) * 100)}%`,
            }}
          />
        );
      })}
      {playhead !== null && (
        <span
          className="opening-preview-playhead"
          aria-hidden="true"
          style={{ left: `${playhead}%` }}
        />
      )}
    </div>
  );
}

function SessionLibraryRow({
  session,
  active,
  maxEventRangeSamples,
  onSelect,
}: {
  readonly session: Session;
  readonly active: boolean;
  readonly maxEventRangeSamples: number;
  readonly onSelect: (sessionId: string) => void;
}) {
  const runtime = useRuntime();
  const controls = usePlaybackControls();
  const [row, setRow] = useState<HTMLElement | null>(null);
  const nearViewport = useNearViewport(row);
  const playbackSessionId = usePlaybackStore((state) => state.sessionId);
  const playbackAvailable = usePlaybackStore((state) => state.available);
  const playbackStatus = usePlaybackStore((state) => state.status);
  const playbackSample = usePlaybackStore((state) => state.positionSample);
  const playbackError = usePlaybackStore((state) => state.error);
  const current = playbackSessionId === session.session_id;
  const playing = current && playbackStatus === "playing";
  const loading =
    current &&
    !playbackAvailable &&
    playbackStatus !== "error" &&
    !active;

  const preview = useQuery({
    queryKey: [
      "session-opening-preview",
      session.workspace_id,
      session.session_id,
      session.source_frame_count,
    ],
    queryFn: ({ signal }) =>
      openingEventPage(
        runtime,
        session,
        Math.max(
          1,
          Math.min(session.source_frame_count, maxEventRangeSamples),
        ),
        signal,
      ),
    enabled: nearViewport && session.recognized_note_count > 0,
    staleTime: Infinity,
  });

  const togglePlayback = () => {
    if (playing) controls.pause();
    else controls.playSession(session.session_id);
  };

  const elapsedSample = current ? playbackSample : 0;
  const previewError = preview.error instanceof Error
    ? preview.error.message
    : preview.error
      ? String(preview.error)
      : null;

  return (
    <article
      className={`library-session ${active ? "active" : ""}`}
      ref={setRow}
    >
      <button
        className="library-session-main"
        type="button"
        onClick={() => onSelect(session.session_id)}
      >
        <span className="library-session-title">
          <strong>{session.display_name ?? "Untitled performance"}</strong>
          {active && <i className="live-pill">live</i>}
        </span>
        <span className="library-session-meta">
          {formatSessionDate(session.started_at)}
          <i aria-hidden="true">·</i>
          {sessionSourceLabel(session.source)}
          <i aria-hidden="true">·</i>
          {formatClock(session.source_frame_count, session.sample_rate_hz)}
        </span>
        <span className="library-session-summary">
          {session.recognized_note_count} notes
          <i aria-hidden="true">·</i>
          {session.corrected_note_count} corrected
        </span>
        <span className="library-session-open" aria-hidden="true">Open →</span>
      </button>

      <div className="library-session-preview">
        <button
          className="opening-preview-link"
          type="button"
          aria-label={
            `Open ${session.display_name ?? "session"} from its piano roll`
          }
          onClick={() => onSelect(session.session_id)}
        >
          {preview.isLoading && session.recognized_note_count > 0 ? (
            <div
              className="opening-preview loading"
              aria-label="Loading opening phrase"
            />
          ) : preview.data ? (
            <OpeningPhrase
              notes={preview.data.items}
              sampleRateHz={session.sample_rate_hz}
              playbackSample={current ? playbackSample : null}
            />
          ) : (
            <div className="opening-preview empty">
              {session.recognized_note_count > 0
                ? "Opening preview unavailable"
                : "No notes detected"}
            </div>
          )}
        </button>

        <div className="library-player">
          <button
            type="button"
            disabled={active || loading}
            aria-label={
              active
                ? `${session.display_name ?? "Session"} is still recording`
                : playing
                  ? `Pause ${session.display_name ?? "session"} recording`
                  : `Play ${session.display_name ?? "session"} recording`
            }
            onClick={togglePlayback}
          >
            <span aria-hidden="true">
              {loading
                ? "…"
                : playing
                  ? "Ⅱ"
                  : "▶"}
            </span>
          </button>
          <label className="library-player-track">
            <span className="sr-only">
              Seek {session.display_name ?? "session"} recording
            </span>
            <input
              type="range"
              min={0}
              max={Math.max(1, session.source_frame_count)}
              step={Math.max(
                1,
                Math.round(session.sample_rate_hz / 20),
              )}
              value={elapsedSample}
              disabled={active || loading}
              onChange={(event) =>
                controls.seekSession(
                  session.session_id,
                  Number(event.currentTarget.value),
                )}
            />
          </label>
          <output>
            {active
              ? "Recording"
              : loading
                ? "Loading…"
                : (
                  <>
                    {formatClock(elapsedSample, session.sample_rate_hz)}
                    <span aria-hidden="true"> / </span>
                    <span className="sr-only"> of </span>
                    {formatClock(
                      session.source_frame_count,
                      session.sample_rate_hz,
                    )}
                  </>
                )}
          </output>
        </div>

        {(previewError || (current && playbackError)) && (
          <p className="library-session-error" role="alert">
            {previewError
              ? `Opening preview: ${previewError}`
              : `Playback: ${playbackError}`}
          </p>
        )}
      </div>
    </article>
  );
}

export function SessionsHome({
  sessions,
  activeSessionId,
  canWrite,
  maxEventRangeSamples,
  onNew,
  onSelect,
}: {
  readonly sessions: readonly Session[];
  readonly activeSessionId: string | null;
  readonly canWrite: boolean;
  readonly maxEventRangeSamples: number;
  readonly onNew: () => void;
  readonly onSelect: (sessionId: string) => void;
}) {
  return (
    <section className="sessions-home" aria-labelledby="sessions-title">
      <header className="sessions-home-heading">
        <div>
          <p className="eyebrow">Your musical notebook</p>
          <h1 id="sessions-title">Sessions</h1>
          <p>Listen again, inspect what the piano played, or begin a new idea.</p>
        </div>
        {canWrite && (
          <button className="button primary" type="button" onClick={onNew}>
            New session
          </button>
        )}
      </header>

      {sessions.length ? (
        <div className="session-library-list">
          {sessions.map((session) => (
            <SessionLibraryRow
              key={session.session_id}
              session={session}
              active={session.session_id === activeSessionId}
              maxEventRangeSamples={maxEventRangeSamples}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : (
        <div className="sessions-empty">
          <span aria-hidden="true">♪</span>
          <h2>No sessions yet</h2>
          <p>Your recorded performances will collect here.</p>
          {canWrite && (
            <button className="button primary" type="button" onClick={onNew}>
              Create a new session
            </button>
          )}
        </div>
      )}
    </section>
  );
}
