import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  formatClock,
  formatSessionDate,
  noteName,
  requestId,
  sessionSourceLabel,
} from "../lib/format.js";
import type {
  AtpianoRuntime,
  EventPage,
  EventRevision,
  Session,
} from "../runtime/atpiano-runtime.js";
import { useRuntime } from "../runtime/runtime-context.js";

type PlayerState = "idle" | "loading" | "ready" | "playing" | "error";

function eventPageOnce(
  runtime: AtpianoRuntime,
  session: Session,
  startSample: number,
  endSample: number,
  signal: AbortSignal,
): Promise<EventPage> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let subscription: ReturnType<AtpianoRuntime["subscribeEvents"]> | null =
      null;
    const finish = (operation: () => void) => {
      if (settled) return;
      settled = true;
      signal.removeEventListener("abort", abort);
      subscription?.close();
      operation();
    };
    const abort = () =>
      finish(() =>
        reject(new DOMException("Preview loading was cancelled.", "AbortError"))
      );
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) {
      abort();
      return;
    }
    try {
      subscription = runtime.subscribeEvents(
        session.workspace_id,
        session.session_id,
        {
          requestId: requestId("session-preview"),
          signal,
          startSample,
          endSample,
          limit: 256,
        },
        {
          next: (page) => finish(() => resolve(page)),
          error: (error) => finish(() => reject(error)),
        },
      );
    } catch (error) {
      finish(() => reject(error));
    }
  });
}

function hasVisibleNote(page: EventPage): boolean {
  return page.items.some(
    (event) =>
      event.kind === "note" &&
      event.pitch !== null &&
      event.lifecycle !== "retracted",
  );
}

function isPageLimitError(error: unknown): boolean {
  return error instanceof Error &&
    error.message.includes("materialized event range exceeds page limit");
}

async function openingEventPage(
  runtime: AtpianoRuntime,
  session: Session,
  endSample: number,
  signal: AbortSignal,
): Promise<EventPage> {
  const search = async (
    start: number,
    end: number,
  ): Promise<EventPage> => {
    try {
      return await eventPageOnce(runtime, session, start, end, signal);
    } catch (error) {
      if (!isPageLimitError(error) || end - start <= 1) throw error;

      const middle = start + Math.floor((end - start) / 2);
      const left = await search(start, middle);
      if (hasVisibleNote(left)) return left;
      return search(middle, end);
    }
  };

  return search(0, endSample);
}

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
}: {
  readonly notes: readonly EventRevision[];
  readonly sampleRateHz: number;
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
    </div>
  );
}

