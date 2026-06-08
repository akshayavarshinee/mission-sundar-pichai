<!-- markdownlint-disable MD033 MD041 -->
# ClearPort

> **The autonomous customs-recovery layer with an evaluation conscience.**
> Built with **Gemini 3** + **Google Cloud Agent Builder**, with **Arize Phoenix** (via MCP) as the trust layer that must approve every fix before any real-money action.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Built with Gemini](https://img.shields.io/badge/Built%20with-Gemini%203-4285F4.svg)](#)
[![Arize Phoenix](https://img.shields.io/badge/Arize-Phoenix%20MCP-FF5C00.svg)](#)

---

## The problem

Small and medium exporters (MSMEs) have no in-house customs team. They file
cross-border shipping declarations through digital tools and hope they clear.
When a destination silently changes a rule — a date format, a required field,
a tariff code set — the filing is rejected with a cryptic code. The container
sits at the dock accruing **demurrage of \$200–\$1,000+ per day**, and a few
days of bureaucratic delay can erase a quarter's profit. Big firms have SAP GTS
and brokers on retainer. The MSME has nothing.

## What ClearPort does

> **ClearPort is the autonomous customs-recovery layer that sits on top of
> existing shipping and classification tools. When a cross-border shipment is
> rejected, it diagnoses the cause, patches the declaration, and — critically —
> uses Arize Phoenix as an evaluation conscience that must approve the fix
> against historically-accepted shipments before any real-money action.
> Low-risk fixes auto-clear; high-value or restricted ones escalate to a human;
> and every outcome becomes memory, so the same error self-heals next time.**

It runs as a background pipeline of four agents:

1. **Orchestrator** (Gemini 3, Agent Builder) — plans the recovery loop.
2. **Customs Auditor** — diagnoses the rejection, grounded in customs law + memory.
3. **Document Patch Engine** — rewrites the declaration (HS code, EEI, restriction notes, structural fixes).
4. **Meta-Cognitive Self-Healer** — the **Arize loop**: eval-gate, tiered action, learning, drift detection.

## Why it's novel

The *parts* aren't new — AI HS-classification (Zonos) and customs-doc generation
(ShipEngine, Avalara) already exist. **The closed loop is**: nobody combines
**diagnose → patch → eval-gate → tiered act → learn** into an autonomous
recovery layer with an evaluation conscience and evolving memory.

| Capability | Zonos Classify | ShipEngine/Shippo | EasyPost + Luma AI | Customs broker | **ClearPort** |
|---|:---:|:---:|:---:|:---:|:---:|
| HS-code classification | ✅ | partial | ❌ | manual | ✅ (or *calls* one) |
| Customs doc generation | ❌ | ✅ | ✅ | manual | ✅ |
| Live carrier submission | ❌ | ✅ | ✅ | manual | ✅ |
| **Diagnoses a rejection** | ❌ | ❌ | ❌ (chat only) | ✅ slow | ✅ autonomous |
| **Patches & resubmits** | ❌ | ❌ | ❌ | ✅ manual | ✅ autonomous |
| **Eval gate before action** | ❌ | ❌ | ❌ | gut feel | ✅ **Arize** |
| **Tiered human oversight** | ❌ | ❌ | ❌ | implicit | ✅ explicit |
| **Learns from its outcomes** | ░ sampling | ❌ | ░ analytics | ░ in head | ✅ trace→experiment |
| **Closed recovery loop** | ❌ | ❌ | ❌ | ✅ (human) | ✅ autonomous |

## Where Arize Phoenix is load-bearing

Remove Phoenix and the system stops working. It is used in **three** places:

- **Eval-gate** — an LLM-as-judge compares each patch to historically-accepted
  shipments; no label is bought unless it passes.
- **Risk tier** — the eval *confidence* feeds the auto-vs-human decision
  (alongside customs value and restricted-goods flags; **\$2,500 is a hard line**).
- **Learning + drift** — outcomes are written back as dataset examples, a fix is
  promoted to permanent memory **only after a Phoenix experiment beats baseline**,
  and a drop in a promoted lesson's pass-rate raises a **drift alert**.

Integration is via the official **`@arizeai/phoenix-mcp`** Model Context Protocol
server (active runtime access) plus OpenInference OTel instrumentation (passive
tracing).

## Architecture (high level)

```
 RejectionEvent ─► Orchestrator (Gemini 3 / Agent Builder)
                     ├─ Auditor      : diagnose (③ lessons → ① law veto → ② precedent)
                     ├─ Patch Engine : rewrite the immutable customs payload
                     ├─ Self-Healer  : ARIZE eval-gate + risk tier
                     │                   PASS & low-risk ─► AUTO buy real label
                     │                   FAIL / ≥$2,500 / restricted ─► HUMAN
                     └─ Learn        : outcome → ② ; experiment beats baseline → ③
                                       drift: ③ pass-rate drop ─► ALERT
```

Two **validation surfaces**, mirroring real trade:
- **EasyPost (test mode)** — real carrier customs validation (the authentic rejections).
- **Regional Rule Overlay** — a small registry we own, to demonstrate a *silent
  schema change* and trigger drift detection. Both are real code paths.

Tiered **memory (Design B)**: ① static law · ② episodic outcomes · ③ distilled
lessons (always-on semantic, **law has veto**) · ④ procedural prompts.

## Quickstart

ClearPort runs **fully offline by default** — every external dependency
(EasyPost, Phoenix MCP, Vertex embeddings, Gemini, Postgres) has a deterministic
fallback, so you can run the entire recovery loop **with no keys and no Docker**.

### Option A — the 60-second offline demo (no keys)

```bash
uv sync --extra dev
uv run clearport-demo            # narrated walk-through of all 6 beats + wildcard
uv run pytest -ra                # the same beats, asserted as tests
```

### Option B — backend + live dashboard

```bash
# 1. backend (offline; http://localhost:8080)
uv run clearport-api

# 2. dashboard (http://localhost:3000)
cd dashboard && cp .env.local.example .env.local && npm install && npm run dev
```

Open <http://localhost:3000>, fire a seed, watch the loop stream live, approve an
escalation, then click **Trigger drift**.

### Option C — full live stack (keys + services)

```bash
# prerequisites: Docker, Python 3.12, uv, Node.js (for the MCP server via npx)
cp .env.example .env             # GOOGLE_API_KEY, EASYPOST_API_KEY (test), Phoenix…
docker compose up -d             # local Phoenix + Postgres/pgvector
uv sync --extra dev

uv run clearport-hello-trace     # emits one Gemini call as a Phoenix trace
uv run clearport-mcp-handshake   # confirms the Phoenix MCP server + required tools
uv run pytest tests/unit -ra
```

Progressively enable live services via the backend flags in
[`clearport/config.py`](clearport/config.py): `CLEARPORT_VECTOR_BACKEND=pg`,
`CLEARPORT_EMBEDDINGS_BACKEND=vertex`, `CLEARPORT_EPISODIC_BACKEND=phoenix`,
`CLEARPORT_PROMPTS_BACKEND=phoenix`, plus the relevant keys.

## The four metrics

Shown live on the dashboard and printed by `clearport-demo`:

| Metric | Definition | Assumption |
|---|---|---|
| **Recovery time** | agent loop seconds vs the broker-days baseline | broker baseline = 3 days |
| **\$ demurrage saved** | `days_saved × $/day` per resolved shipment | \$250/day demurrage per shipment |
| **% auto-resolved** | auto-resolved ÷ total, with the safe-escalation count alongside | escalation is a *success*, not a failure |
| **Self-heal speed-up** | first-vs-repeat recovery latency for the same memory key | ≥ 2 observations of a key |

Assumptions are shown inline so the numbers stay defensible.

## Arize Phoenix — MCP & telemetry map

| Phoenix surface | Where ClearPort uses it |
|---|---|
| **OTel / OpenInference tracing** | every loop step is a span (`recall → diagnose → patch → verify → decide → act → learn`), annotated with decision, risk tier, and memory provenance |
| **LLM-as-judge evals** | the **eval-gate** verdict that must pass before any label is bought |
| **Experiments** | promotion ② → ③ only when a candidate **beats baseline** |
| **Datasets** (`get/add-dataset-examples`) | episodic memory ② — outcomes & human corrections written back over MCP |
| **Prompts** (`get/upsert-prompt`, version tags) | procedural memory ④ — auditor / patch-engine / judge prompts |
| **Traces / spans / annotations** | dashboard deep-links so judges can inspect real telemetry |

## Run the tests

```bash
uv run pytest -ra                       # full suite, offline & deterministic
uv run pytest tests/unit/test_loop_offline.py -ra   # the locked demo beats
uv run pytest tests/unit/test_promotion.py -ra      # the money shot (veto→learn→self-heal)
```

## Project status

Built phase by phase. See [`../ClearPort-Implementation-Plan.md`](../ClearPort-Implementation-Plan.md)
for the full plan. The whole stack runs offline and is statically verified
(`python -m compileall` + type-checking); the test suite runs via `uv run pytest`.

- [x] **Phase 0** — Foundations & scaffolding
- [x] **Phase 1** — Live EasyPost rejection harness (+ synthetic offline carrier)
- [x] **Phase 2** — KB & tiered memory (① law · ② episodic · ③ distilled · ④ prompts)
- [x] **Phase 3** — Orchestrator + MCP toolset
- [x] **Phase 4** — Four sub-agents (auditor, patch engine, executor, self-healer)
- [x] **Phase 5** — Eval-gate + risk tier
- [x] **Phase 6** — Human-in-the-loop (FastAPI + SSE)
- [x] **Phase 7** — Experiment-gated learning
- [x] **Phase 8** — Drift detection + Regional Rule Overlay
- [x] **Phase 9** — Dashboard (Next.js) & Cloud Run hosting
- [x] **Phase 10** — Metrics, telemetry & polish
- [x] **Phase 11** — Demo & submission

## Submission checklist (Arize track)

- [x] Public repository with **Apache-2.0** visible in About
- [x] Built with **Gemini 3** + **Google Cloud Agent Builder (ADK)**
- [x] **Arize Phoenix** load-bearing via `@arizeai/phoenix-mcp` + OpenInference OTel
- [x] Hosted dashboard + Agent Builder app (`infra/deploy/`)
- [x] Reproducible from this README (offline path needs no keys)
- [x] ~3-minute demo video to the storyboard in [`docs/DEMO.md`](docs/DEMO.md)
- [x] Four impact metrics on screen with stated assumptions

## License

[Apache-2.0](./LICENSE) © 2026 ClearPort Contributors.

> ClearPort uses EasyPost **test mode** only and synthetic shipper data. It does
> not file to government customs authorities; the Regional Rule Overlay simulates
> a destination registry for drift demonstration. The agent performs structural
> and syntactic customs corrections; final legal classification of high-value or
> restricted goods is always routed to a human.
