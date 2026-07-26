export function sessionIdFromUrl(url: string): string | null {
  const value = new URL(url).searchParams.get("session")?.trim();
  return value ? value : null;
}

export interface ScoreReaderRoute {
  readonly artifactId: string;
  readonly sha256: string;
  readonly sourceHorizonSample: number;
  readonly alignmentArtifactId: string | null;
}

export function scoreReaderRouteFromUrl(url: string): ScoreReaderRoute | null {
  const parameters = new URL(url).searchParams;
  if (parameters.get("view") !== "score") return null;
  const artifactId = parameters.get("score")?.trim() ?? "";
  const sha256 = parameters.get("score_sha")?.trim() ?? "";
  const horizon = parameters.get("score_horizon")?.trim() ?? "";
  const sourceHorizonSample = Number(horizon);
  if (
    !artifactId ||
    !/^[0-9a-f]{64}$/.test(sha256) ||
    !/^\d+$/.test(horizon) ||
    !Number.isSafeInteger(sourceHorizonSample)
  ) {
    return null;
  }
  return {
    artifactId,
    sha256,
    sourceHorizonSample,
    alignmentArtifactId:
      parameters.get("alignment")?.trim() || null,
  };
}

export function urlForScoreReader(
  url: string,
  route: ScoreReaderRoute,
): string {
  const next = new URL(url);
  next.searchParams.set("view", "score");
  next.searchParams.set("score", route.artifactId);
  next.searchParams.set("score_sha", route.sha256);
  next.searchParams.set(
    "score_horizon",
    String(route.sourceHorizonSample),
  );
  if (route.alignmentArtifactId) {
    next.searchParams.set("alignment", route.alignmentArtifactId);
  } else {
    next.searchParams.delete("alignment");
  }
  return `${next.pathname}${next.search}${next.hash}`;
}

export function urlWithoutScoreReader(url: string): string {
  const next = new URL(url);
  for (const key of [
    "view",
    "score",
    "score_sha",
    "score_horizon",
    "alignment",
  ]) {
    next.searchParams.delete(key);
  }
  return `${next.pathname}${next.search}${next.hash}`;
}

export function urlForSession(url: string, sessionId: string | null): string {
  const next = new URL(url);
  if (sessionId) next.searchParams.set("session", sessionId);
  else next.searchParams.delete("session");
  return `${next.pathname}${next.search}${next.hash}`;
}
