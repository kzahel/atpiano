import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import { LocalRuntime } from "./local-runtime.js";

const desktopProtocol = "atpiano.desktop.v1";
const contractSchema = "atpiano.contract.v1";
const tokenPattern = /^[0-9a-f]{64}$/;

interface DesktopRuntimeInfo {
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
}

export interface DesktopRuntimeBootstrap {
  readonly runtime: LocalRuntime;
  monitor(onFailure: (message: string) => void): Promise<UnlistenFn>;
}

export function isTauriRuntime(): boolean {
  return "__TAURI_INTERNALS__" in window;
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
    value.platform !== "macos" ||
    value.architecture !== "arm64" ||
    value.executionBackend !== "cpu" ||
    !tokenPattern.test(value.bearerToken) ||
    value.webSocketProtocol !== `${desktopProtocol}.${value.bearerToken}` ||
    !tokenPattern.test(value.modelPackSha256) ||
    !value.sidecarVersion ||
    !value.modelPackId
  ) {
    throw new Error("The desktop engine compatibility record is invalid.");
  }
  return value;
}

export async function createDesktopRuntime(): Promise<DesktopRuntimeBootstrap> {
  const info = validateRuntimeInfo(
    await invoke<DesktopRuntimeInfo>("desktop_runtime"),
  );
  return {
    runtime: new LocalRuntime({
      baseUrl: info.baseUrl,
      bearerToken: info.bearerToken,
      webSocketProtocol: info.webSocketProtocol,
    }),
    monitor: (onFailure) =>
      listen<string>("desktop-runtime-failed", (event) => {
        onFailure(event.payload);
      }),
  };
}
