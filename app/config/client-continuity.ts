import { createHash, randomUUID } from "node:crypto";
import { readFileSync, readdirSync, statSync } from "node:fs";
import {
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import type { Plugin, ResolvedConfig } from "vite";

export const CLIENT_VERSION_SCHEMA = "atpiano.client-version.v1";
export const CLIENT_BUILD_HISTORY_SCHEMA =
  "atpiano.client-build-history.v1";
export const RETAINED_CLIENT_GENERATIONS = 3;

export interface ClientVersion {
  readonly schema_version: typeof CLIENT_VERSION_SCHEMA;
  readonly build_id: string;
  readonly built_at: string;
}

interface ClientBuildGeneration extends ClientVersion {
  readonly assets: readonly string[];
}

interface ClientBuildHistory {
  readonly schema_version: typeof CLIENT_BUILD_HISTORY_SCHEMA;
  readonly generations: readonly ClientBuildGeneration[];
}

interface ReconcileOptions {
  readonly distDirectory: string;
  readonly historyPath: string;
  readonly current: ClientBuildGeneration;
  readonly legacyAssets?: readonly string[];
  readonly retainGenerations?: number;
}

function isAssetPath(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.startsWith("assets/") &&
    !value.includes("\\") &&
    value.split("/").every(
      (component) => component !== "" && component !== "." && component !== "..",
    )
  );
}

function normalizeAssets(values: readonly string[]): string[] {
  return [...new Set(values.filter(isAssetPath))].sort();
}

async function existingAssetPaths(distDirectory: string): Promise<string[]> {
  const assetRoot = path.join(distDirectory, "assets");
  try {
    if (!(await stat(assetRoot)).isDirectory()) return [];
  } catch {
    return [];
  }
  const found: string[] = [];
  const visit = async (directory: string): Promise<void> => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) await visit(target);
      else if (entry.isFile()) {
        found.push(path.relative(distDirectory, target).split(path.sep).join("/"));
      }
    }
  };
  await visit(assetRoot);
  return normalizeAssets(found);
}

async function readHistory(historyPath: string): Promise<ClientBuildHistory | null> {
  try {
    const parsed: unknown = JSON.parse(await readFile(historyPath, "utf8"));
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      (parsed as { schema_version?: unknown }).schema_version !==
        CLIENT_BUILD_HISTORY_SCHEMA ||
      !Array.isArray((parsed as { generations?: unknown }).generations)
    ) {
      return null;
    }
    const generations = (
      parsed as { generations: readonly Record<string, unknown>[] }
    ).generations.flatMap((value): ClientBuildGeneration[] => {
      if (
        typeof value.build_id !== "string" ||
        typeof value.built_at !== "string" ||
        !Array.isArray(value.assets)
      ) {
        return [];
      }
      return [{
        schema_version: CLIENT_VERSION_SCHEMA,
        build_id: value.build_id,
        built_at: value.built_at,
        assets: normalizeAssets(value.assets.filter(
          (asset): asset is string => typeof asset === "string",
        )),
      }];
    });
    return {
      schema_version: CLIENT_BUILD_HISTORY_SCHEMA,
      generations,
    };
  } catch {
    return null;
  }
}

async function removeEmptyDirectories(directory: string): Promise<void> {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (entry.isDirectory()) {
      await removeEmptyDirectories(path.join(directory, entry.name));
    }
  }
  if ((await readdir(directory)).length === 0) await rm(directory, { recursive: false });
}

function clientInputPaths(appRoot: string): string[] {
  const paths: string[] = [];
  const visit = (target: string): void => {
    const metadata = statSync(target);
    if (metadata.isDirectory()) {
      for (const name of readdirSync(target).sort()) {
        visit(path.join(target, name));
      }
    } else if (metadata.isFile()) {
      paths.push(target);
    }
  };
  for (const relative of [
    "config",
    "index.html",
    "package-lock.json",
    "package.json",
    "public",
    "src",
    "vite.config.ts",
  ]) {
    visit(path.join(appRoot, relative));
  }
  return paths;
}

export function createClientBuildId(appRoot: string): string {
  const hash = createHash("sha256");
  for (const source of clientInputPaths(appRoot)) {
    hash.update(path.relative(appRoot, source).split(path.sep).join("/"));
    hash.update("\0");
    hash.update(readFileSync(source));
    hash.update("\0");
  }
  return hash.digest("hex");
}

export async function reconcileClientBuildHistory(
  options: ReconcileOptions,
): Promise<ClientBuildHistory> {
  const retain = options.retainGenerations ?? RETAINED_CLIENT_GENERATIONS;
  if (!Number.isSafeInteger(retain) || retain < 1) {
    throw new Error("retained client generations must be a positive integer");
  }
  const existing = await readHistory(options.historyPath);
  const generations = [...(existing?.generations ?? [])];
  if (generations.length === 0) {
    const legacyAssets = normalizeAssets(options.legacyAssets ?? []);
    if (legacyAssets.length > 0) {
      generations.push({
        schema_version: CLIENT_VERSION_SCHEMA,
        build_id: `legacy-before-${options.current.build_id}`,
        built_at: options.current.built_at,
        assets: legacyAssets,
      });
    }
  }
  const distinctGenerations = generations.filter(
    (value) => value.build_id !== options.current.build_id,
  );
  distinctGenerations.push({
    ...options.current,
    assets: normalizeAssets(options.current.assets),
  });
  const retained = distinctGenerations.slice(-retain);
  const retainedAssets = new Set(retained.flatMap((value) => value.assets));
  for (const asset of await existingAssetPaths(options.distDirectory)) {
    if (!retainedAssets.has(asset)) {
      await rm(path.join(options.distDirectory, asset));
    }
  }
  await removeEmptyDirectories(path.join(options.distDirectory, "assets"));
  const history = {
    schema_version: CLIENT_BUILD_HISTORY_SCHEMA,
    generations: retained,
  } satisfies ClientBuildHistory;
  await mkdir(path.dirname(options.historyPath), { recursive: true });
  const temporary = `${options.historyPath}.tmp-${process.pid}-${randomUUID()}`;
  await writeFile(temporary, `${JSON.stringify(history, null, 2)}\n`, "utf8");
  await rename(temporary, options.historyPath);
  return history;
}

export function clientContinuityPlugin(
  version: ClientVersion,
): Plugin {
  let configuration: ResolvedConfig;
  let priorAssets: string[] = [];
  return {
    name: "atpiano-client-continuity",
    apply: "build",
    async buildStart() {
      priorAssets = await existingAssetPaths(configuration.build.outDir);
    },
    configResolved(resolved) {
      configuration = resolved;
    },
    generateBundle() {
      this.emitFile({
        type: "asset",
        fileName: "client-version.json",
        source: `${JSON.stringify(version, null, 2)}\n`,
      });
    },
    async writeBundle(_output, bundle) {
      const assets = Object.keys(bundle).filter(isAssetPath);
      await reconcileClientBuildHistory({
        distDirectory: configuration.build.outDir,
        historyPath: path.join(
          configuration.root,
          ".atpiano-build-history.json",
        ),
        current: { ...version, assets },
        legacyAssets: priorAssets,
      });
    },
  };
}
