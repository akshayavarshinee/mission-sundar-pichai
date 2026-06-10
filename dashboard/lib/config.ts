/** Resolve public API base for REST + SSE. Empty string = same-origin (Vercel proxy). */
export function resolveApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE;
  if (raw === "" || raw === "/") return "";
  if (raw) return raw.replace(/\/$/, "");
  return "http://localhost:8080";
}

/** Server-only upstream for Vercel rewrites / streaming proxies. */
export function backendUpstream(): string {
  const upstream =
    process.env.BACKEND_UPSTREAM ??
    process.env.CLEARPORT_BACKEND_UPSTREAM ??
    "";
  return upstream.replace(/\/$/, "");
}
