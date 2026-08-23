#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function fail(message) {
  throw new Error(message);
}

function releaseUrl(repository, tag, asset) {
  return `https://github.com/${repository}/releases/download/${tag}/${encodeURIComponent(asset)}`;
}

function signatureFor(updaterPath) {
  const signaturePath = `${updaterPath}.sig`;
  if (!fs.existsSync(signaturePath) || !fs.statSync(signaturePath).isFile()) {
    fail(`missing updater signature: ${signaturePath}`);
  }
  const signature = fs.readFileSync(signaturePath, "utf8").trim();
  if (signature.length < 32) fail(`updater signature is unusable: ${signaturePath}`);
  return signature;
}

export function updaterManifest({
  tag,
  repository,
  macosUpdaterPath,
  windowsUpdaterPath,
  notes = "",
  pubDate,
}) {
  if (!/^desktop-v\d+\.\d+\.\d+$/.test(tag)) fail(`unexpected desktop tag: ${tag}`);
  if (!/^[^/]+\/[^/]+$/.test(repository)) fail(`unexpected repository: ${repository}`);
  const version = tag.slice("desktop-v".length);
  const macosAsset = path.basename(macosUpdaterPath);
  const windowsAsset = path.basename(windowsUpdaterPath);
  if (!/^Atpiano(?:_[0-9.]+)?_aarch64\.app\.tar\.gz$/.test(macosAsset)) {
    fail(`unexpected macOS updater asset: ${macosAsset}`);
  }
  if (windowsAsset !== `Atpiano_${version}_x64-setup.nsis.zip`) {
    fail(`unexpected Windows updater asset: ${windowsAsset}`);
  }
  const publishedAt = pubDate ?? new Date().toISOString();
  if (Number.isNaN(Date.parse(publishedAt))) fail(`invalid publication date: ${publishedAt}`);
  return {
    version,
    notes,
    pub_date: publishedAt,
    platforms: {
      "darwin-aarch64": {
        signature: signatureFor(macosUpdaterPath),
        url: releaseUrl(repository, tag, macosAsset),
      },
      "windows-x86_64": {
        signature: signatureFor(windowsUpdaterPath),
        url: releaseUrl(repository, tag, windowsAsset),
      },
    },
  };
}

function parseArguments(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index];
    const value = argv[index + 1];
    if (!name?.startsWith("--") || value === undefined) {
      fail(`invalid argument near ${name ?? "<end>"}`);
    }
    result[name.slice(2)] = value;
  }
  for (const name of [
    "tag",
    "repository",
    "macos-updater",
    "windows-updater",
    "output",
  ]) {
    if (!result[name]) fail(`missing --${name}`);
  }
  return result;
}

if (fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    const args = parseArguments(process.argv.slice(2));
    const manifest = updaterManifest({
      tag: args.tag,
      repository: args.repository,
      macosUpdaterPath: args["macos-updater"],
      windowsUpdaterPath: args["windows-updater"],
      notes: args["notes-file"] ? fs.readFileSync(args["notes-file"], "utf8").trim() : "",
      pubDate: args["pub-date"],
    });
    fs.writeFileSync(args.output, `${JSON.stringify(manifest, null, 2)}\n`, {
      encoding: "utf8",
      flag: "wx",
    });
    console.log(`Wrote two-target updater manifest ${manifest.version}`);
  } catch (error) {
    console.error(`Updater manifest creation failed: ${error.message}`);
    process.exitCode = 1;
  }
}
