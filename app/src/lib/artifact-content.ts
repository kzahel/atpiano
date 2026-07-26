import { requestId } from "./format.js";
import type { AtpianoRuntime } from "../runtime/atpiano-runtime.js";

function hexadecimal(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

export async function artifactText(
  runtime: AtpianoRuntime,
  workspaceId: string,
  sessionId: string,
  artifactId: string,
  expectedSha256: string,
  signal?: AbortSignal,
): Promise<string> {
  const access = await runtime.getArtifactAccess(
    workspaceId,
    sessionId,
    artifactId,
    {
      requestId: requestId("artifact-content"),
      ...(signal ? { signal } : {}),
    },
  );
  const response = await fetch(
    new URL(access.url, window.location.origin),
    signal ? { signal } : undefined,
  );
  if (!response.ok) {
    throw new Error(`Artifact download failed: HTTP ${response.status}`);
  }
  const content = await response.arrayBuffer();
  const actualSha256 = hexadecimal(
    await window.crypto.subtle.digest("SHA-256", content),
  );
  if (actualSha256 !== expectedSha256) {
    throw new Error(
      `Pinned artifact checksum mismatch: expected ${expectedSha256}, received ${actualSha256}.`,
    );
  }
  return new TextDecoder().decode(content);
}
