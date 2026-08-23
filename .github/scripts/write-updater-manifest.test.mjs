import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { updaterManifest } from "./write-updater-manifest.mjs";

function fixture() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "atpiano-updater-test-"));
  const macosUpdaterPath = path.join(directory, "Atpiano.app.tar.gz");
  const windowsUpdaterPath = path.join(
    directory,
    "Atpiano_1.2.3_x64-setup.exe",
  );
  fs.writeFileSync(`${macosUpdaterPath}.sig`, "m".repeat(64));
  fs.writeFileSync(`${windowsUpdaterPath}.sig`, "w".repeat(64));
  return {
    directory,
    tag: "desktop-v1.2.3",
    repository: "kzahel/atpiano",
    macosUpdaterPath,
    windowsUpdaterPath,
    notes: "Proof of concept.",
    pubDate: "2026-08-23T12:00:00.000Z",
  };
}

test("writes the exact two-target update identity", (context) => {
  const data = fixture();
  context.after(() => fs.rmSync(data.directory, { recursive: true }));

  assert.deepEqual(updaterManifest(data), {
    version: "1.2.3",
    notes: "Proof of concept.",
    pub_date: data.pubDate,
    platforms: {
      "darwin-aarch64": {
        signature: "m".repeat(64),
        url: "https://github.com/kzahel/atpiano/releases/download/desktop-v1.2.3/Atpiano.app.tar.gz",
      },
      "windows-x86_64": {
        signature: "w".repeat(64),
        url: "https://github.com/kzahel/atpiano/releases/download/desktop-v1.2.3/Atpiano_1.2.3_x64-setup.exe",
      },
    },
  });
});

test("rejects an updater name or missing detached signature", (context) => {
  const data = fixture();
  context.after(() => fs.rmSync(data.directory, { recursive: true }));
  assert.throws(
    () =>
      updaterManifest({
        ...data,
        macosUpdaterPath: path.join(data.directory, "Atpiano_aarch64.app.tar.gz"),
      }),
    /unexpected macOS updater asset/,
  );
  assert.throws(
    () => updaterManifest({ ...data, windowsUpdaterPath: `${data.windowsUpdaterPath}.extra` }),
    /unexpected Windows updater asset/,
  );
  fs.rmSync(`${data.windowsUpdaterPath}.sig`);
  assert.throws(() => updaterManifest(data), /missing updater signature/);
});
