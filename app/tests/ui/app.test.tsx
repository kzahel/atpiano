import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/app.js";
import type { AtpianoRuntime } from "../../src/runtime/atpiano-runtime.js";
import { createFixtureRuntime } from "../../src/runtime/fixture-data.js";
import { RuntimeProvider } from "../../src/runtime/runtime-context.js";
import {
  resetPlaybackStore,
  usePlaybackStore,
} from "../../src/state/playback-store.js";
import { useWorkspaceStore } from "../../src/state/workspace-store.js";

function renderApp(
  runtime: AtpianoRuntime = createFixtureRuntime(),
  options: { readonly home?: boolean } = {},
) {
  if (
    !options.home &&
    new URL(window.location.href).searchParams.get("session") === null
  ) {
    window.history.replaceState(
      null,
      "",
      "/?session=20260726T100000-abcdef123456",
    );
  }
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
    window.localStorage.removeItem("atpiano.score-reader-density");
    resetPlaybackStore();
    useWorkspaceStore.setState({
      selectedSessionId: null,
      libraryIntent: true,
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

  it("uses the session library as the homepage", async () => {
    renderApp(createFixtureRuntime(), { home: true });

    expect(await screen.findByRole("heading", { name: "Sessions" }))
      .toBeTruthy();
    expect(screen.getByText("Your musical notebook")).toBeTruthy();
    await screen.findAllByText("Morning progression");
    expect(document.querySelectorAll(".library-session-main")).toHaveLength(3);
    expect(screen.queryByText("Schema v1")).toBeNull();
    expect(screen.queryByText("Local engine")).toBeNull();
    expect(screen.queryByText("On this device")).toBeNull();
    expect(new URL(window.location.href).searchParams.get("session")).toBeNull();
  });

  it("imports a WAV as a product session without showing replay controls", async () => {
    const user = userEvent.setup();
    const fixture = createFixtureRuntime();
    const importRecording = vi.spyOn(fixture, "importRecording");
    renderApp(fixture, { home: true });
    await user.click(
      await screen.findByRole("button", { name: "New session" }),
    );
    const file = new File(["wav bytes"], "Sunday chords.wav", {
      type: "audio/wav",
    });

    await user.upload(
      screen.getByLabelText("Choose WAV or MP3 recording"),
      file,
    );

    await waitFor(() => expect(importRecording).toHaveBeenCalledOnce());
    expect(
      screen.queryByRole("button", { name: "Replay musical fixture" }),
    ).toBeNull();
    expect(
      screen.queryByText(/fixture replay/i),
    ).toBeNull();
    expect(
      await screen.findByRole("heading", { name: "Sunday chords" }),
    ).toBeTruthy();
  });

  it("returns to Sessions from the atpiano brand", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });

    await user.click(
      screen.getByRole("button", { name: "Atpiano Sessions home" }),
    );

    expect(await screen.findByRole("heading", { name: "Sessions" }))
      .toBeTruthy();
    expect(new URL(window.location.href).searchParams.get("session")).toBeNull();
  });

  it("loads only nearby previews and recordings only on play", async () => {
    const user = userEvent.setup();
    const fixture = createFixtureRuntime();
    const intersectionCallbacks: IntersectionObserverCallback[] = [];
    class TestIntersectionObserver {
      constructor(callback: IntersectionObserverCallback) {
        intersectionCallbacks.push(callback);
      }
      observe() {}
      disconnect() {}
      unobserve() {}
      takeRecords(): IntersectionObserverEntry[] {
        return [];
      }
    }
    vi.stubGlobal("IntersectionObserver", TestIntersectionObserver);
    const previewSessions: string[] = [];
    const artifactSessions: string[] = [];
    const readSessions: string[] = [];
    const primarySessionId = "20260726T100000-abcdef123456";
    const runtime = new Proxy(fixture, {
      get(target, property) {
        if (property === "subscribeEvents") {
          return (
            ...args: Parameters<AtpianoRuntime["subscribeEvents"]>
          ) => {
            previewSessions.push(args[1]);
            return target.subscribeEvents(...args);
          };
        }
        if (property === "listArtifacts") {
          return async (
            workspaceId: string,
            sessionId: string,
            request: Parameters<AtpianoRuntime["listArtifacts"]>[2],
          ) => {
            artifactSessions.push(sessionId);
            return target.listArtifacts(
              workspaceId,
              primarySessionId,
              request,
            );
          };
        }
        if (property === "readArtifact") {
          return async (
            workspaceId: string,
            sessionId: string,
            _artifactId: string,
            request: Parameters<AtpianoRuntime["readArtifact"]>[3],
          ) => {
            readSessions.push(sessionId);
            return target.readArtifact(
              workspaceId,
              primarySessionId,
              `artifact:${primarySessionId}:audio`,
              request,
            );
          };
        }
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) satisfies AtpianoRuntime;
    const play = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockResolvedValue();
    const pause = vi
      .spyOn(HTMLMediaElement.prototype, "pause")
      .mockImplementation(() => undefined);

    renderApp(runtime, { home: true });

    await waitFor(() => expect(intersectionCallbacks).toHaveLength(3));
    expect(previewSessions).toEqual([]);
    act(() => {
      intersectionCallbacks[0]!([
        { isIntersecting: true } as IntersectionObserverEntry,
      ], {} as IntersectionObserver);
    });
    await waitFor(() => expect(previewSessions).toHaveLength(1));
    act(() => {
      intersectionCallbacks.slice(1).forEach((callback) =>
        callback(
          [{ isIntersecting: true } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        )
      );
    });
    await waitFor(() => expect(previewSessions).toHaveLength(3));
    await waitFor(() =>
      expect(
        screen.getAllByRole("img", {
          name: /Opening phrase with \d+ notes/,
        }),
      ).toHaveLength(3)
    );
    expect(artifactSessions).toEqual([]);
    expect(readSessions).toEqual([]);

    await user.click(
      screen.getByRole("button", {
        name: "Play Morning progression recording",
      }),
    );
    expect(
      await screen.findByRole("button", {
        name: "Pause Morning progression recording",
      }),
    ).toBeTruthy();
    expect(artifactSessions).toEqual([primarySessionId]);
    expect(readSessions).toEqual([primarySessionId]);

    const nocturneId = "20260725T201500-bbbbbbbbbbbb";
    await user.click(
      screen.getByRole("button", {
        name: "Play Nocturne sketch recording",
      }),
    );
    expect(
      await screen.findByRole("button", {
        name: "Pause Nocturne sketch recording",
      }),
    ).toBeTruthy();
    expect(play).toHaveBeenCalledTimes(2);
    expect(artifactSessions).toEqual([primarySessionId, nocturneId]);
    expect(readSessions).toEqual([primarySessionId, nocturneId]);
    expect(pause).toHaveBeenCalled();
  });

  it("subdivides dense opening ranges instead of exposing page limits", async () => {
    const fixture = createFixtureRuntime();
    const denseSessionId = "20260726T100000-abcdef123456";
    const rejectedRanges: Array<[number, number]> = [];
    const runtime = new Proxy(fixture, {
      get(target, property) {
        if (property === "subscribeEvents") {
          return (
            ...args: Parameters<AtpianoRuntime["subscribeEvents"]>
          ) => {
            const [, sessionId, range, subscriber] = args;
            if (
              sessionId === denseSessionId &&
              range.endSample - range.startSample > 48_000 * 20
            ) {
              rejectedRanges.push([range.startSample, range.endSample]);
              let closed = false;
              queueMicrotask(() => {
                if (!closed) {
                  subscriber.error(
                    new Error(
                      "materialized event range exceeds page limit",
                    ),
                  );
                }
              });
              return {
                close() {
                  closed = true;
                },
              };
            }
            return target.subscribeEvents(...args);
          };
        }
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) satisfies AtpianoRuntime;

    renderApp(runtime, { home: true });

    await waitFor(() =>
      expect(
        screen.getAllByRole("img", {
          name: /Opening phrase with \d+ notes/,
        }),
      ).toHaveLength(3)
    );
    expect(rejectedRanges).toHaveLength(2);
    expect(screen.queryByText(/exceeds page limit/)).toBeNull();
  });

  it("renames a session inline and shows save completion", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });

    await user.click(
      screen.getByRole("button", { name: "Rename Morning progression" }),
    );
    const input = screen.getByRole("textbox", { name: "Session name" });
    await user.clear(input);
    await user.type(input, "Sunday invention{Enter}");

    expect(
      await screen.findByRole("heading", { name: "Sunday invention" }),
    ).toBeTruthy();
    expect(await screen.findByText("Saved ✓")).toBeTruthy();
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
      await screen.findByRole("button", {
        name: "Enharmonic key · Six sharps",
      }),
    ).toBeTruthy();
    expect(screen.getByLabelText("Engraving")).toBeTruthy();
    expect(
      await screen.findByRole("button", { name: /Original model MusicXML/ }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Download model baseline" }),
    ).toBeNull();
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

  it("detaches score follow without interrupting playback", async () => {
    const user = userEvent.setup();
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    renderApp();

    await screen.findByLabelText("Rendered committed MusicXML score");
    const play = await screen.findByRole("button", {
      name: "Play recorded audio",
    });
    await waitFor(() =>
      expect((play as HTMLButtonElement).disabled).toBe(false)
    );
    await user.click(play);
    expect(usePlaybackStore.getState().status).toBe("playing");
    expect(usePlaybackStore.getState().scoreFollow).toBe("following");

    fireEvent.wheel(window);

    expect(usePlaybackStore.getState().scoreFollow).toBe("detached");
    await screen.findByRole("button", {
      name: "Follow playback",
    });
    await user.click(
      screen.getByRole("button", { name: "Pause recorded audio" }),
    );
    expect(usePlaybackStore.getState().status).toBe("paused");
    expect(usePlaybackStore.getState().scoreFollow).toBe("detached");
    await user.click(
      screen.getByRole("button", { name: "Play recorded audio" }),
    );
    expect(usePlaybackStore.getState().scoreFollow).toBe("detached");

    await user.click(
      screen.getByRole("button", { name: "Follow playback" }),
    );

    expect(usePlaybackStore.getState().scoreFollow).toBe("following");
    expect(
      screen.queryByRole("button", { name: "Follow playback" }),
    ).toBeNull();
  });

  it("exports the model baseline through the shared runtime operation", async () => {
    const user = userEvent.setup();
    const fixture = createFixtureRuntime();
    const exported: string[] = [];
    const runtime = new Proxy(fixture, {
      get(target, property) {
        if (property === "exportArtifact") {
          return async (
            _workspaceId: string,
            _sessionId: string,
            artifactId: string,
          ) => {
            exported.push(artifactId);
            return {
              outcome: "download-started" as const,
              fileName: "score.musicxml",
            };
          };
        }
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) satisfies AtpianoRuntime;
    renderApp(runtime);

    await user.click(
      await screen.findByRole("button", { name: /Original model MusicXML/ }),
    );

    expect(exported).toEqual([
      "artifact:20260726T100000-abcdef123456:musicxml",
    ]);
    expect(await screen.findByText("Downloading score.musicxml…")).toBeTruthy();
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

  it("opens mobile session history and closes it after navigation", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });

    const trigger = screen.getByRole("button", { name: "Sessions" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");

    await user.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(document.querySelector(".session-rail")?.classList).toContain(
      "mobile-open",
    );

    await user.click(screen.getByRole("button", { name: /Nocturne sketch/ }));

    expect(await screen.findByRole("heading", { name: "Nocturne sketch" }))
      .toBeTruthy();
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(document.querySelector(".session-rail")?.classList).not.toContain(
      "mobile-open",
    );
  });

  it("dismisses mobile session history with Escape", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });

    const trigger = screen.getByRole("button", { name: "Sessions" });
    await user.click(trigger);
    fireEvent.keyDown(window, { key: "Escape" });

    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });

  it("opens the exact score snapshot in a dedicated page reader", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });

    await user.click(
      await screen.findByRole("button", { name: "Open score reader" }),
    );

    expect(screen.getByRole("button", { name: /Workspace/ })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Piano roll" })).toBeNull();
    expect(await screen.findByText("Page 1 of 4")).toBeTruthy();
    const route = new URL(window.location.href).searchParams;
    expect(route.get("view")).toBe("score");
    expect(route.get("score")).toBe(
      "artifact:20260726T100000-abcdef123456:musicxml",
    );
    expect(route.get("score_sha")).toMatch(/^[0-9a-f]{64}$/);
    expect(route.get("score_horizon")).toBe(String(48_000 * 41));
    expect(route.get("alignment")).toBe(
      "artifact:20260726T100000-abcdef123456:score-alignment",
    );

    await user.click(
      screen.getByRole("button", { name: "Next score page" }),
    );
    expect(screen.getByText("Page 2 of 4")).toBeTruthy();

    fireEvent.keyDown(window, { key: "PageDown" });
    expect(screen.getByText("Page 3 of 4")).toBeTruthy();

    const engraving = screen.getByLabelText(
      "Rendered committed MusicXML score",
    );
    const comfortableFormatWidth = Number(
      engraving.dataset.osmdFormatWidth,
    );
    expect(engraving.dataset.osmdMinimumSystemDistance).toBe("12");

    const density = screen.getByLabelText("Density");
    await user.selectOptions(density, "compact");
    await waitFor(() =>
      expect(screen.getByText("Page 3 of 4")).toBeTruthy()
    );
    await waitFor(() =>
      expect(engraving.dataset.osmdMinimumSystemDistance).toBe("6")
    );
    expect(Number(engraving.dataset.osmdFormatWidth)).toBeGreaterThan(
      comfortableFormatWidth,
    );
    expect(
      window.localStorage.getItem("atpiano.score-reader-density"),
    ).toBe("compact");

    fireEvent.keyDown(density, { key: "PageDown" });
    expect(screen.getByText("Page 3 of 4")).toBeTruthy();

    const reader = screen.getByLabelText("Score page reader");
    fireEvent.pointerDown(reader, { clientX: 180 });
    fireEvent.pointerUp(reader, { clientX: 260 });
    expect(screen.getByText("Page 2 of 4")).toBeTruthy();

    await user.click(
      screen.getByRole("button", { name: "Enter fullscreen" }),
    );
    expect(
      await screen.findByText("Browser fullscreen is unavailable."),
    ).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /Workspace/ }));
    expect(
      await screen.findByRole("heading", { name: "Piano roll" }),
    ).toBeTruthy();
    expect(new URL(window.location.href).searchParams.get("view")).toBeNull();
  });

  it("keeps one playback host through reader navigation", async () => {
    const user = userEvent.setup();
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    renderApp();
    const play = await screen.findByRole("button", {
      name: "Play recorded audio",
    });
    await waitFor(() =>
      expect((play as HTMLButtonElement).disabled).toBe(false)
    );
    const audio = document.querySelector(".persistent-playback-audio");
    await user.click(play);
    expect(usePlaybackStore.getState().status).toBe("playing");

    await user.click(
      await screen.findByRole("button", { name: "Open score reader" }),
    );

    expect(await screen.findByText("Page 1 of 4")).toBeTruthy();
    expect(document.querySelector(".persistent-playback-audio")).toBe(audio);
    await user.click(
      screen.getByRole("button", { name: "Pause recorded audio" }),
    );
    expect(usePlaybackStore.getState().status).toBe("paused");
    expect(screen.getByText("Page 1 of 4")).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: "Play recorded audio" }),
    );
    expect(usePlaybackStore.getState().status).toBe("playing");
    expect(screen.getByText("Page 1 of 4")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /Workspace/ }));

    expect(
      await screen.findByRole("heading", { name: "Piano roll" }),
    ).toBeTruthy();
    expect(document.querySelector(".persistent-playback-audio")).toBe(audio);
    expect(
      screen.getByRole("button", { name: "Pause recorded audio" }),
    ).toBeTruthy();
  });

  it("reloads a pinned score route without resolving it as current", async () => {
    window.history.replaceState(
      null,
      "",
      "/?session=20260726T100000-abcdef123456" +
        "&view=score" +
        "&score=artifact%3A20260726T100000-abcdef123456%3Amusicxml" +
        "&score_sha=8ad10edb9214c4c428225789d5eb6b6f7611c87f48cc8526b42bf5ea5c411e1d" +
        `&score_horizon=${48_000 * 41}` +
        "&alignment=artifact%3A20260726T100000-abcdef123456%3Ascore-alignment",
    );

    renderApp();

    expect(
      await screen.findByRole("button", { name: /Workspace/ }),
    ).toBeTruthy();
    expect(await screen.findByText("Page 1 of 4")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Piano roll" })).toBeNull();
  });

  it("returns from reader mode with ordinary browser Back", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "Morning progression" });
    await user.click(
      await screen.findByRole("button", { name: "Open score reader" }),
    );
    expect(await screen.findByText("Page 1 of 4")).toBeTruthy();

    window.history.back();

    expect(
      await screen.findByRole("heading", { name: "Piano roll" }),
    ).toBeTruthy();
    expect(new URL(window.location.href).searchParams.get("view")).toBeNull();
  });

  it("refuses pinned MusicXML whose bytes do not match the route", async () => {
    window.history.replaceState(
      null,
      "",
      "/?session=20260726T100000-abcdef123456" +
        "&view=score" +
        "&score=artifact%3A20260726T100000-abcdef123456%3Amusicxml" +
        `&score_sha=${"0".repeat(64)}` +
        `&score_horizon=${48_000 * 41}`,
    );

    renderApp();

    expect(
      await screen.findByText("The pinned score could not load."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /Workspace/ })).toBeTruthy();
  });

  it("keeps a pinned score visible until a newer one is chosen", async () => {
    const fixture = createFixtureRuntime();
    const runtime = new Proxy(fixture, {
      get(target, property) {
        if (property === "listArtifacts") {
          return async (
            ...args: Parameters<AtpianoRuntime["listArtifacts"]>
          ) => {
            const page = await target.listArtifacts(...args);
            return {
              ...page,
              items: page.items.map((artifact) =>
                artifact.kind === "musicxml"
                  ? {
                      ...artifact,
                      artifact_id: "artifact:newer-score",
                      sha256: "1".repeat(64),
                    }
                  : artifact,
              ),
            };
          };
        }
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) satisfies AtpianoRuntime;
    window.history.replaceState(
      null,
      "",
      "/?session=20260726T100000-abcdef123456" +
        "&view=score" +
        "&score=artifact%3A20260726T100000-abcdef123456%3Amusicxml" +
        "&score_sha=8ad10edb9214c4c428225789d5eb6b6f7611c87f48cc8526b42bf5ea5c411e1d" +
        `&score_horizon=${48_000 * 41}`,
    );
    const user = userEvent.setup();

    renderApp(runtime);

    expect(await screen.findByText("Page 1 of 4")).toBeTruthy();
    const update = await screen.findByRole("button", {
      name: /A newer committed score is available/,
    });
    expect(new URL(window.location.href).searchParams.get("score")).not.toBe(
      "artifact:newer-score",
    );

    await user.click(update);

    expect(new URL(window.location.href).searchParams.get("score")).toBe(
      "artifact:newer-score",
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

    await user.click(screen.getByRole("button", { name: /Run test recording/ }));

    expect(
      await screen.findByText("Listening with background correction"),
    ).toBeTruthy();
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
    expect(document.querySelectorAll(".library-session-main")).toHaveLength(2);
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

    await user.click(
      await screen.findByRole("button", { name: "Refresh score" }),
    );

    expect(await screen.findByText("Score runtime unavailable")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Morning progression" }))
      .toBeTruthy();
    expect(screen.getByRole("heading", { name: "Piano roll" })).toBeTruthy();
  });

  it("explains when the committed model detected no piano notes", async () => {
    const user = userEvent.setup();
    const fixture = createFixtureRuntime();
    const message =
      "No completed piano notes were detected, so there is nothing to score.";
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
          return async (
            ...args: Parameters<AtpianoRuntime["getJob"]>
          ) => {
            const job = await target.getJob(...args);
            return {
              ...job,
              status: "failed" as const,
              completed_at: "2026-07-26T10:00:45Z",
              artifact_ids: [],
              error: {
                schema_version: "atpiano.contract.v1" as const,
                error_id: `error:${job.job_id}`,
                code: "internal" as const,
                message,
                retryable: true,
                workspace_id: job.workspace_id,
                session_id: job.session_id,
                capture_id: null,
                job_id: job.job_id,
                details: {},
              },
            };
          };
        }
        const value = Reflect.get(target, property);
        return typeof value === "function" ? value.bind(target) : value;
      },
    }) satisfies AtpianoRuntime;
    renderApp(runtime);
    await screen.findByRole("heading", { name: "Morning progression" });

    await user.click(screen.getByRole("button", { name: "Refresh score" }));

    expect(await screen.findAllByText(message)).toHaveLength(2);
    expect(
      screen.queryByText("Score rendering failed. Your performance is still safe."),
    ).toBeNull();
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

    expect(
      await screen.findAllByText("Score job status unavailable"),
    ).toHaveLength(2);
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
