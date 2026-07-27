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
  const content = await runtime.readArtifact(
    workspaceId,
    sessionId,
    artifactId,
    {
      requestId: requestId("artifact-content"),
      ...(signal ? { signal } : {}),
    },
  );
  const actualSha256 = hexadecimal(
    await window.crypto.subtle.digest("SHA-256", content.bytes),
  );
  if (actualSha256 !== expectedSha256) {
    throw new Error(
      `Pinned artifact checksum mismatch: expected ${expectedSha256}, received ${actualSha256}.`,
    );
  }
  return new TextDecoder().decode(content.bytes);
}
