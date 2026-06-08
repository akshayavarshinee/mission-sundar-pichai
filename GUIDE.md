<!-- markdownlint-disable MD033 MD041 -->
# ClearPort — Run Guide (offline, no keys, no cloud)

> **TL;DR** — On a fresh machine:
> ```powershell
> .\tools\setup.ps1     # one-time install (offline; no API keys needed)
> .\tools\start.ps1     # backend :8080 + dashboard :3000, opens the browser
> ```
> Then click **“▶ Play full demo”** in the dashboard. That’s the whole thing.

ClearPort runs **100% offline by default**. Every external dependency — Gemini,
Arize Phoenix, EasyPost, Vertex embeddings, Postgres — has a deterministic
fallback, so the entire diagnose → patch → **eval-gate** → decide → act → learn
loop executes with **no API keys, no Docker, and no internet**. You can later
flip on live services by setting environment variables — never by changing code.

---

## 1. Prerequisites

| Need | Required? | Notes |
|---|---|---|
| **Python 3.12+** | ✅ required | `python --version`. You have 3.13 — fine. |
| **Node.js 18+** (`npm`) | ⬜ optional | Only for the **web dashboard**. Skip it and use the console demo. |
| **uv** | ⬜ optional | Faster installs. If absent, setup falls back to `venv` + `pip`. |
| **Docker** | ❌ not needed | Only for the *optional* live Phoenix/Postgres stack. |
| **Any API key** | ❌ not needed | Offline mode needs zero secrets. |

---

## 2. Setup (one time)

### Windows (PowerShell)
```powershell
cd <repo>\clearport
.\tools\setup.ps1
```

### macOS / Linux
```bash
cd <repo>/clearport
chmod +x tools/*.sh
./tools/setup.sh
```

The setup script:
1. verifies Python 3.12+,
2. creates `.env` from `.env.example` (offline defaults — **no keys**),
3. installs backend deps (`uv sync --extra dev`, or a `.venv` + `pip` fallback),
4. installs the dashboard (`npm install`) and creates `dashboard/.env.local`
   (skipped automatically if Node isn’t installed).

> If a corporate proxy blocks installs, do the same steps manually — see
> **§8 Manual setup**.

---

## 3. Run it — three ways

### Way A — Console demo (fastest; no Node required)
A single narrated run of the whole storyboard:
```powershell
uv run clearport-demo
# (venv fallback) .\.venv\Scripts\python -m clearport.scripts.demo
```
Prints all six beats + the wildcard and the four headline metrics. **This is the
most reliable thing to screen-record** — it executes the exact same service code
the dashboard uses.

### Way B — Full web experience (backend + dashboard)
```powershell
.\tools\start.ps1            # Windows  →  opens http://localhost:3000
./tools/start.sh            # macOS/Linux
```
Two windows open (backend + dashboard). In the dashboard, click **“▶ Play full
demo”**.

### Way C — Backend only (use the API directly)
```powershell
uv run clearport-api        # http://localhost:8080  (Swagger UI at /docs)
```
Then drive it with the REST endpoints in **§6**.

---

## 4. Using the dashboard

| Control | What it does |
|---|---|
| **▶ Play full demo** | Runs the entire storyboard hands-free (incl. the eval **VETO**, the **self-heal**, and the **drift** beats). Best for recording. |
| **Reset** | Clears all runs, approvals, and learned memory for a clean take. |
| **Seed buttons (S1–S4, C0, W1)** | Fire one shipment through the loop. `W1 ⚡` is the unrehearsed wildcard. |
| **Run learning** | Runs experiment-gated promotion (episodic ② → distilled ③). |
| **Trigger drift** | Simulates a silent destination rule change, raises a drift alert, then auto-heals. |
| **Approve / Reject** (queue) | Human-in-the-loop decision on an escalation; Approve buys the (test-mode) label. |
| **Phoenix traces ↗** | Deep-links to the Phoenix UI (only meaningful when Phoenix is running). |

The header shows a **backend health pill** (green = reachable) and the timeline
shows a **live/reconnecting** dot.

> **Why “Play full demo” exists:** clicking the **S1** button alone *auto-resolves*
> (the built-in classifier fixes the HS code), so you’d never see the **eval-gate
> veto**. The money shot needs a case the classifier *can’t* resolve. “Play full
> demo” stages that honestly on the server (exactly as the test-suite does), so
> the VETO → human-correct → **promote** → **self-heal** arc actually appears.

