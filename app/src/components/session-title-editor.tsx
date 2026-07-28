import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import type { Session } from "../runtime/atpiano-runtime.js";

type SaveState = "idle" | "saving" | "saved" | "error";

export function SessionTitleEditor({
  session,
  canEdit,
  onSave,
}: {
  readonly session: Session;
  readonly canEdit: boolean;
  readonly onSave: (displayName: string) => Promise<void>;
}) {
  const persisted = session.display_name ?? "Untitled performance";
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(persisted);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const saveSequence = useRef(0);

  useEffect(() => {
    if (!editing) setValue(persisted);
  }, [editing, persisted, session.session_id]);

  const save = async (exitAfterSave: boolean) => {
    const normalized = value.trim();
    if (!normalized) {
      setSaveState("error");
      setError("Enter a session name.");
      return;
    }
    if (normalized.length > 200) {
      setSaveState("error");
      setError("Session names can contain at most 200 characters.");
      return;
    }
    if (normalized === persisted) {
      setSaveState("idle");
      setError(null);
      if (exitAfterSave) setEditing(false);
      return;
    }
    const sequence = ++saveSequence.current;
    setSaveState("saving");
    setError(null);
    try {
      await onSave(normalized);
      if (sequence !== saveSequence.current) return;
      setValue(normalized);
      setSaveState("saved");
      if (exitAfterSave) setEditing(false);
    } catch (reason) {
      if (sequence !== saveSequence.current) return;
      setSaveState("error");
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  useEffect(() => {
    if (!editing || value.trim() === persisted || saveState === "saving") {
      return;
    }
    const timer = window.setTimeout(() => {
      void save(false);
    }, 700);
    return () => window.clearTimeout(timer);
  }, [editing, persisted, value]);

  useEffect(() => {
    if (saveState !== "saved") return;
    const timer = window.setTimeout(() => setSaveState("idle"), 1_800);
    return () => window.clearTimeout(timer);
  }, [saveState]);

  const cancel = () => {
    saveSequence.current += 1;
    setValue(persisted);
    setSaveState("idle");
    setError(null);
    setEditing(false);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      cancel();
    } else if (event.key === "Enter") {
      event.preventDefault();
      void save(true);
    }
  };

  if (!editing) {
    return (
      <div className="session-name">
        <h1>{persisted}</h1>
        {canEdit && (
          <button
            className="rename-trigger"
            type="button"
            aria-label={`Rename ${persisted}`}
            onClick={() => {
              setValue(persisted);
              setEditing(true);
            }}
          >
            <span aria-hidden="true">✎</span>
          </button>
        )}
        {saveState === "saved" && (
          <span className="save-state saved" role="status">Saved ✓</span>
        )}
      </div>
    );
  }

  return (
    <div className="session-name editing">
      <label>
        <span className="sr-only">Session name</span>
        <input
          autoFocus
          value={value}
          maxLength={200}
          onChange={(event) => {
            setValue(event.currentTarget.value);
            setSaveState("idle");
            setError(null);
          }}
          onKeyDown={handleKeyDown}
          onBlur={() => void save(true)}
        />
      </label>
      <span
        className={`save-state ${saveState}`}
        role={saveState === "error" ? "alert" : "status"}
      >
        {saveState === "saving"
          ? "Saving…"
          : saveState === "saved"
            ? "Saved ✓"
            : error ?? "Autosaves as you type"}
      </span>
      {saveState === "error" && (
        <button
          className="text-button"
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => void save(false)}
        >
          Retry
        </button>
      )}
    </div>
  );
}
