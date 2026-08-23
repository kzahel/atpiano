#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

export const UPDATE_ENDPOINT =
  "https://updates.graehlarts.com/atpiano/tauri/{{target}}/{{arch}}/{{current_version}}";
const UPDATER_KEY_PLACEHOLDER = "__ATPIANO_TAURI_UPDATER_PUBLIC_KEY__";
const CANARY_PUBLIC_KEY =
  "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEM4NUNFMEMxOUY4NDgzQkIKUldTN2c0U2Z3ZUJjeUQzQjlTZmhMUXE1bXVJajVLZXlLQzJPZzZLTElUU1lzcE5OVURyOXVWN3kK";

function fail(message) {
  throw new Error(message);
}

function sectionVersion(contents, section) {
  const marker = `[${section}]`;
  const start = contents.indexOf(marker);
  if (start < 0) fail(`${section} section is missing`);
  const remainder = contents.slice(start + marker.length);
  const nextSection = remainder.search(/\n\[/);
  const body = nextSection < 0 ? remainder : remainder.slice(0, nextSection);
  const version = body?.match(/^version\s*=\s*"([^"]+)"/m)?.[1];
  if (!version) fail(`${section} has no version`);
  return version;
}

export function validateDesktopReleaseConfiguration({
  appPackage,
  tauri,
  windowsTauri,
  cargo,
  pyproject,
  product,
  capabilities,
}) {
  const versions = {
    appPackage: appPackage.version,
    tauri: tauri.version,
    cargo: sectionVersion(cargo, "package"),
    python: sectionVersion(pyproject, "project"),
  };
  if (new Set(Object.values(versions)).size !== 1) {
    fail(`version drift: ${JSON.stringify(versions)}`);
  }
  if (!/^\d+\.\d+\.\d+$/.test(tauri.version)) {
    fail(`version is not stable semver: ${tauri.version}`);
  }
  if (tauri.identifier !== "com.atpiano.desktop") {
    fail(`unexpected Tauri identifier: ${tauri.identifier}`);
  }
  if (JSON.stringify(tauri.bundle?.targets) !== JSON.stringify(["app", "dmg"])) {
    fail(`unexpected desktop bundle targets: ${JSON.stringify(tauri.bundle?.targets)}`);
  }
  if (tauri.bundle?.createUpdaterArtifacts !== true) {
    fail("Tauri updater artifacts must be enabled");
  }
  if (JSON.stringify(windowsTauri.bundle?.targets) !== JSON.stringify(["nsis"])) {
    fail(`unexpected Windows bundle targets: ${JSON.stringify(windowsTauri.bundle?.targets)}`);
  }
  if (
    windowsTauri.bundle?.windows?.nsis?.installMode !== "currentUser" ||
    windowsTauri.bundle?.windows?.allowDowngrades !== false
  ) {
    fail("Windows NSIS must be current-user and reject downgrades");
  }
  if (windowsTauri.plugins?.updater?.windows?.installMode !== "passive") {
    fail("Windows updater install mode must be passive");
  }
  const endpoints = tauri.plugins?.updater?.endpoints;
  if (!Array.isArray(endpoints) || endpoints.length !== 1 || endpoints[0] !== UPDATE_ENDPOINT) {
    fail(`unexpected updater endpoints: ${JSON.stringify(endpoints)}`);
  }
  const publicKey = tauri.plugins?.updater?.pubkey;
  if (!publicKey || publicKey === UPDATER_KEY_PLACEHOLDER) {
    fail("replace the Atpiano updater public-key placeholder");
  }
  if (publicKey === CANARY_PUBLIC_KEY) {
    fail("Atpiano must not reuse the canary updater key");
  }
  let decoded;
  try {
    decoded = Buffer.from(publicKey, "base64").toString("utf8");
  } catch {
    fail("updater public key is not base64");
  }
  if (!decoded.startsWith("untrusted comment: minisign public key") || !decoded.includes("\nRW")) {
    fail("updater public key does not encode a minisign public-key file");
  }

  const expectedProduct = {
    id: "atpiano",
    displayName: "Atpiano",
    hostnames: ["updates.graehlarts.com"],
    pathPrefix: "/atpiano",
    githubRepo: "kzahel/atpiano",
    tagPrefix: "desktop-v",
    tauriUpdates: true,
  };
  if (JSON.stringify(product) !== JSON.stringify(expectedProduct)) {
    fail(`unexpected update-server product config: ${JSON.stringify(product)}`);
  }
  for (const permission of ["process:default", "updater:default"]) {
    if (!capabilities.permissions?.includes(permission)) {
      fail(`desktop capability is missing ${permission}`);
    }
  }
  return { version: tauri.version, endpoint: UPDATE_ENDPOINT };
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

export function validateDesktopReleaseRepository(root) {
  const result = validateDesktopReleaseConfiguration({
    appPackage: readJson(path.join(root, "app", "package.json")),
    tauri: readJson(path.join(root, "app", "src-tauri", "tauri.conf.json")),
    windowsTauri: readJson(
      path.join(root, "app", "src-tauri", "tauri.windows.conf.json"),
    ),
    cargo: fs.readFileSync(path.join(root, "app", "src-tauri", "Cargo.toml"), "utf8"),
    pyproject: fs.readFileSync(path.join(root, "pyproject.toml"), "utf8"),
    product: readJson(path.join(root, "update-server", "atpiano.json")),
    capabilities: readJson(
      path.join(root, "app", "src-tauri", "capabilities", "default.json"),
    ),
  });
  const changelog = fs.readFileSync(path.join(root, "CHANGELOG.md"), "utf8");
  if (!changelog.includes(`## [${result.version}]`)) {
    fail(`CHANGELOG.md has no ${result.version} entry`);
  }
  validateMacosDmgReleaseContract({
    workflow: fs.readFileSync(
      path.join(root, ".github", "workflows", "desktop.yml"),
      "utf8",
    ),
    buildScript: fs.readFileSync(
      path.join(root, "scripts", "build-atpiano-desktop"),
      "utf8",
    ),
  });
  return result;
}

export function validateMacosDmgReleaseContract({ workflow, buildScript }) {
  if (!workflow.includes("scripts/build-atpiano-desktop notarize-release-dmg")) {
    fail("macOS release workflow does not notarize the DMG");
  }
  if (!workflow.includes("-name 'Atpiano.app.tar.gz'")) {
    fail("macOS release workflow does not select the Tauri v2 updater artifact");
  }
  for (const command of [
    "xcrun notarytool submit",
    "xcrun stapler staple",
    "xcrun stapler validate",
    "--type open",
    "--context context:primary-signature",
  ]) {
    if (!buildScript.includes(command)) {
      fail(`macOS DMG release contract is missing: ${command}`);
    }
  }
}

if (fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    const root = path.resolve(import.meta.dirname, "..");
    const result = validateDesktopReleaseRepository(root);
    console.log(`Validated Atpiano desktop release configuration ${result.version}`);
  } catch (error) {
    console.error(`Desktop release configuration failed: ${error.message}`);
    process.exitCode = 1;
  }
}
