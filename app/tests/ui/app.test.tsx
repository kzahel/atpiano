import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getByRole("heading", { name: "Detected keys" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Committed score" })).toBeTruthy();

    await user.click(screen.getByText("Piano roll", { selector: "label" }));

    expect(screen.queryByRole("heading", { name: "Piano roll" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Detected keys" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Committed score" })).toBeTruthy();
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
});
