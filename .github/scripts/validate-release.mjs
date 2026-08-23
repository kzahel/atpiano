#!/usr/bin/env node

import fs from "node:fs";
import { fileURLToPath } from "node:url";

function fail(message) {
  throw new Error(message);
}

function matchingAsset(assetNames, pattern, label) {
  const matches = [...assetNames].filter((name) => pattern.test(name));
  if (matches.length !== 1) {
    fail(`expected exactly one ${label}, found ${matches.length}: ${matches.join(", ")}`);
  }
  return matches[0];
}

export function validateRelease({ release, latest, tag, repository }) {
  if (!/^desktop-v\d+\.\d+\.\d+$/.test(tag)) {
    fail(`unexpected desktop tag: ${tag}`);
  }
  const version = tag.slice("desktop-v".length);
  if (release.tagName !== tag) fail(`release tag ${release.tagName} does not match ${tag}`);
  if (!release.isDraft) fail("release must remain a draft until validation succeeds");
  if (!Array.isArray(release.assets)) fail("release assets are missing");

  const assetNames = new Set();
  for (const asset of release.assets) {
    if (!asset.name || assetNames.has(asset.name)) {
      fail(`missing or duplicate release asset name: ${asset.name ?? "<empty>"}`);
    }
    assetNames.add(asset.name);
    if (!/^sha256:[0-9a-f]{64}$/i.test(asset.digest ?? "")) {
      fail(`release asset ${asset.name} is missing a GitHub SHA-256 digest`);
    }
  }

  const dmg = matchingAsset(
    assetNames,
    new RegExp(`^Atpiano_${version.replaceAll(".", "\\.")}_aarch64\\.dmg$`),
    "macOS Apple-silicon DMG",
  );
  const updater = matchingAsset(
    assetNames,
    /^Atpiano(?:_[0-9.]+)?_aarch64\.app\.tar\.gz$/,
    "macOS Apple-silicon updater archive",
  );
  const signature = `${updater}.sig`;
  const windowsInstaller = matchingAsset(
    assetNames,
    new RegExp(`^Atpiano_${version.replaceAll(".", "\\.")}_x64-setup\\.exe$`),
    "Windows x64 NSIS installer",
  );
  const windowsUpdater = matchingAsset(
    assetNames,
    new RegExp(`^Atpiano_${version.replaceAll(".", "\\.")}_x64-setup\\.nsis\\.zip$`),
    "Windows x64 updater archive",
  );
  const windowsSignature = `${windowsUpdater}.sig`;
  const mediaSources = matchingAsset(
    assetNames,
    new RegExp(`^Atpiano_${version.replaceAll(".", "\\.")}_media-sources\\.tar\\.gz$`),
    "corresponding media source archive",
  );
  for (const required of ["latest.json", "SHA256SUMS", signature, windowsSignature]) {
    if (!assetNames.has(required)) fail(`missing required release asset: ${required}`);
  }
  const expectedAssets = new Set([
    dmg,
    updater,
    signature,
    windowsInstaller,
    windowsUpdater,
    windowsSignature,
    mediaSources,
    "latest.json",
    "SHA256SUMS",
  ]);
  const unexpected = [...assetNames].filter((name) => !expectedAssets.has(name));
  if (unexpected.length) fail(`unexpected release assets: ${unexpected.join(", ")}`);

  if (latest.version !== version) {
    fail(`latest.json version ${latest.version} does not match ${version}`);
  }
  if (!latest.platforms || typeof latest.platforms !== "object") {
    fail("latest.json platforms are missing");
  }
  const platforms = Object.keys(latest.platforms).sort();
  if (
    JSON.stringify(platforms) !==
    JSON.stringify(["darwin-aarch64", "windows-x86_64"])
  ) {
    fail(`unexpected latest.json platforms: ${platforms.join(", ")}`);
  }
  for (const [platform, asset] of [
    ["darwin-aarch64", updater],
    ["windows-x86_64", windowsUpdater],
  ]) {
    const metadata = latest.platforms[platform];
    if (typeof metadata.signature !== "string" || metadata.signature.length < 32) {
      fail(`latest.json ${platform} has no usable signature`);
    }
    const expectedUrl =
      `https://github.com/${repository}/releases/download/${tag}/${encodeURIComponent(asset)}`;
    if (metadata.url !== expectedUrl) {
      fail(`latest.json ${platform} has an unexpected URL: ${metadata.url}`);
    }
  }
  return { version, platforms };
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
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
  for (const name of ["release", "latest", "tag", "repository"]) {
    if (!result[name]) fail(`missing --${name}`);
  }
  return result;
}

if (fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    const args = parseArguments(process.argv.slice(2));
    const result = validateRelease({
      release: readJson(args.release),
      latest: readJson(args.latest),
      tag: args.tag,
      repository: args.repository,
    });
    console.log(`Validated Atpiano desktop release ${result.version}`);
  } catch (error) {
    console.error(`Desktop release validation failed: ${error.message}`);
    process.exitCode = 1;
  }
}
