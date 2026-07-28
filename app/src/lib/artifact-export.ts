import type {
  ArtifactContent,
  ArtifactExportResult,
} from "../runtime/atpiano-runtime.js";

export function startBrowserArtifactExport(
  content: ArtifactContent,
): ArtifactExportResult {
  const url = URL.createObjectURL(
    new Blob([content.bytes], { type: content.access.media_type }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = content.access.download_name;
  link.hidden = true;
  document.body.append(link);
  try {
    link.click();
  } finally {
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
  }
  return {
    outcome: "download-started",
    fileName: content.access.download_name,
  };
}
