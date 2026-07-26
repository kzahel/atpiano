import { describe, expect, it } from "vitest";

import {
  scoreReaderRouteFromUrl,
  sessionIdFromUrl,
  urlForScoreReader,
  urlForSession,
  urlWithoutScoreReader,
} from "../../src/lib/session-url.js";

describe("session URL", () => {
  it("round-trips an opaque session ID", () => {
    const path = urlForSession(
      "http://127.0.0.1:8123/?view=roll",
      "20260726T114525-d82bfe1f7822",
    );

    expect(path).toBe(
      "/?view=roll&session=20260726T114525-d82bfe1f7822",
    );
    expect(sessionIdFromUrl(`http://127.0.0.1:8123${path}`)).toBe(
      "20260726T114525-d82bfe1f7822",
    );
  });

  it("removes only the session target for New", () => {
    expect(
      urlForSession(
        "http://127.0.0.1:8123/?session=old&view=score",
        null,
      ),
    ).toBe("/?view=score");
  });

  it("pins and removes an exact score-reader target", () => {
    const route = {
      artifactId: "artifact:score-one",
      sha256: "a".repeat(64),
      sourceHorizonSample: 96_000,
      alignmentArtifactId: "artifact:alignment-one",
    };
    const path = urlForScoreReader(
      "http://127.0.0.1:8123/?session=session-one",
      route,
    );

    expect(
      scoreReaderRouteFromUrl(`http://127.0.0.1:8123${path}`),
    ).toEqual(route);
    expect(
      urlWithoutScoreReader(`http://127.0.0.1:8123${path}`),
    ).toBe("/?session=session-one");
  });

  it("rejects an incomplete score-reader target", () => {
    expect(
      scoreReaderRouteFromUrl(
        "http://127.0.0.1:8123/?view=score&score=artifact",
      ),
    ).toBeNull();
  });
});
