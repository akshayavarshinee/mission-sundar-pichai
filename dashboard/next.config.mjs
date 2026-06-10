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
    // /api/events is handled by app/api/events/route.ts for reliable SSE streaming.
    return [
      { source: "/health", destination: `${upstream}/health` },
      { source: "/api/seeds", destination: `${upstream}/api/seeds` },
      { source: "/api/runs", destination: `${upstream}/api/runs` },
      { source: "/api/approvals", destination: `${upstream}/api/approvals` },
      { source: "/api/metrics", destination: `${upstream}/api/metrics` },
      { source: "/api/learn", destination: `${upstream}/api/learn` },
      { source: "/api/reset", destination: `${upstream}/api/reset` },
      { source: "/api/demo/play", destination: `${upstream}/api/demo/play` },
      { source: "/api/recover/:seedId", destination: `${upstream}/api/recover/:seedId` },
      { source: "/api/approvals/:runId/approve", destination: `${upstream}/api/approvals/:runId/approve` },
      { source: "/api/approvals/:runId/reject", destination: `${upstream}/api/approvals/:runId/reject` },
      { source: "/api/drift/:seedId", destination: `${upstream}/api/drift/:seedId` },
    ];
  },
};

export default nextConfig;
