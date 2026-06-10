import { backendUpstream } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Stream SSE from the FastAPI backend through Vercel (same-origin for the browser). */
export async function GET() {
  const upstream = backendUpstream();
  if (!upstream) {
    return new Response("BACKEND_UPSTREAM is not configured", { status: 503 });
  }

  const res = await fetch(`${upstream}/api/events`, {
    headers: { Accept: "text/event-stream" },
    cache: "no-store",
  });

  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => res.statusText);
    return new Response(detail, { status: res.status });
  }

  return new Response(res.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
