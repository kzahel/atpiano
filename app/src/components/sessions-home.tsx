import { formatClock, formatSessionDate } from "../lib/format.js";
import type { Session } from "../runtime/atpiano-runtime.js";

export function SessionsHome({
  sessions,
  activeSessionId,
  canWrite,
  onNew,
  onSelect,
}: {
  readonly sessions: readonly Session[];
  readonly activeSessionId: string | null;
  readonly canWrite: boolean;
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
          {sessions.map((session) => {
            const active = session.session_id === activeSessionId;
            return (
              <article
                className={`library-session ${active ? "active" : ""}`}
                key={session.session_id}
              >
                <button
                  className="library-session-main"
                  type="button"
                  onClick={() => onSelect(session.session_id)}
                >
                  <span className="library-session-title">
                    <strong>
                      {session.display_name ?? "Untitled performance"}
                    </strong>
                    {active && <i className="live-pill">live</i>}
                  </span>
                  <span className="library-session-meta">
                    {formatSessionDate(session.started_at)}
                    <i aria-hidden="true">·</i>
                    {session.source === "microphone"
                      ? "Microphone"
                      : "Fixture replay"}
                    <i aria-hidden="true">·</i>
                    {formatClock(
                      session.source_frame_count,
                      session.sample_rate_hz,
                    )}
                  </span>
                  <span className="library-session-summary">
                    {session.recognized_note_count} notes
                    <i aria-hidden="true">·</i>
                    {session.corrected_note_count} corrected
                  </span>
                  <span className="library-session-open" aria-hidden="true">
                    Open →
                  </span>
                </button>
              </article>
            );
          })}
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
