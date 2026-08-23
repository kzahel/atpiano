import assert from "node:assert/strict";
import test from "node:test";

import {
  UPDATE_ENDPOINT,
  validateDesktopReleaseConfiguration,
  validateMacosDmgReleaseContract,
} from "./validate-desktop-release.mjs";

const publicKey = Buffer.from(
  "untrusted comment: minisign public key 0123456789ABCDEF\nRWQatpiano\n",
).toString("base64");

function fixture() {
  return {
    appPackage: { version: "1.2.3" },
    cargo: '[package]\nname = "atpiano-desktop"\nversion = "1.2.3"\n',
    pyproject: '[project]\nname = "atpiano"\nversion = "1.2.3"\n',
    tauri: {
      version: "1.2.3",
      identifier: "com.atpiano.desktop",
      bundle: { targets: ["app", "dmg"], createUpdaterArtifacts: true },
      plugins: { updater: { endpoints: [UPDATE_ENDPOINT], pubkey: publicKey } },
    },
    windowsTauri: {
      bundle: {
        targets: ["nsis"],
        windows: {
          allowDowngrades: false,
          nsis: { installMode: "currentUser" },
        },
      },
      plugins: { updater: { windows: { installMode: "passive" } } },
    },
    product: {
      id: "atpiano",
      displayName: "Atpiano",
      hostnames: ["updates.graehlarts.com"],
      pathPrefix: "/atpiano",
      githubRepo: "kzahel/atpiano",
      tagPrefix: "desktop-v",
      tauriUpdates: true,
    },
    capabilities: { permissions: ["process:default", "updater:default"] },
  };
}

test("accepts Atpiano's exact two-platform release contract", () => {
  assert.equal(validateDesktopReleaseConfiguration(fixture()).version, "1.2.3");
});

test("rejects version drift", () => {
  const data = fixture();
  data.tauri.version = "1.2.4";
  assert.throws(() => validateDesktopReleaseConfiguration(data), /version drift/);
});

test("rejects accidental macOS target expansion", () => {
  const data = fixture();
  data.tauri.bundle.targets.push("nsis");
  assert.throws(() => validateDesktopReleaseConfiguration(data), /bundle targets/);
});

test("rejects unsafe Windows package or updater drift", () => {
  const data = fixture();
  data.windowsTauri.bundle.windows.nsis.installMode = "perMachine";
  assert.throws(() => validateDesktopReleaseConfiguration(data), /current-user/);
  data.windowsTauri.bundle.windows.nsis.installMode = "currentUser";
  data.windowsTauri.plugins.updater.windows.installMode = "quiet";
  assert.throws(() => validateDesktopReleaseConfiguration(data), /passive/);
});

test("rejects an unresolved or reused updater key", () => {
  const data = fixture();
  data.tauri.plugins.updater.pubkey = "__ATPIANO_TAURI_UPDATER_PUBLIC_KEY__";
  assert.throws(
    () => validateDesktopReleaseConfiguration(data),
    /public-key placeholder/,
  );
  data.tauri.plugins.updater.pubkey =
    "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEM4NUNFMEMxOUY4NDgzQkIKUldTN2c0U2Z3ZUJjeUQzQjlTZmhMUXE1bXVJajVLZXlLQzJPZzZLTElUU1lzcE5OVURyOXVWN3kK";
  assert.throws(() => validateDesktopReleaseConfiguration(data), /reuse the canary/);
});

test("rejects product route drift", () => {
  const data = fixture();
  data.product.pathPrefix = "/different";
  assert.throws(() => validateDesktopReleaseConfiguration(data), /product config/);
});

test("requires notarization, stapling, and Gatekeeper assessment for the DMG", () => {
  const workflow = [
    "scripts/build-atpiano-desktop notarize-release-dmg",
    "-name 'Atpiano.app.tar.gz'",
  ].join("\n");
  const buildScript = [
    "xcrun notarytool submit",
    "xcrun stapler staple",
    "xcrun stapler validate",
    "--type open",
    "--context context:primary-signature",
  ].join("\n");
  assert.doesNotThrow(() =>
    validateMacosDmgReleaseContract({ workflow, buildScript }),
  );
  assert.throws(
    () => validateMacosDmgReleaseContract({ workflow: "", buildScript }),
    /does not notarize/,
  );
  assert.throws(
    () =>
      validateMacosDmgReleaseContract({
        workflow: "scripts/build-atpiano-desktop notarize-release-dmg",
        buildScript,
      }),
    /does not select the Tauri v2 updater artifact/,
  );
  assert.throws(
    () => validateMacosDmgReleaseContract({ workflow, buildScript: "" }),
    /missing: xcrun notarytool submit/,
  );
});
