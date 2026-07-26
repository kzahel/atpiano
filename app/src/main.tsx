import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./app.js";
import { createFixtureRuntime } from "./runtime/fixture-data.js";
import { LocalRuntime } from "./runtime/local-runtime.js";
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

const runtimeChoice = new URLSearchParams(window.location.search).get("runtime");
const runtime =
  runtimeChoice === "fixture" || (import.meta.env.DEV && runtimeChoice !== "local")
    ? createFixtureRuntime()
    : new LocalRuntime();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RuntimeProvider runtime={runtime}>
        <App />
      </RuntimeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
