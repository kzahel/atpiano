import { describe, expect, it, vi } from "vitest";

import {
  HttpAuthenticationClient,
  type AuthSession,
} from "../../src/auth/auth-client.js";

const session: AuthSession = {
  schema_version: "atpiano.contract.v1",
  authenticated: true,
  principal: {
    schema_version: "atpiano.contract.v1",
    user_id: "user:alice",
    username: "alice",
    display_name: "Alice",
    memberships: [],
    group_memberships: [],
  },
};

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("authentication client", () => {
  it("invokes browser fetch with the global receiver", async () => {
    let receiver: unknown;
    const fetchImplementation = function (this: unknown) {
      receiver = this;
      return Promise.resolve(jsonResponse({}, 401));
    } as typeof fetch;
    const client = new HttpAuthenticationClient(fetchImplementation);

    await expect(client.bootstrap()).resolves.toEqual({
      mode: "required",
      session: null,
    });
    expect(receiver).toBe(globalThis);
  });

  it("bypasses legacy local servers and requests login after 401", async () => {
    const legacy = new HttpAuthenticationClient(
      vi.fn(async () => jsonResponse({}, 404)),
    );
    const family = new HttpAuthenticationClient(
      vi.fn(async () => jsonResponse({}, 401)),
    );

    await expect(legacy.bootstrap()).resolves.toEqual({ mode: "bypass" });
    await expect(family.bootstrap()).resolves.toEqual({
      mode: "required",
      session: null,
    });
  });

  it("uses same-origin cookie requests for login and logout", async () => {
    const requests: Request[] = [];
    const fetchImplementation: typeof fetch = async (input, init) => {
      const request = new Request(
        new URL(
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.href
              : input.url,
          "https://family.test",
        ),
        init,
      );
      requests.push(request);
      return request.url.endsWith("/logout")
        ? jsonResponse({ logged_out: true })
        : jsonResponse(session);
    };
    const client = new HttpAuthenticationClient(fetchImplementation);

    await expect(client.login("alice", "private password")).resolves.toEqual(
      session,
    );
    await client.logout();

    expect(requests.map((request) => request.credentials)).toEqual([
      "same-origin",
      "same-origin",
    ]);
    expect(await requests[0]!.json()).toEqual({
      schema_version: "atpiano.contract.v1",
      username: "alice",
      password: "private password",
    });
    expect(requests[1]!.method).toBe("POST");
  });

  it("returns the server's bounded authentication error", async () => {
    const client = new HttpAuthenticationClient(
      vi.fn(async () =>
        jsonResponse(
          { error: { message: "username or password is incorrect" } },
          401,
        )
      ),
    );

    await expect(client.login("alice", "wrong")).rejects.toThrow(
      "username or password is incorrect",
    );
  });
});
