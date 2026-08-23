import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { relaunch } from "@tauri-apps/plugin-process";

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
  readonly scoreRuntime: DesktopScoreRuntimeManager;
  monitor(onFailure: (message: string) => void): Promise<UnlistenFn>;
}

export interface DesktopScoreRuntimeStatus {
  readonly state: "not-installed" | "installing" | "available" | "invalid";
  readonly contractId: string;
  readonly noticeVersion: string;
  readonly modelName: string;
  readonly sourceCommit: string;
  readonly checkpointSha256: string;
  readonly supportLayerId: string;
  readonly executionBackend: "cpu";
  readonly purpose: string;
  readonly notice: string;
  readonly acknowledgement: string;
  readonly repositoryUrl: string;
  readonly checkpointReleaseUrl: string;
  readonly paperUrl: string;
  readonly sourceBytes: number;
  readonly checkpointBytes: number;
  readonly downloadBytes: number;
  readonly installedSpaceEstimateBytes: number;
  readonly minimumFreeBytes: number;
  readonly supportAvailable: boolean;
  readonly installedBytes: number | null;
  readonly error: string | null;
}

export interface DesktopScoreAcquisitionProgress {
  readonly phase:
    | "preparing"
    | "source"
    | "verifying-source"
    | "checkpoint"
    | "installing"
    | "complete";
  readonly completedBytes: number;
  readonly totalBytes: number;
}

export type DesktopScoreLinkId =
  | "repository"
  | "checkpoint"
  | "paper"
  | "acquisition-record";

export interface DesktopScoreRuntimeClient {
  status(): Promise<DesktopScoreRuntimeStatus>;
  acquire(): Promise<DesktopScoreRuntimeStatus>;
  cancel(): Promise<boolean>;
  remove(): Promise<DesktopScoreRuntimeStatus>;
  openLink(linkId: DesktopScoreLinkId): Promise<void>;
  monitor(
    onProgress: (progress: DesktopScoreAcquisitionProgress) => void,
  ): Promise<UnlistenFn>;
  relaunch(): Promise<void>;
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

export class DesktopScoreRuntimeManager implements DesktopScoreRuntimeClient {
  status(): Promise<DesktopScoreRuntimeStatus> {
    return invoke<DesktopScoreRuntimeStatus>("desktop_score_runtime_status");
  }

  acquire(): Promise<DesktopScoreRuntimeStatus> {
    return invoke<DesktopScoreRuntimeStatus>("desktop_score_acquire", {
      acknowledged: true,
    });
  }

  cancel(): Promise<boolean> {
    return invoke<boolean>("desktop_score_cancel");
  }

  remove(): Promise<DesktopScoreRuntimeStatus> {
    return invoke<DesktopScoreRuntimeStatus>("desktop_score_remove");
  }

  openLink(linkId: DesktopScoreLinkId): Promise<void> {
    return invoke<void>("desktop_score_open_link", { linkId });
  }

  monitor(
    onProgress: (progress: DesktopScoreAcquisitionProgress) => void,
  ): Promise<UnlistenFn> {
    return listen<DesktopScoreAcquisitionProgress>(
      "desktop-score-acquisition-progress",
      (event) => onProgress(event.payload),
    );
  }

  async relaunch(): Promise<void> {
    await invoke<void>("desktop_prepare_update_install");
    await relaunch();
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
    scoreRuntime: new DesktopScoreRuntimeManager(),
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
