import { describe, expect, it } from "vitest";

import {
  sessionIdFromUrl,
  urlForSession,
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
});
