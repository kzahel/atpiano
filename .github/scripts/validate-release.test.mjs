import assert from "node:assert/strict";
import test from "node:test";

import { validateRelease } from "./validate-release.mjs";

const tag = "desktop-v1.2.3";
const version = "1.2.3";
const repository = "kzahel/atpiano";
const digest = `sha256:${"a".repeat(64)}`;

function fixture() {
  const updater = "Atpiano_aarch64.app.tar.gz";
  const windowsUpdater = `Atpiano_${version}_x64-setup.nsis.zip`;
  const names = [
    `Atpiano_${version}_aarch64.dmg`,
    updater,
    `${updater}.sig`,
    `Atpiano_${version}_x64-setup.exe`,
    windowsUpdater,
    `${windowsUpdater}.sig`,
    `Atpiano_${version}_media-sources.tar.gz`,
    "latest.json",
  ];
  return {
    release: {
      tagName: tag,
      isDraft: true,
      assets: names.map((name) => ({ name, digest })),
    },
    latest: {
      version,
      platforms: {
        "darwin-aarch64": {
          signature: "signed-updater-metadata-that-is-long-enough",
          url: `https://github.com/${repository}/releases/download/${tag}/${updater}`,
        },
        "windows-x86_64": {
          signature: "signed-windows-metadata-that-is-long-enough",
          url: `https://github.com/${repository}/releases/download/${tag}/${windowsUpdater}`,
        },
      },
    },
  };
}

test("accepts the exact Atpiano two-target draft", () => {
  assert.equal(validateRelease({ ...fixture(), tag, repository }).version, version);
});

test("rejects an already-public release", () => {
  const data = fixture();
  data.release.isDraft = false;
  assert.throws(() => validateRelease({ ...data, tag, repository }), /remain a draft/);
});

test("rejects target expansion", () => {
  const data = fixture();
  data.latest.platforms["linux-x86_64"] = {
    signature: "signed-updater-metadata-that-is-long-enough",
    url: "https://example.test/setup.exe",
  };
  assert.throws(() => validateRelease({ ...data, tag, repository }), /unexpected latest/);
});

test("rejects updater URLs outside the exact tagged release", () => {
  const data = fixture();
  data.latest.platforms["darwin-aarch64"].url = "https://example.test/Atpiano.app.tar.gz";
  assert.throws(() => validateRelease({ ...data, tag, repository }), /unexpected URL/);
  data.latest.platforms["darwin-aarch64"].url =
    `https://github.com/${repository}/releases/download/${tag}/Atpiano_aarch64.app.tar.gz`;
  data.latest.platforms["windows-x86_64"].url = "https://example.test/setup.nsis.zip";
  assert.throws(() => validateRelease({ ...data, tag, repository }), /unexpected URL/);
});

test("rejects unexpected packages or missing GitHub digests", () => {
  const data = fixture();
  data.release.assets.push({ name: "Atpiano_1.2.3_x64.dmg", digest });
  assert.throws(() => validateRelease({ ...data, tag, repository }), /unexpected release assets/);
  data.release.assets.pop();
  data.release.assets[0].digest = null;
  assert.throws(() => validateRelease({ ...data, tag, repository }), /missing a GitHub/);
});

test("rejects a missing corresponding media source archive", () => {
  const data = fixture();
  data.release.assets = data.release.assets.filter(
    (asset) => !asset.name.endsWith("_media-sources.tar.gz"),
  );
  assert.throws(
    () => validateRelease({ ...data, tag, repository }),
    /corresponding media source archive/,
  );
});
