import type { components } from "../generated/schema.js";

type AuthSession = components["schemas"]["AuthSession"];

export type AuthenticationBootstrap =
  | { readonly mode: "bypass" }
  | {
      readonly mode: "required";
      readonly session: AuthSession | null;
    };

export interface AuthenticationClient {
  bootstrap(): Promise<AuthenticationBootstrap>;
  login(username: string, password: string): Promise<AuthSession>;
  logout(): Promise<void>;
}

function isAuthSession(value: unknown): value is AuthSession {
  if (typeof value !== "object" || value === null) return false;
  if (!("authenticated" in value) || value.authenticated !== true) {
    return false;
  }
  if (!("principal" in value)) return false;
  const principal = value.principal;
  return (
    typeof principal === "object" &&
    principal !== null &&
    "username" in principal &&
    typeof principal.username === "string" &&
    "display_name" in principal &&
    typeof principal.display_name === "string"
  );
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const value = await response.json() as unknown;
    if (
      typeof value === "object" &&
      value !== null &&
      "error" in value &&
      typeof value.error === "object" &&
      value.error !== null &&
      "message" in value.error
    ) {
      return String(value.error.message);
    }
  } catch {
    // Use the bounded generic message below.
  }
  return "Authentication is temporarily unavailable.";
}

export class HttpAuthenticationClient implements AuthenticationClient {
  readonly #fetch: typeof fetch;

  constructor(fetchImplementation: typeof fetch = globalThis.fetch) {
    this.#fetch = fetchImplementation.bind(globalThis);
  }

  async bootstrap(): Promise<AuthenticationBootstrap> {
    const response = await this.#fetch("/api/v1/auth/session", {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (response.status === 404) return { mode: "bypass" };
    if (response.status === 401) {
      return { mode: "required", session: null };
    }
    if (!response.ok) throw new Error(await errorMessage(response));
    const value = await response.json() as unknown;
    if (!isAuthSession(value)) {
      throw new Error("The authentication response is incompatible.");
    }
    return { mode: "required", session: value };
  }

  async login(username: string, password: string): Promise<AuthSession> {
    const response = await this.#fetch("/api/v1/auth/login", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        schema_version: "atpiano.contract.v1",
        username,
        password,
      }),
    });
    if (!response.ok) throw new Error(await errorMessage(response));
    const value = await response.json() as unknown;
    if (!isAuthSession(value)) {
      throw new Error("The authentication response is incompatible.");
    }
    return value;
  }

  async logout(): Promise<void> {
    const response = await this.#fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(await errorMessage(response));
  }
}

export type { AuthSession };
