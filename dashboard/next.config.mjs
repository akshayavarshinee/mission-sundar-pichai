/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The dashboard talks to the FastAPI backend over REST + SSE. The base URL is
  // injected at build/run time via NEXT_PUBLIC_API_BASE (defaults to localhost).
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080",
    NEXT_PUBLIC_PHOENIX_BASE: process.env.NEXT_PUBLIC_PHOENIX_BASE ?? "http://localhost:6006",
  },
};

export default nextConfig;
