import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

import {
  CLIENT_VERSION_SCHEMA,
  clientContinuityPlugin,
  createClientBuildId,
} from "./config/client-continuity.js";

const clientVersion = {
  schema_version: CLIENT_VERSION_SCHEMA,
  build_id: createClientBuildId(
    fileURLToPath(new URL(".", import.meta.url)),
  ),
  built_at: new Date().toISOString(),
} as const;

export default defineConfig({
  plugins: [react(), clientContinuityPlugin(clientVersion)],
  define: {
    __ATPIANO_BUILD_ID__: JSON.stringify(clientVersion.build_id),
  },
  build: {
    outDir: "dist",
    emptyOutDir: false,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    include: ["tests/ui/**/*.test.{ts,tsx}"],
    setupFiles: ["./tests/setup.ts"],
  },
});
