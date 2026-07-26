import { createContext, type ReactNode, useContext } from "react";

import type { AtpianoRuntime } from "./atpiano-runtime.js";

const RuntimeContext = createContext<AtpianoRuntime | null>(null);

export function RuntimeProvider({
  runtime,
  children,
}: {
  readonly runtime: AtpianoRuntime;
  readonly children: ReactNode;
}) {
  return (
    <RuntimeContext.Provider value={runtime}>
      {children}
    </RuntimeContext.Provider>
  );
}

export function useRuntime(): AtpianoRuntime {
  const runtime = useContext(RuntimeContext);
  if (runtime === null) {
    throw new Error("AtpianoRuntime provider is missing");
  }
  return runtime;
}
