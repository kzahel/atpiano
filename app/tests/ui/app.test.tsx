import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/app.js";
import type { AtpianoRuntime } from "../../src/runtime/atpiano-runtime.js";
import { createFixtureRuntime } from "../../src/runtime/fixture-data.js";
import { RuntimeProvider } from "../../src/runtime/runtime-context.js";
import { useWorkspaceStore } from "../../src/state/workspace-store.js";

function renderApp(runtime: AtpianoRuntime = createFixtureRuntime()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RuntimeProvider runtime={runtime}>
        <App />
      </RuntimeProvider>
    </QueryClientProvider>,
  );
}

describe("shared application", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    useWorkspaceStore.setState({
      selectedSessionId: null,
      newIntent: false,
      showRoll: true,
      showKeyboard: true,
      showScore: true,
      inspectionSample: null,
      captureState: {
        phase: "idle",
        operationId: null,
        capture: null,
        error: null,
      },
    });
  });

  it("shows performance history and independently toggles its views", async () => {
    const user = userEvent.setup();
    renderApp();

    expect(await screen.findByRole("heading", { name: "Morning progression" }))
      .toBeTruthy();
    expect(screen.getByRole("heading", { name: "Piano roll" })).toBeTruthy();
    expect(screen.getByText("Sustain")).toBeTruthy();
    expect(screen.getByText("Soft")).toBeTruthy();
    expect(
      screen.getByLabelText("Model-estimated pedal gestures"),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Detected keys" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Committed score" })).toBeTruthy();
    expect(
      (await screen.findByRole(
        "button",
        { name: "Play recorded audio" },
      )) as HTMLButtonElement,
    ).not.toHaveProperty("disabled", true);

    await user.click(screen.getByText("Piano roll", { selector: "label" }));

    expect(screen.queryByRole("heading", { name: "Piano roll" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Detected keys" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Committed score" })).toBeTruthy();
  });

  it("draws the shared inspection position on the piano roll", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });

    fireEvent.change(screen.getByRole("slider"), {
      target: { value: String(48_000 * 21) },
    });

    const playhead = document.querySelector<HTMLElement>(".roll-playhead");
    expect(playhead).toBeTruthy();
    expect(playhead?.style.left).toBe("50%");
  });

  it("keeps the selected session in the copyable URL", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });
    expect(new URL(window.location.href).searchParams.get("session")).toBe(
      "20260726T100000-abcdef123456",
    );

    await user.click(screen.getByRole("button", { name: /Nocturne sketch/ }));

    await waitFor(() =>
      expect(new URL(window.location.href).searchParams.get("session")).toBe(
        "20260725T201500-bbbbbbbbbbbb",
      ),
    );
  });

  it("enters New without creating history and replay claims the active target", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });

    await user.click(screen.getAllByRole("button", { name: /New session/ })[0]!);
    expect(screen.getByRole("heading", { name: "What would you like to play?" }))
      .toBeTruthy();
    expect(screen.getAllByRole("button", { name: /Morning progression/ })).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: /Replay musical fixture/ }));

    expect(await screen.findByText("Listening and correcting")).toBeTruthy();
    expect(
      await screen.findByRole("heading", { name: "Morning progression" }),
    ).toBeTruthy();
  });

  it("deletes only the explicitly selected historical session", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });

    await user.click(screen.getByRole("button", { name: /Nocturne sketch/ }));
    expect(await screen.findByRole("heading", { name: "Nocturne sketch" }))
      .toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Delete session" }));

    expect(await screen.findByText(/moved to recoverable trash/)).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /Nocturne sketch/ })).toBeNull();
    });
    expect(screen.getByRole("button", { name: /Morning progression/ })).toBeTruthy();
  });

  it("isolates a failed score job from session review", async () => {
    const user = userEvent.setup();
    const fixture = createFixtureRuntime();
    const runtime = new Proxy(fixture, {
      get(target, property) {
        if (property === "startScoreJob") {
          return async () => {
            throw new Error("Score runtime unavailable");
          };
        }
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) satisfies AtpianoRuntime;
    renderApp(runtime);
    expect(await screen.findByRole("heading", { name: "Morning progression" }))
      .toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Refresh score" }));

    expect(await screen.findByText("Score runtime unavailable")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Morning progression" }))
      .toBeTruthy();
    expect(screen.getByRole("heading", { name: "Piano roll" })).toBeTruthy();
  });

  it("leaves rendering state when score-job polling fails", async () => {
    const user = userEvent.setup();
    const fixture = createFixtureRuntime();
    const runtime = new Proxy(fixture, {
      get(target, property) {
        if (property === "startScoreJob") {
          return async (
            ...args: Parameters<AtpianoRuntime["startScoreJob"]>
          ) => {
            const job = await target.startScoreJob(...args);
            return {
              ...job,
              status: "running" as const,
              completed_at: null,
              artifact_ids: [],
              error: null,
            };
          };
        }
        if (property === "getJob") {
          return async () => {
            throw new Error("Score job status unavailable");
          };
        }
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) satisfies AtpianoRuntime;
    renderApp(runtime);
    expect(await screen.findByRole("heading", { name: "Morning progression" }))
      .toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Refresh score" }));

    expect(await screen.findByText("Score job status unavailable")).toBeTruthy();
    expect(
      screen.getByText("Score rendering failed. Your performance is still safe."),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Refresh score" }),
    ).not.toHaveProperty("disabled", true);
  });

  it("subscribes through the live audio head before the session snapshot advances", async () => {
    const fixture = createFixtureRuntime();
    let subscribedThrough = 0;
    const runtime = new Proxy(fixture, {
      get(target, property) {
        if (property === "listSessions") {
          return async (...args: Parameters<AtpianoRuntime["listSessions"]>) => {
            const page = await target.listSessions(...args);
            return {
              ...page,
              items: page.items.map((session, index) =>
                index === 0
                  ? { ...session, status: "active" as const, source_frame_count: 0 }
                  : session,
              ),
            };
          };
        }
        if (property === "getSession") {
          return async (...args: Parameters<AtpianoRuntime["getSession"]>) => {
            const session = await target.getSession(...args);
            return { ...session, status: "active" as const, source_frame_count: 0 };
          };
        }
        if (property === "getHorizon") {
          return async (...args: Parameters<AtpianoRuntime["getHorizon"]>) => {
            const horizon = await target.getHorizon(...args);
            return {
              ...horizon,
              audio_head_sample: 96_000,
              provisional_sample: 84_000,
              commit_sample: 72_000,
            };
          };
        }
        if (property === "subscribeEvents") {
          return (...args: Parameters<AtpianoRuntime["subscribeEvents"]>) => {
            subscribedThrough = args[2].endSample;
            return target.subscribeEvents(...args);
          };
        }
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) satisfies AtpianoRuntime;

    renderApp(runtime);

    await waitFor(() => expect(subscribedThrough).toBe(96_000));
    expect(screen.getAllByText("00:02.0").length).toBeGreaterThan(0);
  });
});
