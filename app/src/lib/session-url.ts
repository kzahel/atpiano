export function sessionIdFromUrl(url: string): string | null {
  const value = new URL(url).searchParams.get("session")?.trim();
  return value ? value : null;
}

export function urlForSession(url: string, sessionId: string | null): string {
  const next = new URL(url);
  if (sessionId) next.searchParams.set("session", sessionId);
  else next.searchParams.delete("session");
  return `${next.pathname}${next.search}${next.hash}`;
}
