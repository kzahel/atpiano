import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import { LocalRuntime } from "./local-runtime.js";
import type {
  ArtifactExportResult,
  RuntimeRequest,
} from "./atpiano-runtime.js";

const desktopProtocol = "atpiano.desktop.v1";
const contractSchema = "atpiano.contract.v1";
const tokenPattern = /^[0-9a-f]{64}$/;

interface DesktopRuntimeInfo {
  readonly appVersion: string;
  readonly baseUrl: string;
  readonly bearerToken: string;
  readonly webSocketProtocol: string;
  readonly protocolVersion: string;
  readonly contractSchemaVersion: string;
  readonly sidecarVersion: string;
  readonly platform: string;
  readonly architecture: string;
  readonly executionBackend: string;
  readonly modelPackId: string;
  readonly modelPackSha256: string;
  readonly scoreAvailable: boolean;
  readonly installationId: string;
  readonly packageType: string;
  readonly updateEndpoint: string;
}

export interface DesktopReleaseInfo {
  readonly appVersion: string;
  readonly webClientBuildId: string;
  readonly sidecarVersion: string;
  readonly modelPackId: string;
  readonly modelPackSha256: string;
  readonly installationId: string;
  readonly packageType: "app" | "nsis";
  readonly updateEndpoint: string;
  readonly platform: string;
  readonly architecture: string;
}

export interface DesktopRuntimeBootstrap {
  readonly runtime: DesktopRuntime;
  readonly releaseInfo: DesktopReleaseInfo;
  monitor(onFailure: (message: string) => void): Promise<UnlistenFn>;
}

interface DesktopArtifactExportResult {
  readonly saved: boolean;
  readonly fileName: string | null;
}

export function isTauriRuntime(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

export function isSupportedDesktopRelease(
  platform: string,
  architecture: string,
  packageType: string,
): packageType is DesktopReleaseInfo["packageType"] {
  return (
    platform === "macos" && architecture === "arm64" && packageType === "app"
  ) || (
    platform === "windows" &&
    architecture === "x86_64" &&
    packageType === "nsis"
  );
}

function validateRuntimeInfo(value: DesktopRuntimeInfo): DesktopRuntimeInfo {
  const baseUrl = new URL(value.baseUrl);
  if (
    baseUrl.protocol !== "http:" ||
    baseUrl.hostname !== "127.0.0.1" ||
    baseUrl.pathname !== "/" ||
    baseUrl.search ||
    baseUrl.hash
  ) {
    throw new Error("The desktop engine returned an invalid loopback URL.");
  }
  if (
    value.protocolVersion !== desktopProtocol ||
    value.contractSchemaVersion !== contractSchema ||
    !isSupportedDesktopRelease(
      value.platform,
      value.architecture,
      value.packageType,
    ) ||
    value.executionBackend !== "cpu" ||
    !tokenPattern.test(value.bearerToken) ||
    value.webSocketProtocol !== `${desktopProtocol}.${value.bearerToken}` ||
    !tokenPattern.test(value.modelPackSha256) ||
    typeof value.scoreAvailable !== "boolean" ||
    !/^\d+\.\d+\.\d+$/.test(value.appVersion) ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value.installationId,
    ) ||
    value.updateEndpoint !==
      "https://updates.graehlarts.com/atpiano/tauri/{{target}}/{{arch}}/{{current_version}}" ||
    !value.sidecarVersion ||
    !value.modelPackId
  ) {
    throw new Error("The desktop engine compatibility record is invalid.");
  }
  return value;
}

export class DesktopRuntime extends LocalRuntime {
  async exportArtifact(
    workspaceId: string,
    sessionId: string,
    artifactId: string,
    request: RuntimeRequest,
  ): Promise<ArtifactExportResult> {
    const access = await this.getArtifactAccess(
      workspaceId,
      sessionId,
      artifactId,
      request,
    );
    const result = await invoke<DesktopArtifactExportResult>(
      "desktop_export_artifact",
      {
        artifactUrl: access.url,
        suggestedName: access.download_name,
      },
    );
    return {
      outcome: result.saved ? "saved" : "cancelled",
      fileName: result.fileName,
    };
  }
}

export async function createDesktopRuntime(): Promise<DesktopRuntimeBootstrap> {
  const info = validateRuntimeInfo(
    await invoke<DesktopRuntimeInfo>("desktop_runtime"),
  );
  return {
    runtime: new DesktopRuntime({
      baseUrl: info.baseUrl,
      bearerToken: info.bearerToken,
      webSocketProtocol: info.webSocketProtocol,
    }),
    releaseInfo: {
      appVersion: info.appVersion,
      webClientBuildId: __ATPIANO_BUILD_ID__,
      sidecarVersion: info.sidecarVersion,
      modelPackId: info.modelPackId,
      modelPackSha256: info.modelPackSha256,
      installationId: info.installationId,
      packageType: info.packageType as DesktopReleaseInfo["packageType"],
      updateEndpoint: info.updateEndpoint,
      platform: info.platform,
      architecture: info.architecture,
    },
    monitor: (onFailure) =>
      listen<string>("desktop-runtime-failed", (event) => {
        onFailure(event.payload);
      }),
  };
}
