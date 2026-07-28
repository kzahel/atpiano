import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { SessionTitleEditor } from "../../src/components/session-title-editor.js";
import type { Session } from "../../src/runtime/atpiano-runtime.js";

const session: Session = {
  schema_version: "atpiano.contract.v1",
  workspace_id: "local",
  session_id: "session-title-test",
  status: "complete",
  source: "microphone",
  sample_rate_hz: 48_000,
  source_frame_count: 96_000,
  started_at: "2026-07-28T10:00:00Z",
  completed_at: "2026-07-28T10:00:02Z",
  display_name: "First idea",
  active_capture_id: null,
  current_transcription_run_id: "run-title-test",
  correction_mode: "after-stop",
  correction_profile_id: "profile-title-test",
  correction_reason: null,
  recognized_note_count: 4,
  corrected_note_count: 4,
  available_artifact_kinds: [],
};

describe("session title editor", () => {
  it("queues the latest value when blur follows an in-flight autosave", async () => {
    vi.useFakeTimers();
    let resolveFirst!: () => void;
    const firstSave = new Promise<void>((resolve) => {
      resolveFirst = resolve;
    });
    const saves: string[] = [];
    function Harness() {
      const [current, setCurrent] = useState(session);
      return (
        <SessionTitleEditor
          session={current}
          canEdit
          onSave={async (value) => {
            saves.push(value);
            if (saves.length === 1) await firstSave;
            setCurrent((saved) => ({ ...saved, display_name: value }));
          }}
        />
      );
    }
    render(<Harness />);

    fireEvent.click(
      screen.getByRole("button", { name: "Rename First idea" }),
    );
    const input = screen.getByRole("textbox", { name: "Session name" });
    fireEvent.change(input, { target: { value: "Second idea" } });
    act(() => vi.advanceTimersByTime(700));
    expect(saves).toEqual(["Second idea"]);

    fireEvent.change(input, { target: { value: "Final idea" } });
    fireEvent.blur(input);
    await act(async () => resolveFirst());
    vi.useRealTimers();
    await waitFor(() =>
      expect(saves).toEqual(["Second idea", "Final idea"])
    );
    expect(
      await screen.findByRole("heading", { name: "Final idea" }),
    ).toBeTruthy();
  });
});
