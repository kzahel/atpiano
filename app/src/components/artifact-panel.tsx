import type { Artifact } from "../runtime/atpiano-runtime.js";

function artifactLabel(
  artifact: Artifact,
  baselineScoreArtifactId: string | undefined,
  selectedScoreArtifactId: string | undefined,
): string {
  if (artifact.kind === "audio") {
    return artifact.media_type === "audio/mpeg"
      ? "Playback audio"
      : "Lossless source audio";
  }
  if (artifact.kind === "midi") return "Performance MIDI";
  if (artifact.kind === "musicxml") {
    if (artifact.artifact_id === baselineScoreArtifactId) {
      return "Original model MusicXML";
    }
    if (artifact.artifact_id === selectedScoreArtifactId) {
      return "Current MusicXML score";
    }
    return "Alternate MusicXML score";
  }
  if (artifact.kind === "score-alignment") return "Score playback alignment";
  if (artifact.kind === "event-history") return "Event history";
  return artifact.filename;
}

export function ArtifactPanel({
  artifacts,
  baselineScoreArtifactId,
  selectedScoreArtifactId,
  error,
  onDownload,
}: {
  readonly artifacts: readonly Artifact[];
  readonly baselineScoreArtifactId: string | undefined;
  readonly selectedScoreArtifactId: string | undefined;
  readonly error: string | null;
  readonly onDownload: (artifact: Artifact) => void;
}) {
  return (
    <section className="artifact-panel" aria-labelledby="artifacts-title">
      <div>
        <p className="eyebrow">Session evidence</p>
        <h3 id="artifacts-title">Exports</h3>
      </div>
      {error && <p className="surface-feedback error" role="alert">{error}</p>}
      {artifacts.length ? (
        <div className="artifact-list">
          {artifacts.map((artifact) => (
            <button
              type="button"
              key={artifact.artifact_id}
              onClick={() => onDownload(artifact)}
            >
              <span aria-hidden="true">↓</span>
              <strong>
                {artifactLabel(
                  artifact,
                  baselineScoreArtifactId,
                  selectedScoreArtifactId,
                )}
              </strong>
              <small>{artifact.sha256.slice(0, 8)} · {artifact.filename}</small>
            </button>
          ))}
        </div>
      ) : (
        <p className="empty-copy">
          Exports appear after the session finishes and its corrected tail
          settles.
        </p>
      )}
    </section>
  );
}