---

## 5. The demo storyboard (6 beats + wildcard)

1. **S4** missing `customs_signer` → fast **AUTO** heal.
2. Hard HS variant → **Arize eval-gate VETO** → escalate. *(hero frame)*
3. Human corrects HS `830249` → **Phoenix experiment beats baseline → PROMOTE ③**.
4. Same variant returns → **self-heals from memory** (not the classifier).
5. **S2** value > **$2,500** → **hard-line ESCALATE** → human approves.
6. Silent rule change → **DRIFT ALERT** → auto-heal.
7. ⚡ **W1** wildcard (`contents_explanation`) → **AUTO** heal.

Full narration + camera notes: [docs/DEMO.md](docs/DEMO.md).

---

## 6. REST API (offline)

Base URL `http://localhost:8080` · interactive docs at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + runtime env |
| GET | `/api/seeds` | list demo shipments |
| POST | `/api/recover/{seed_id}` | run the loop on one seed |
| GET | `/api/runs` · `/api/runs/{id}` | recovery results |
| GET | `/api/approvals` | the human queue |
| POST | `/api/approvals/{id}/approve` · `/reject` · `/correct` | HITL decisions |
| GET | `/api/metrics` | the four headline metrics |
| POST | `/api/learn` | experiment-gated promotion ② → ③ |
| POST | `/api/drift/{seed_id}` | trigger + auto-heal drift |
| POST | `/api/reset` | clear the board (keeps SSE alive) |
| POST | `/api/demo/play` | run the full scripted storyboard |
| GET | `/api/events` | **SSE** live event stream |

```powershell
# quick smoke test
curl http://localhost:8080/health
curl -X POST http://localhost:8080/api/demo/play
curl http://localhost:8080/api/metrics
```

---

## 7. What’s real vs simulated (offline mode)

Being honest about this is part of the pitch:

| Capability | Offline (default) | Live (optional) |
|---|---|---|
| Carrier customs validation | **Simulated** via `policy_lint` — the *same* EasyPost rules | **Real** EasyPost **test mode** |
| Eval-gate judge | **Real logic**: deterministic policy backstop | backstop **AND** Gemini judge |
| Experiment-gated learning | **Real logic**, deterministic | same, with Phoenix datasets/experiments |
| Drift detection | **Real** monitor over a **simulated** registry we own (never fakes EasyPost) | same |
| Embeddings | **Local** feature-hashing (3072-d) | Vertex `gemini-embedding-001` |
| LLM reasoning | deterministic rule-based fallback | Gemini 3 |
| Tracing | best-effort no-op | OpenInference → Phoenix |

---

## 8. Manual setup (if the scripts can’t run)

```powershell
# backend
copy .env.example .env
uv sync --extra dev                 # OR:  python -m venv .venv ; .\.venv\Scripts\python -m pip install -e ".[dev]"

# dashboard (optional)
cd dashboard
copy .env.local.example .env.local
npm install
```

Run:
```powershell
uv run clearport-api                # backend  :8080
cd dashboard ; npm run dev          # dashboard :3000
```

---

## 9. Going live later (optional)

Set these in `.env` (backend) — code never changes. See [clearport/config.py](clearport/config.py).

| Capability | Env vars |
|---|---|
| Gemini 3 brain | `GOOGLE_API_KEY` *(or Vertex: `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`)* |
| Phoenix tracing | `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_API_KEY` |
| Phoenix MCP memory ② / prompts ④ | `CLEARPORT_EPISODIC_BACKEND=phoenix`, `CLEARPORT_PROMPTS_BACKEND=phoenix` |
| Vertex embeddings | `CLEARPORT_EMBEDDINGS_BACKEND=vertex` |
| Postgres + pgvector | `CLEARPORT_VECTOR_BACKEND=pg`, `DATABASE_URL=…` |
| EasyPost (test) | `EASYPOST_API_KEY=` *(a **test** key)* |

Local live stack: `docker compose up -d` (Phoenix at `:6006`, Postgres at `:5432`),
then for the dashboard set `NEXT_PUBLIC_PHOENIX_BASE`. Cloud Run deploy scripts:
[infra/deploy/](infra/deploy/).

---

## 10. Verify (before any demo or submission)