function SessionLibraryRow({
  session,
  active,
  maxEventRangeSamples,
  playingSessionId,
  onPlaying,
  onStopped,
  onSelect,
}: {
  readonly session: Session;
  readonly active: boolean;
  readonly maxEventRangeSamples: number;
  readonly playingSessionId: string | null;
  readonly onPlaying: (sessionId: string) => void;
  readonly onStopped: (sessionId: string) => void;
  readonly onSelect: (sessionId: string) => void;
}) {
  const runtime = useRuntime();
  const [row, setRow] = useState<HTMLElement | null>(null);
  const nearViewport = useNearViewport(row);
  const [playerState, setPlayerState] = useState<PlayerState>("idle");
  const [playerError, setPlayerError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const audio = useRef<HTMLAudioElement | null>(null);
  const audioUrl = useRef<string | null>(null);
  const loadSequence = useRef(0);

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

  useEffect(() => {
    if (
      playingSessionId !== session.session_id &&
      playerState === "playing"
    ) {
      audio.current?.pause();
      setPlayerState("ready");
    }
  }, [playerState, playingSessionId, session.session_id]);

  useEffect(
    () => () => {
      loadSequence.current += 1;
      audio.current?.pause();
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    },
    [],
  );

  const play = async (player: HTMLAudioElement) => {
    try {
      await player.play();
      setPlayerState("playing");
      setPlayerError(null);
      onPlaying(session.session_id);
    } catch (error) {
      setPlayerState("ready");
      setPlayerError(
        error instanceof DOMException && error.name === "NotAllowedError"
          ? "Recording loaded. Press play again to begin."
          : error instanceof Error
            ? error.message
            : String(error),
      );
    }
  };

  const loadAndPlay = async () => {
    const sequence = ++loadSequence.current;
    setPlayerState("loading");
    setPlayerError(null);
    try {
      const artifacts = await runtime.listArtifacts(
        session.workspace_id,
        session.session_id,
        { requestId: requestId("library-audio"), limit: 100 },
      );
      const audioArtifacts = artifacts.items.filter(
        (artifact) => artifact.kind === "audio",
      );
      const artifact =
        audioArtifacts.find((item) => item.media_type === "audio/mpeg") ??
        audioArtifacts[0];
      if (!artifact) {
        throw new Error("This session does not have a playable recording.");
      }
      const content = await runtime.readArtifact(
        session.workspace_id,
        session.session_id,
        artifact.artifact_id,
        { requestId: requestId("library-audio-read") },
      );
      if (sequence !== loadSequence.current) return;

      const url = URL.createObjectURL(
        new Blob([content.bytes], { type: content.access.media_type }),
      );
      const player = document.createElement("audio");
      player.preload = "metadata";
      player.src = url;
      player.addEventListener("timeupdate", () =>
        setElapsed(player.currentTime)
      );
      player.addEventListener("ended", () => {
        setElapsed(0);
        setPlayerState("ready");
        onStopped(session.session_id);
      });
      player.addEventListener("error", () => {
        setPlayerState("error");
        setPlayerError("The recording could not be played.");
        onStopped(session.session_id);
      });
      audio.current = player;
      audioUrl.current = url;
      setPlayerState("ready");
      await play(player);
    } catch (error) {
      if (sequence !== loadSequence.current) return;
      setPlayerState("error");
      setPlayerError(error instanceof Error ? error.message : String(error));
    }
  };

  const togglePlayback = () => {
    const player = audio.current;
    if (playerState === "playing" && player) {
      player.pause();
      setPlayerState("ready");
      onStopped(session.session_id);
    } else if (player) {
      void play(player);
    } else {
      void loadAndPlay();
    }
  };

  const durationSeconds = session.source_frame_count / session.sample_rate_hz;
  const progress = durationSeconds > 0
    ? Math.min(100, (elapsed / durationSeconds) * 100)
    : 0;
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
        {preview.isLoading && session.recognized_note_count > 0 ? (
          <div className="opening-preview loading" aria-label="Loading opening phrase" />
        ) : preview.data ? (
          <OpeningPhrase
            notes={preview.data.items}
            sampleRateHz={session.sample_rate_hz}
          />
        ) : (
          <div className="opening-preview empty">
            {session.recognized_note_count > 0
              ? "Opening preview unavailable"
              : "No notes detected"}
          </div>
        )}

        <div className="library-player">
          <button
            type="button"
            disabled={active || playerState === "loading"}
            aria-label={
              active
                ? `${session.display_name ?? "Session"} is still recording`
                : playerState === "playing"
                  ? `Pause ${session.display_name ?? "session"} recording`
                  : `Play ${session.display_name ?? "session"} recording`
            }
            onClick={togglePlayback}
          >
            <span aria-hidden="true">
              {playerState === "loading"
                ? "…"
                : playerState === "playing"
                  ? "Ⅱ"
                  : "▶"}
            </span>
          </button>
          <span className="library-player-track" aria-hidden="true">
            <i style={{ width: `${progress}%` }} />
          </span>
          <output>
            {active
              ? "Recording"
              : playerState === "loading"
                ? "Loading…"
                : formatClock(
                    elapsed * session.sample_rate_hz,
                    session.sample_rate_hz,
                  )}
          </output>
        </div>

        {(previewError || playerError) && (
          <p className="library-session-error" role="alert">
            {previewError
              ? `Opening preview: ${previewError}`
              : `Playback: ${playerError}`}
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
  const [playingSessionId, setPlayingSessionId] = useState<string | null>(null);

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
              playingSessionId={playingSessionId}
              onPlaying={setPlayingSessionId}
              onStopped={(sessionId) =>
                setPlayingSessionId((current) =>
                  current === sessionId ? null : current
                )}
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
