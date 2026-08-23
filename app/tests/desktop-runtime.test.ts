import assert from "node:assert/strict";
import test from "node:test";

import { isSupportedDesktopRelease } from "../src/runtime/desktop-runtime.js";

test("desktop release identities and package types are exact pairs", () => {
  assert.equal(isSupportedDesktopRelease("macos", "arm64", "app"), true);
  assert.equal(
    isSupportedDesktopRelease("windows", "x86_64", "nsis"),
    true,
  );
  for (const identity of [
    ["macos", "arm64", "nsis"],
    ["windows", "x86_64", "app"],
    ["windows", "arm64", "nsis"],
    ["linux", "x86_64", "appimage"],
  ] as const) {
    assert.equal(isSupportedDesktopRelease(identity[0], identity[1], identity[2]), false);
  }
});
