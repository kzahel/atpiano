import assert from "node:assert/strict";
import test from "node:test";

import { updateInstallBlocker } from "../src/desktop-update/install-blocker.js";
import { installPolicy } from "../src/desktop-update/policy.js";
import {
  PERIODIC_CHECK_INTERVAL_MS,
  scheduleAutomaticChecks,
  STARTUP_CHECK_DELAY_MS,
} from "../src/desktop-update/schedule.js";
import { progressPercent } from "../src/desktop-update/state.js";

test("the declared macOS and Windows packages can install in-app", () => {
  assert.equal(installPolicy("app").canInstallInApp, true);
  assert.equal(installPolicy("nsis").canInstallInApp, true);
  for (const bundle of [
    "appimage",
    "deb",
    "msi",
    "rpm",
    null,
  ]) {
    assert.equal(installPolicy(bundle).canInstallInApp, false);
  }
});

test("automatic checks use the accepted startup and daily schedule", () => {
  const scheduled = new Map<number, { callback: () => void; delay: number }>();
  const cleared: number[] = [];
  let next = 1;
  const reasons: string[] = [];
  const timers = {
    setTimeout(callback: () => void, delay: number) {
      const handle = next++;
      scheduled.set(handle, { callback, delay });
      return handle as unknown as ReturnType<typeof globalThis.setTimeout>;
    },
    clearTimeout(handle: ReturnType<typeof globalThis.setTimeout>) {
      cleared.push(handle as unknown as number);
    },
    setInterval(callback: () => void, delay: number) {
      const handle = next++;
      scheduled.set(handle, { callback, delay });
      return handle as unknown as ReturnType<typeof globalThis.setTimeout>;
    },
    clearInterval(handle: ReturnType<typeof globalThis.setTimeout>) {
      cleared.push(handle as unknown as number);
    },
  };
  const dispose = scheduleAutomaticChecks((reason) => reasons.push(reason), timers);
  assert.deepEqual(
    [...scheduled.values()].map((entry) => entry.delay),
    [STARTUP_CHECK_DELAY_MS, PERIODIC_CHECK_INTERVAL_MS],
  );
  for (const entry of scheduled.values()) entry.callback();
  assert.deepEqual(reasons, ["startup", "periodic"]);
  dispose();
  assert.deepEqual(cleared, [1, 2]);
});

test("installation is blocked by capture, settling, or score work", () => {
  assert.match(
    updateInstallBlocker({
      capturePhase: "recording",
      sessionStatuses: [],
      scoreJobStatus: null,
    }) ?? "",
    /recording/,
  );
  assert.match(
    updateInstallBlocker({
      capturePhase: "idle",
      sessionStatuses: ["stopping"],
      scoreJobStatus: null,
    }) ?? "",
    /settling/,
  );
  assert.match(
    updateInstallBlocker({
      capturePhase: "idle",
      sessionStatuses: ["complete"],
      scoreJobStatus: "running",
    }) ?? "",
    /score generation/,
  );
  assert.equal(
    updateInstallBlocker({
      capturePhase: "idle",
      sessionStatuses: ["complete"],
      scoreJobStatus: "complete",
    }),
    null,
  );
});

test("download progress is bounded and supports unknown lengths", () => {
  assert.equal(
    progressPercent({
      phase: "downloading",
      version: "1.2.3",
      downloadedBytes: 120,
      totalBytes: 100,
    }),
    100,
  );
  assert.equal(
    progressPercent({
      phase: "downloading",
      version: "1.2.3",
      downloadedBytes: 12,
    }),
    undefined,
  );
});
