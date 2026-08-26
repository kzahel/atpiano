import { type FormEvent, type ReactNode, useState } from "react";

import type {
  AuthenticationClient,
  AuthSession,
} from "./auth-client.js";
import { ThemeToggle } from "../components/theme-toggle.js";

export function AuthenticationBoundary({
  client,
  initialSession,
  onLogout,
  renderAuthenticated,
}: {
  readonly client: AuthenticationClient;
  readonly initialSession: AuthSession | null;
  readonly onLogout?: () => void;
  readonly renderAuthenticated: (
    session: AuthSession,
    logout: () => void,
    logoutPending: boolean,
  ) => ReactNode;
}) {
  const [session, setSession] = useState(initialSession);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [logoutPending, setLogoutPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const submittedPassword = password;
    setPassword("");
    setPending(true);
    setError(null);
    try {
      setSession(await client.login(username.trim(), submittedPassword));
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Authentication is temporarily unavailable.",
      );
    } finally {
      setPending(false);
    }
  };

  const logout = async () => {
    if (logoutPending) return;
    setLogoutPending(true);
    setError(null);
    try {
      await client.logout();
      onLogout?.();
      setSession(null);
      setUsername("");
      setPassword("");
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Logout is temporarily unavailable.",
      );
    } finally {
      setLogoutPending(false);
    }
  };

  if (session !== null) {
    return renderAuthenticated(
      session,
      () => void logout(),
      logoutPending,
    );
  }

  return (
    <main className="login-shell">
      <section className="login-card" aria-labelledby="login-title">
        <ThemeToggle />
        <div className="login-brand" aria-hidden="true">♪</div>
        <p className="eyebrow">Private family workspace</p>
        <h1 id="login-title">Sign in to Atpiano</h1>
        <p className="login-introduction">
          Review performances and record the piano while the home workspace
          is online.
        </p>
        <form onSubmit={(event) => void submit(event)}>
          <label>
            Username
            <input
              autoComplete="username"
              autoFocus
              disabled={pending}
              maxLength={64}
              name="username"
              required
              value={username}
              onChange={(event) => setUsername(event.currentTarget.value)}
            />
          </label>
          <label>
            Password
            <input
              autoComplete="current-password"
              disabled={pending}
              maxLength={1024}
              name="password"
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
            />
          </label>
          {error !== null && (
            <p className="login-error" role="alert">{error}</p>
          )}
          <button
            className="button primary"
            disabled={pending}
            type="submit"
          >
            {pending ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <small>
          Accounts are created locally by the workspace administrator.
        </small>
      </section>
    </main>
  );
}
