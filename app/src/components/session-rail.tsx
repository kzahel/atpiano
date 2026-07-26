import type { Session, Workspace } from "../runtime/atpiano-runtime.js";
import { formatClock, formatSessionDate } from "../lib/format.js";

export function SessionRail({
  workspace,
  sessions,
  selectedSessionId,
  activeSessionId,
  newIntent,
  onNew,
  onSelect,
}: {
  readonly workspace: Workspace | undefined;
  readonly sessions: readonly Session[];
  readonly selectedSessionId: string | null;
  readonly activeSessionId: string | null;
  readonly newIntent: boolean;
  readonly onNew: () => void;
  readonly onSelect: (sessionId: string) => void;
}) {
  return (
    <aside className="session-rail" aria-label="Session history">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">A</span>
        <div>
          <strong>atpiano</strong>
          <small>{workspace?.name ?? "Connecting…"}</small>
        </div>
      </div>

      <button
        className={`new-session ${newIntent ? "selected" : ""}`}
        type="button"
        onClick={onNew}
      >
        <span aria-hidden="true">＋</span>
        New session
      </button>

      <div className="history-heading">
        <span>Recent performances</span>
        <span>{sessions.length}</span>
      </div>
      <nav className="session-list">
        {sessions.map((session) => {
          const selected = session.session_id === selectedSessionId;
          const active = session.session_id === activeSessionId;
          return (
            <button
              className={`session-item ${selected ? "selected" : ""}`}
              key={session.session_id}
              type="button"
              aria-current={selected ? "page" : undefined}
              onClick={() => onSelect(session.session_id)}
            >
              <span className="session-item-top">
                <strong>{session.display_name ?? formatSessionDate(session.started_at)}</strong>
                {active && <i className="live-pill">live</i>}
              </span>
              <span className="session-meta">
                {formatSessionDate(session.started_at)}
                <i>·</i>
                {formatClock(session.source_frame_count, session.sample_rate_hz)}
              </span>
              <span className="session-source">
                {session.source === "microphone" ? "Microphone" : "Fixture replay"}
                <i className={`status-pin ${session.status}`} aria-hidden="true" />
              </span>
            </button>
          );
        })}
      </nav>
      <p className="rail-note">
        Stored locally
        <span>Audio never leaves this runtime.</span>
      </p>
    </aside>
  );
}
