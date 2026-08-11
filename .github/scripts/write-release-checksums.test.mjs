import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

test("writes sorted checksums for every signed Atpiano asset", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "atpiano-checksums-"));
  try {
    const release = path.join(directory, "release.json");
    const output = path.join(directory, "SHA256SUMS");
    fs.writeFileSync(release, JSON.stringify({
      assets: [
        { name: "Atpiano.app.tar.gz.sig", digest: `sha256:${"c".repeat(64)}` },
        { name: "Atpiano.app.tar.gz", digest: `sha256:${"b".repeat(64)}` },
        { name: "Atpiano.dmg", digest: `sha256:${"a".repeat(64)}` },
      ],
    }));
    const result = spawnSync(
      process.execPath,
      [fileURLToPath(new URL("./write-release-checksums.mjs", import.meta.url)), release, output],
      { encoding: "utf8" },
    );
    assert.equal(result.status, 0, result.stderr);
    assert.equal(
      fs.readFileSync(output, "utf8"),
      `${"a".repeat(64)}  Atpiano.dmg\n${"b".repeat(64)}  Atpiano.app.tar.gz\n${"c".repeat(64)}  Atpiano.app.tar.gz.sig\n`,
    );
  } finally {
    fs.rmSync(directory, { recursive: true });
  }
});
