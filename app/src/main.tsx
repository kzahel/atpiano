import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./app.js";
import { HttpAuthenticationClient } from "./auth/auth-client.js";
import { AuthenticationBoundary } from "./auth/authentication-boundary.js";
import { ClientUpdateNotice } from "./client-update.js";
import { createFixtureRuntime } from "./runtime/fixture-data.js";
import {
  createDesktopRuntime,
  isTauriRuntime,
  type DesktopRuntimeBootstrap,
} from "./runtime/desktop-runtime.js";
import { LocalRuntime } from "./runtime/local-runtime.js";
import type { AtpianoRuntime } from "./runtime/atpiano-runtime.js";
import { RuntimeProvider } from "./runtime/runtime-context.js";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function Root({
  runtime,
  desktop,
  viewer,
}: {
  readonly runtime: AtpianoRuntime;
  readonly desktop?: DesktopRuntimeBootstrap;
  readonly viewer?: {
    readonly username: string;
    readonly displayName: string;
    readonly canWrite: boolean;
    readonly logoutPending: boolean;
    readonly onLogout: () => void;
  };
}) {
  const [failure, setFailure] = useState<string | null>(null);
  useEffect(() => {
    if (!desktop) return;
    let disposed = false;
    let unlisten: (() => void) | undefined;
    void desktop.monitor((message) => {
      if (!disposed) setFailure(message);
    }).then((release) => {
      if (disposed) release();
      else unlisten = release;
    });
    return () => {
      disposed = true;
      unlisten?.();
    };
  }, [desktop]);
  if (failure !== null) {
    return (
      <main className="bootstrap-failure">
        <p className="eyebrow">Local engine stopped</p>
        <h1>Atpiano needs to restart</h1>
        <p>{failure}</p>
        <button type="button" onClick={() => window.location.reload()}>
          Restart the local engine
        </button>
      </main>
    );
  }
  return (
    <QueryClientProvider client={queryClient}>
      <RuntimeProvider runtime={runtime}>
        <App viewer={viewer} />
      </RuntimeProvider>
    </QueryClientProvider>
  );
}

function render(
  runtime: AtpianoRuntime,
  desktop?: DesktopRuntimeBootstrap,
) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <ClientUpdateNotice />
      <Root runtime={runtime} desktop={desktop} />
    </StrictMode>,
  );
}

function renderAuthenticated(
  runtime: AtpianoRuntime,
  client: HttpAuthenticationClient,
  initialSession: Awaited<ReturnType<typeof client.login>> | null,
) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <ClientUpdateNotice />
      <AuthenticationBoundary
        client={client}
        initialSession={initialSession}
        onLogout={() => queryClient.clear()}
        renderAuthenticated={(session, logout, logoutPending) => (
          <Root
            runtime={runtime}
            viewer={{
              username: session.principal.username,
              displayName: session.principal.display_name,
              canWrite: session.principal.memberships.some(
                (membership) =>
                  membership.workspace_id === "local" &&
                  membership.role !== "viewer",
              ),
              logoutPending,
              onLogout: logout,
            }}
          />
        )}
      />
    </StrictMode>,
  );
}

async function main() {
  const runtimeChoice =
    new URLSearchParams(window.location.search).get("runtime");
  if (isTauriRuntime() && runtimeChoice !== "fixture") {
    const desktop = await createDesktopRuntime();
    render(desktop.runtime, desktop);
    return;
  }
  const runtime =
    runtimeChoice === "fixture" ||
    (import.meta.env.DEV && runtimeChoice !== "local")
      ? createFixtureRuntime()
      : new LocalRuntime();
  if (runtimeChoice === "fixture" || (
    import.meta.env.DEV && runtimeChoice !== "local"
  )) {
    render(runtime);
    return;
  }
  const authentication = new HttpAuthenticationClient();
  const bootstrap = await authentication.bootstrap();
  if (bootstrap.mode === "bypass") {
    render(runtime);
    return;
  }
  renderAuthenticated(runtime, authentication, bootstrap.session);
}

void main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  createRoot(document.getElementById("root")!).render(
    <main className="bootstrap-failure">
      <p className="eyebrow">Local engine unavailable</p>
      <h1>Atpiano could not start</h1>
      <p>{message}</p>
      <button type="button" onClick={() => window.location.reload()}>
        Try again
      </button>
    </main>,
  );
});
