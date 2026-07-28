import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  CLIENT_UPDATE_EVENT,
  CLIENT_VERSION_POLL_MS,
  CLIENT_VERSION_SCHEMA,
  ClientUpdateNotice,
  fetchClientVersion,
  isClientAssetLoadError,
  reportClientAssetLoadError,
} from "../../src/client-update.js";

function version(buildId: string) {
  return new Response(JSON.stringify({
    schema_version: CLIENT_VERSION_SCHEMA,
    build_id: buildId,
    built_at: "2026-07-28T17:00:00Z",
  }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("client deployment updates", () => {
  it("accepts only the versioned build document", async () => {
    expect(
      await fetchClientVersion(vi.fn(async () => version("next"))),
    ).toEqual({
      schema_version: CLIENT_VERSION_SCHEMA,
      build_id: "next",
      built_at: "2026-07-28T17:00:00Z",
    });
    expect(
      await fetchClientVersion(vi.fn(async () =>
        new Response('{"build_id":"next"}')
      )),
    ).toBeNull();
    expect(
      await fetchClientVersion(vi.fn(async () => {
        throw new TypeError("offline");
      })),
    ).toBeNull();
  });

  it("detects browser dynamic-import acquisition failures", () => {
    expect(
      isClientAssetLoadError(
        new TypeError("Failed to fetch dynamically imported module"),
      ),
    ).toBe(true);
    expect(
      isClientAssetLoadError(
        new TypeError("Importing a module script failed."),
      ),
    ).toBe(true);
    expect(isClientAssetLoadError(new Error("invalid MusicXML"))).toBe(false);
  });

  it("raises an urgent reload notice for a missing client chunk", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => version(__ATPIANO_BUILD_ID__)));
    render(<ClientUpdateNotice />);

    expect(
      reportClientAssetLoadError(
        new TypeError("Failed to fetch dynamically imported module"),
      ),
    ).toBe(true);

    expect(
      await screen.findByText(
        "Atpiano was updated. Reload this page to continue.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reload" })).toBeTruthy();
  });

  it("polls and notices a newer build without reloading", async () => {
    vi.useFakeTimers();
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(version(__ATPIANO_BUILD_ID__))
      .mockResolvedValue(version("new-build"));
    vi.stubGlobal("fetch", fetcher);
    render(<ClientUpdateNotice />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByText("A newer Atpiano version is ready.")).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(CLIENT_VERSION_POLL_MS);
    });

    expect(
      screen.getByText("A newer Atpiano version is ready."),
    ).toBeTruthy();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("checks again when the window regains focus", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(version(__ATPIANO_BUILD_ID__))
      .mockResolvedValue(version("focused-build"));
    vi.stubGlobal("fetch", fetcher);
    render(<ClientUpdateNotice />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledOnce());

    fireEvent.focus(window);

    expect(
      await screen.findByText("A newer Atpiano version is ready."),
    ).toBeTruthy();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("checks again when a sleeping document becomes visible", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(version(__ATPIANO_BUILD_ID__))
      .mockResolvedValue(version("visible-build"));
    vi.stubGlobal("fetch", fetcher);
    render(<ClientUpdateNotice />);
    await waitFor(() => expect(fetcher).toHaveBeenCalledOnce());
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });

    fireEvent(document, new Event("visibilitychange"));

    expect(
      await screen.findByText("A newer Atpiano version is ready."),
    ).toBeTruthy();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("ignores unrelated application events", () => {
    vi.stubGlobal("fetch", vi.fn(async () => version(__ATPIANO_BUILD_ID__)));
    render(<ClientUpdateNotice />);

    window.dispatchEvent(new CustomEvent(`${CLIENT_UPDATE_EVENT}:other`));

    expect(screen.queryByRole("button", { name: "Reload" })).toBeNull();
  });
});