```powershell
.\tools\verify.ps1      # compileall + full pytest, offline
# or:  uv run pytest -ra
```
Key tests that prove the story:
- `tests/unit/test_loop_offline.py` — the locked beats (S1–S4, W1, eval-veto).
- `tests/unit/test_promotion.py` — the money shot (veto → learn → self-heal).
- `tests/unit/test_drift.py` — drift detection + auto-heal.

---

## 11. Project structure

```
clearport/
├── clearport/            # backend package
│   ├── agents/           # orchestrator, auditor, patch engine, executor, classifier
│   ├── eval/             # judge (eval-gate), risk tier, experiments, baseline
│   ├── memory/           # ① law ② episodic ③ lessons ④ prompts + recall + embeddings
│   ├── validation/       # EasyPost client, policy_lint, regional overlay (drift)
│   ├── arize/            # tracing, MCP client, ADK toolset, drift monitor
│   ├── api/              # FastAPI app, SSE bus, metrics, demo runner
│   ├── seeds/            # S1–S4/C0/W1 + curated law KB
│   └── scripts/          # hello_trace, mcp_handshake, demo
├── dashboard/            # Next.js 14 dashboard (App Router + Tailwind)
├── tools/                # setup / start / verify scripts (this guide’s commands)
├── infra/                # Cloud Run deploy + Cloud SQL schema
├── docs/DEMO.md          # video storyboard
└── GUIDE.md              # you are here
```

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard shows **“backend down”** | Start the API: `uv run clearport-api`. Confirm `http://localhost:8080/health`. |
| **Port already in use** | Backend: set `PORT=8090`. Dashboard: `npm run dev -- -p 3001` and set `NEXT_PUBLIC_API_BASE`. |
| Editor flags **`Cannot find name 'process'`** in `dashboard/lib/api.ts` | Expected before install — `@types/node` is in `devDependencies`; run `npm install`. |
| Clicking **S1** doesn’t show a VETO | By design — it auto-resolves. Use **▶ Play full demo** (or break the classifier) to see the veto. |
| Timeline not updating | SSE auto-reconnects (watch the live dot). Check the browser console and that CORS reaches `:8080`. |
| `uv` not found | The scripts fall back to `.venv` + `pip` automatically. |
| Tests need network/keys | They don’t — everything is offline. If something asks for a key, you’re in live mode; unset the related `CLEARPORT_*` / key env vars. |

---

## 13. DO / DON’T (project-lead checklist)

**DO**
- ✅ Run `tools/setup.ps1` once, then `tools/start.ps1`; use **▶ Play full demo** to record.
- ✅ Hit **Reset** between takes for clean metrics.
- ✅ Run `tools/verify.ps1` before every demo and before submitting.
- ✅ Keep EasyPost in **test mode** only; keep personas synthetic.
- ✅ Put any secrets in `.env` / Secret Manager; commit only `.env.example`.
- ✅ Lead the video with the **eval-gate veto**, pay it off with **self-heal**, close on **drift**.
- ✅ Show the metric **assumptions** on screen (they’re printed inline) to stay defensible.

**DON’T**
- ❌ Don’t commit real keys or your `.env` (both are git-ignored — keep it that way).
- ❌ Don’t switch EasyPost to production or buy real labels.
- ❌ Don’t expect the lone **S1** button to show the veto (it auto-resolves).
- ❌ Don’t file to real customs authorities — the Regional Overlay is a *simulated* registry.
- ❌ Don’t install Docker on a locked-down laptop; offline mode needs none of it.
- ❌ Don’t remove or bypass the **eval-gate** or the **learning loop** — they’re the two load-bearing pieces (“if anything is cut, cut breadth, never these”).
- ❌ Don’t hardcode config in code; change behaviour via env vars only.

---

## 14. Where Arize Phoenix is load-bearing

Remove Phoenix and the value proposition collapses. It is used in **three** places:
**eval-gate** (judge must pass before any action), **risk tier** (eval *confidence*
feeds auto-vs-human, with a **$2,500 hard line**), and **learning + drift** (outcomes
become datasets; a fix is promoted only when a **Phoenix experiment beats baseline**;
a pass-rate drop raises a **drift alert**). Integration is via the official
`@arizeai/phoenix-mcp` server plus OpenInference OTel tracing.

For the architecture, novelty statement, and comparison table, see [README.md](README.md).
For the submission checklist, see the end of the README.
