import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  CLIENT_BUILD_HISTORY_SCHEMA,
  CLIENT_VERSION_SCHEMA,
  reconcileClientBuildHistory,
} from "../config/client-continuity.js";

test("retains exactly three complete hashed asset generations", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "atpiano-builds-"));
  const dist = path.join(root, "dist");
  const assets = path.join(dist, "assets");
  const historyPath = path.join(root, ".atpiano-build-history.json");
  await mkdir(assets, { recursive: true });
  try {
    await writeFile(path.join(assets, "legacy.js"), "legacy");
    for (const build of ["one", "two", "three", "four"]) {
      await writeFile(path.join(assets, `${build}.js`), build);
      await reconcileClientBuildHistory({
        distDirectory: dist,
        historyPath,
        current: {
          schema_version: CLIENT_VERSION_SCHEMA,
          build_id: build,
          built_at: `2026-07-28T17:0${build.length}:00Z`,
          assets: [`assets/${build}.js`],
        },
        legacyAssets: build === "one" ? ["assets/legacy.js"] : [],
      });
    }

    const history = JSON.parse(await readFile(historyPath, "utf8"));
    assert.equal(history.schema_version, CLIENT_BUILD_HISTORY_SCHEMA);
    assert.deepEqual(
      history.generations.map((value: { build_id: string }) => value.build_id),
      ["two", "three", "four"],
    );
    await assert.rejects(readFile(path.join(assets, "legacy.js")));
    await assert.rejects(readFile(path.join(assets, "one.js")));
    assert.equal(await readFile(path.join(assets, "two.js"), "utf8"), "two");
    assert.equal(await readFile(path.join(assets, "three.js"), "utf8"), "three");
    assert.equal(await readFile(path.join(assets, "four.js"), "utf8"), "four");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("rejects an invalid generation bound", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "atpiano-builds-"));
  try {
    await assert.rejects(
      reconcileClientBuildHistory({
        distDirectory: path.join(root, "dist"),
        historyPath: path.join(root, "history.json"),
        current: {
          schema_version: CLIENT_VERSION_SCHEMA,
          build_id: "invalid",
          built_at: "2026-07-28T17:00:00Z",
          assets: [],
        },
        retainGenerations: 0,
      }),
      /positive integer/,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("rebuilding identical client inputs does not consume a generation", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "atpiano-builds-"));
  const dist = path.join(root, "dist");
  const assets = path.join(dist, "assets");
  const historyPath = path.join(root, "history.json");
  await mkdir(assets, { recursive: true });
  try {
    await writeFile(path.join(assets, "same.js"), "same");
    for (const builtAt of [
      "2026-07-28T17:00:00Z",
      "2026-07-28T17:01:00Z",
    ]) {
      await reconcileClientBuildHistory({
        distDirectory: dist,
        historyPath,
        current: {
          schema_version: CLIENT_VERSION_SCHEMA,
          build_id: "same",
          built_at: builtAt,
          assets: ["assets/same.js"],
        },
      });
    }

    const history = JSON.parse(await readFile(historyPath, "utf8"));
    assert.equal(history.generations.length, 1);
    assert.equal(
      history.generations[0].built_at,
      "2026-07-28T17:01:00Z",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
