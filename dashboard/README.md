# ClearPort Dashboard

A cinematic, judge-usable web UI for the ClearPort customs-recovery agent. It
streams the live recovery loop over SSE and exposes one-click demo controls.

## What you can do here

- **Fire seeds S1–S4 + the W1 wildcard** and watch each recovery resolve live.
- **Watch the live trace timeline** — every loop step, eval verdict, law-veto,
  promotion, and drift alert as it happens.
- **Inspect eval verdicts** — the Arize eval-gate rubric, risk tier, and the
  exact field-level patch applied (the money shot is a confident-but-wrong patch
  getting **vetoed**).
- **Approve / reject escalations** in the human-in-the-loop queue.
- **Run learning** — experiment-gated promotion (episodic ② → distilled ③).
- **Trigger drift** — simulate a silent destination rule change and watch the
  loop detect it and auto-heal.
- **Deep-link to Phoenix** to inspect the real underlying telemetry.

## Run it

The dashboard talks to the ClearPort FastAPI backend.

```bash
# 1) start the backend (from the repo root)
uv run clearport-api          # http://localhost:8080

# 2) start the dashboard
cd dashboard
cp .env.local.example .env.local   # adjust if your backend isn't on :8080
npm install
npm run dev                   # http://localhost:3000
```

## Configuration

| Variable                       | Default                  | Purpose                          |
| ------------------------------ | ------------------------ | -------------------------------- |
| `NEXT_PUBLIC_API_BASE`         | `http://localhost:8080`  | ClearPort REST + SSE backend     |
| `NEXT_PUBLIC_PHOENIX_BASE`     | `http://localhost:6006`  | Phoenix UI for trace deep-links  |
| `NEXT_PUBLIC_AGENT_BUILDER_URL`| Cloud console            | Link to the hosted Agent Builder app |

## Stack

Next.js 14 (App Router) · React 18 · TypeScript · Tailwind CSS. No client state
library — a single SSE hook (`lib/useEvents.ts`) with auto-reconnect drives the
live updates; REST calls in `lib/api.ts` mirror the backend contract.

## Deploy (Cloud Run)

```bash
# build + deploy both surfaces (see ../infra/deploy)
../infra/deploy/deploy_dashboard.sh
```
