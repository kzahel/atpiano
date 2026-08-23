import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DesktopScoreRuntimeDialog } from
  "../../src/components/desktop-score-runtime-dialog.js";
import type {
  DesktopScoreRuntimeClient,
  DesktopScoreRuntimeStatus,
} from "../../src/runtime/desktop-runtime.js";

const acknowledgement =
  "I understand this notice and want to download the optional research model.";

function runtimeStatus(
  overrides: Partial<DesktopScoreRuntimeStatus> = {},
): DesktopScoreRuntimeStatus {
  return {
    state: "not-installed",
    contractId: "midi2score-research-2026.08",
    noticeVersion: "midi2score-research-notice-v1",
    modelName: "MIDI2ScoreTransformer",
    sourceCommit: "115432bda16ca16e0fec2e9465788f2ba369971f",
    checkpointSha256:
      "7b8ec6e3da365b97443fb67a8f0b37d63997e93c152d665d43cb2011245db638",
    supportLayerId: "atpiano-midi2score-support-py311-2026.08",
    executionBackend: "cpu",
    purpose: "Optional local sheet-music generation from committed MIDI",
    notice:
      "MIDI2ScoreTransformer is an optional research model. Its upstream source and checkpoint do not currently include an explicit license. Atpiano does not include or license those assets. If you have the right to use them, Atpiano can download the exact upstream files for education or research use only and run them locally on this device. Do not use them commercially or redistribute them.",
    acknowledgement,
    repositoryUrl: "https://github.com/example/model",
    checkpointReleaseUrl: "https://github.com/example/model/releases/tag/v1",
    paperUrl: "https://example.test/paper",
    sourceBytes: 187_103,
    checkpointBytes: 389_829_880,
    downloadBytes: 390_016_983,
    installedSpaceEstimateBytes: 1_500_000_000,
    minimumFreeBytes: 2_500_000_000,
    supportAvailable: true,
    installedBytes: null,
    error: null,
    ...overrides,
  };
}

function runtimeManager(status: DesktopScoreRuntimeStatus) {
  const acquire = vi.fn(async () => runtimeStatus({
    state: "available",
    installedBytes: 1_234_000_000,
  }));
  const remove = vi.fn(async () => runtimeStatus());
  const openLink = vi.fn(async () => undefined);
  const manager: DesktopScoreRuntimeClient = {
    status: vi.fn(async () => status),
    acquire,
    cancel: vi.fn(async () => true),
    remove,
    openLink,
    monitor: vi.fn(async () => () => undefined),
    relaunch: vi.fn(async () => undefined),
  };
  return { acquire, manager, openLink, remove };
}

describe("desktop score runtime dialog", () => {
  it("does not acquire before an explicit acknowledgement", async () => {
    const user = userEvent.setup();
    const { acquire, manager, openLink } = runtimeManager(runtimeStatus());

    render(
      <DesktopScoreRuntimeDialog
        open
        manager={manager}
        onClose={vi.fn()}
      />,
    );

    expect(await screen.findByText(/education or research use only/)).toBeTruthy();
    expect(screen.getByText("389,829,880 bytes", { exact: false })).toBeTruthy();
    expect(acquire).not.toHaveBeenCalled();

    const download = screen.getByRole("button", {
      name: "Download research model",
    }) as HTMLButtonElement;
    expect(download.disabled).toBe(true);

    await user.click(screen.getByRole("button", { name: /Research paper/ }));
    expect(openLink).toHaveBeenCalledWith("paper");
    expect(acquire).not.toHaveBeenCalled();

    await user.click(screen.getByRole("checkbox", { name: acknowledgement }));
    expect(download.disabled).toBe(false);
    await user.click(download);

    expect(acquire).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Research model installed")).toBeTruthy();
  });

  it("fails closed when the signed support layer is unavailable", async () => {
    const user = userEvent.setup();
    const { acquire, manager } = runtimeManager(runtimeStatus({
      supportAvailable: false,
    }));

    render(
      <DesktopScoreRuntimeDialog
        open
        manager={manager}
        onClose={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("checkbox", {
      name: acknowledgement,
    }));
    const download = screen.getByRole("button", {
      name: "Download research model",
    }) as HTMLButtonElement;
    expect(download.disabled).toBe(true);
    expect(screen.getByRole("alert").textContent).toMatch(
      /does not contain the signed score-support layer/,
    );
    expect(acquire).not.toHaveBeenCalled();
  });

  it("shows provenance and preserves user work during removal", async () => {
    const user = userEvent.setup();
    const { manager, remove } = runtimeManager(runtimeStatus({
      state: "available",
      installedBytes: 1_234_000_000,
    }));

    render(
      <DesktopScoreRuntimeDialog
        open
        manager={manager}
        onClose={vi.fn()}
      />,
    );

    expect(await screen.findByText("Research model installed")).toBeTruthy();
    await user.click(screen.getByText("Installed model details"));
    expect(screen.getByText("midi2score-research-2026.08")).toBeTruthy();
    expect(screen.getByText("cpu")).toBeTruthy();

    const removal = screen.getByRole("checkbox", {
      name: /Sessions and already generated score artifacts will be preserved/,
    });
    expect(removal).toBeTruthy();
    await user.click(removal);
    await user.click(screen.getByRole("button", {
      name: "Remove research model",
    }));
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it("renders an initial native status failure", async () => {
    const manager = runtimeManager(runtimeStatus()).manager;
    vi.mocked(manager.status).mockRejectedValueOnce(
      new Error("The signed acquisition contract could not be read."),
    );

    render(
      <DesktopScoreRuntimeDialog
        open
        manager={manager}
        onClose={vi.fn()}
      />,
    );

    expect((await screen.findByRole("alert")).textContent).toMatch(
      /signed acquisition contract could not be read/,
    );
  });
});
