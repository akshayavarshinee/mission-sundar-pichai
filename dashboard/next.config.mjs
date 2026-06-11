/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080",
    NEXT_PUBLIC_PHOENIX_BASE: process.env.NEXT_PUBLIC_PHOENIX_BASE ?? "http://localhost:6006",
  },
  async rewrites() {
    const upstream = (
      process.env.BACKEND_UPSTREAM ?? process.env.CLEARPORT_BACKEND_UPSTREAM ?? ""
    ).replace(/\/$/, "");
    if (!upstream) return [];

    // Same-origin proxy: browser → Vercel (HTTPS) → GCP backend (HTTP/HTTPS).
    // A single catch-all forwards every current and future REST route, so new
    // endpoints (e.g. /api/shipments, /api/runs/:id, /api/memory/*) work without
    // maintaining a hand-written allow-list.
    //
    // /api/events is deliberately NOT listed: it is served by
    // app/api/events/route.ts for reliable SSE streaming. As an `afterFiles`
    // rewrite (the default when returning an array), the filesystem route
    // takes precedence, so the catch-all never shadows the SSE handler.
    return [
      { source: "/health", destination: `${upstream}/health` },
      { source: "/api/:path*", destination: `${upstream}/api/:path*` },
    ];
  },
};

export default nextConfig;
