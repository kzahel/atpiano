import { useCallback, useEffect, useState } from "react";

export const CLIENT_VERSION_SCHEMA = "atpiano.client-version.v1";
export const CLIENT_UPDATE_EVENT = "atpiano:client-update-required";
export const CLIENT_VERSION_POLL_MS = 60_000;

interface ClientVersion {
  readonly schema_version: typeof CLIENT_VERSION_SCHEMA;
  readonly build_id: string;
  readonly built_at: string;
}

interface ClientUpdateEventDetail {
  readonly urgent: boolean;
}

function validClientVersion(value: unknown): value is ClientVersion {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.schema_version === CLIENT_VERSION_SCHEMA &&
    typeof candidate.build_id === "string" &&
    candidate.build_id.length > 0 &&
    typeof candidate.built_at === "string"
  );
}

export async function fetchClientVersion(
  fetcher: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<ClientVersion | null> {
  try {
    const response = await fetcher(
      `/client-version.json?current=${encodeURIComponent(__ATPIANO_BUILD_ID__)}`,
      {
        cache: "no-store",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      },
    );
    if (!response.ok) return null;
    const value: unknown = await response.json();
    return validClientVersion(value) ? value : null;
  } catch {
    return null;
  }
}

export function isClientAssetLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return [
    "Failed to fetch dynamically imported module",
    "Importing a module script failed",
    "error loading dynamically imported module",
    "Unable to preload CSS",
    "Load failed",
  ].some((fragment) => message.includes(fragment));
}

export function reportClientAssetLoadError(error: unknown): boolean {
  if (!isClientAssetLoadError(error)) return false;
  window.dispatchEvent(
    new CustomEvent<ClientUpdateEventDetail>(CLIENT_UPDATE_EVENT, {
      detail: { urgent: true },
    }),
  );
  return true;
}

export function ClientUpdateNotice() {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [urgent, setUrgent] = useState(false);

  const check = useCallback(async () => {
    const version = await fetchClientVersion();
    if (
      version !== null &&
      version.build_id !== __ATPIANO_BUILD_ID__
    ) {
      setUpdateAvailable(true);
    }
  }, []);

  useEffect(() => {
    const required = (event: Event) => {
      const detail = (event as CustomEvent<ClientUpdateEventDetail>).detail;
      setUpdateAvailable(true);
      setUrgent(detail?.urgent === true);
    };
    const focused = () => void check();
    const visible = () => {
      if (document.visibilityState === "visible") void check();
    };
    window.addEventListener(CLIENT_UPDATE_EVENT, required);
    window.addEventListener("focus", focused);
    document.addEventListener("visibilitychange", visible);
    void check();
    const interval = window.setInterval(() => void check(), CLIENT_VERSION_POLL_MS);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener(CLIENT_UPDATE_EVENT, required);
      window.removeEventListener("focus", focused);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [check]);

  if (!updateAvailable) return null;
  return (
    <aside
      className={`client-update-notice${urgent ? " urgent" : ""}`}
      role={urgent ? "alert" : "status"}
    >
      <span>
        {urgent
          ? "Atpiano was updated. Reload this page to continue."
          : "A newer Atpiano version is ready."}
      </span>
      <button type="button" onClick={() => window.location.reload()}>
        Reload
      </button>
    </aside>
  );
}
