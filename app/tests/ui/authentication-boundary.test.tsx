import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type {
  AuthenticationClient,
  AuthSession,
} from "../../src/auth/auth-client.js";
import { AuthenticationBoundary } from "../../src/auth/authentication-boundary.js";

const session: AuthSession = {
  schema_version: "atpiano.contract.v1",
  authenticated: true,
  principal: {
    schema_version: "atpiano.contract.v1",
    user_id: "user:alice",
    username: "alice",
    display_name: "Alice",
    memberships: [],
  },
};

describe("authentication boundary", () => {
  it("logs in, clears the password field, and logs out", async () => {
    const user = userEvent.setup();
    const login = vi.fn(async () => session);
    const logout = vi.fn(async () => undefined);
    const client: AuthenticationClient = {
      bootstrap: vi.fn(),
      login,
      logout,
    };
    const onLogout = vi.fn();
    render(
      <AuthenticationBoundary
        client={client}
        initialSession={null}
        onLogout={onLogout}
        renderAuthenticated={(current, signOut) => (
          <section>
            <h1>Hello {current.principal.display_name}</h1>
            <button type="button" onClick={signOut}>Logout</button>
          </section>
        )}
      />,
    );

    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "private password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Hello Alice" }))
      .toBeTruthy();
    expect(login).toHaveBeenCalledWith("alice", "private password");
    expect(screen.queryByDisplayValue("private password")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Logout" }));

    expect(await screen.findByRole("heading", { name: "Sign in to Atpiano" }))
      .toBeTruthy();
    expect(logout).toHaveBeenCalledOnce();
    expect(onLogout).toHaveBeenCalledOnce();
    expect(
      (screen.getByLabelText("Username") as HTMLInputElement).value,
    ).toBe("");
    expect(
      (screen.getByLabelText("Password") as HTMLInputElement).value,
    ).toBe("");
  });

  it("shows a generic server failure and clears the password", async () => {
    const user = userEvent.setup();
    const client: AuthenticationClient = {
      bootstrap: vi.fn(),
      login: vi.fn(async () => {
        throw new Error("username or password is incorrect");
      }),
      logout: vi.fn(),
    };
    render(
      <AuthenticationBoundary
        client={client}
        initialSession={null}
        renderAuthenticated={() => null}
      />,
    );

    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "wrong password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "username or password is incorrect",
    );
    expect(
      (screen.getByLabelText("Password") as HTMLInputElement).value,
    ).toBe("");
  });
});
