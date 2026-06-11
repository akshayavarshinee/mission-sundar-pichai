# ClearPort — Demo Script & Storyboard (live VM + Arize Phoenix, ~4 min)

> **The judged demo runs on the live GCE VM**, where Arize Phoenix is genuinely
> load-bearing — not a trace sink. The arc is two acts:
>
> 1. **The loop** (dashboard): the **eval-gate veto** money shot → the **self-heal**
>    payoff → the **drift** auto-heal.
> 2. **The Arize proof** (Phoenix tab): open Phoenix and show the *real artifacts the
>    loop just produced* — a verify span carrying an `eval_gate` **annotation**, a
>    promoted lesson's **experiment** comparison, the **`clearport-outcomes` dataset**
>    growing, and the synthetic **benchmark experiment** with a **false-auto-clear** rate.
>
> An offline, no-keys console fallback is preserved at the end for flaky networks.

---

## 0. URLs & pre-flight

The deploy job writes a `.env` with `SITE_HOST` (a free `sslip.io` name that
resolves to the VM's static IP). Two tabs:

| Tab | URL | What it is |
|-----|-----|------------|
| **App** | `https://<SITE_HOST>` | Dashboard + API behind one HTTPS origin (Caddy: `/api/*` → backend, else → dashboard). |
| **Phoenix** | `http://<VM_IP>:6006` | Self-hosted Arize Phoenix — traces, evals, datasets, experiments. No API key. |

Pre-flight (SSH to the VM, or from the deploy box):

```bash
# All containers healthy: caddy, dashboard, backend, phoenix, db
docker compose -f docker-compose.prod.yml ps
curl -fsS https://<SITE_HOST>/health        # {"status":"ok", ...}

# Prove the MCP tool surface Phoenix exposes (the handshake the agent relies on).
docker exec clearport-api clearport-mcp-handshake   # lists get-span-annotations, datasets, experiments…
```

> Keep the **Phoenix tab open at `/projects`** so Act 2 is one click away. To make
> the dashboard's "Phoenix ↗" deep-links resolve from your laptop, the dashboard
> image is built with `NEXT_PUBLIC_PHOENIX_BASE=http://<VM_IP>:6006`; otherwise
> just drive Phoenix directly in its own tab.

---

## Act 1 — The loop (dashboard)

| # | On screen | What you say | What to verify |
|---|-----------|--------------|----------------|
| 0 | Dashboard at rest: 4 metric counters, empty timeline | "MSME exporters get cryptic customs rejections; a container stuck at the dock costs **\$200–\$1,000/day**. ClearPort recovers them autonomously — with an **Arize Phoenix eval-gate** as its conscience." | Counters render; the "live" dot is green. |
| 1 | Click **S4** (missing signer) | "A scarf shipment is rejected — no `customs_signer`. ClearPort recalls law, diagnoses, patches, the **eval-gate passes**, and it auto-buys the label." | Card `AUTO_RESOLVED`, eval **PASS**, diff `customs_signer: ∅→…`. |
| 2 | Click the **hard HS variant** — money shot | "A tricky tariff case. The agent proposes a fix, but the eval-gate **VETOES** it against historically-accepted shipments. **No money is spent**; it escalates to a human." | Card ringed red, eval **VETO**, decision `ESCALATE`. **Hero frame.** |
| 3 | **Approve the human correction** (HS `830249`), then **Run learning** | "A human corrects it. ClearPort logs the outcome and registers a **real Phoenix experiment** comparing the correction against the accepted baseline; because it **beats baseline**, the lesson is **promoted** to permanent memory." | Timeline: `Lesson promoted`. The lesson row gets a **"View experiment in Phoenix ↗"** link. |
| 4 | Re-fire the **same hard variant** | "Same error returns — now it **self-heals from memory**, no human, visibly faster." | Card `AUTO_RESOLVED`; `self-heal speed-up` rises above 1×. |
| 5 | Click **S2** (\$3,200 EEI) | "A \$3,200 shipment needs EEI filing. ClearPort fixes it — but the value crosses the **\$2,500 hard line**, so it escalates regardless of confidence. The new **cost-of-being-wrong** term reinforces that. Oversight by design." | `AWAITING_APPROVAL`; reasons cite the hard line + expected error cost. Approve it. |
| 6 | Click **Trigger drift** | "A destination silently changes a rule. A promoted lesson's pass-rate drops — ClearPort raises a **drift alert**, re-investigates, and **auto-heals** the new schema." | Drift banner red → green "auto-healed". |
| ⚡ | Click **W1** (wildcard) | "Unrehearsed: a different failure — missing contents explanation. Same loop, clean recovery." | Card `AUTO_RESOLVED`. |

Optional, on any resolved case: click **Investigate in Phoenix (MCP)**. "This
re-grounds the verdict by reading the run's verify-span **annotations back out of
Phoenix over the Model Context Protocol** — the same MCP surface the handshake
validated." → an explanation appears with a **live Phoenix MCP read-back** badge.

---

## Act 2 — The Arize proof (Phoenix tab)

> Switch to the Phoenix tab. Everything here was produced by the runs you just did
> — nothing is pre-seeded for show.

**① Eval verdict as a span annotation.** `/projects` → **clearport** → open the
**hard-HS** run's trace → the **`verify`** span → **Annotations**. "The eval-gate
didn't just decide in code — it wrote its verdict back onto the span: an
**`eval_gate`** annotation with **label** (pass/veto), **score** (confidence), and
the judge's **explanation**. The verdict is part of the observable trace."

**② A promoted lesson's experiment.** Back in the dashboard, the promoted lesson's
**"View experiment in Phoenix ↗"** opens `/datasets/<id>/compare?experimentId=<id>`.
"This is a **real Phoenix experiment** — the human correction scored against the
accepted-baseline dataset. The lesson was promoted **because this experiment beat
baseline**, not on a hunch."

**③ The `clearport-outcomes` dataset growing.** `/datasets` → **`clearport-outcomes`**.
"Every loop outcome (memory tier ②) is mirrored into this Phoenix dataset. Re-run a
seed and the example count ticks up — Phoenix is the live system-of-record for the
agent's experience, alongside **`clearport-accepted-baseline`**."

**④ The benchmark experiment with false-auto-clear.** In the dashboard's
**Intelligence → Benchmark** panel, click **Run benchmark** (registers a real
experiment). Then in Phoenix `/experiments`, open it. "A **synthetic suite** of
labeled rejections (all 7 error classes + an adversarial prompt-injection slice)
run through the loop. The headline metric is **false-auto-clear rate** — how often
it auto-cleared a *wrong* fix. Offline that's **0.0**; the evaluators
(correctness / safety / diagnosis) are visible as Phoenix evaluator traces."

Close on the four headline metrics: **recovery time vs days**, **\$ demurrage
saved**, **% auto-resolved (with safe escalations)**, **self-heal speed-up** — and
the **calibration bars** in the Benchmark panel (confidence vs empirical correctness).

---

## Why each beat is honest

- **Real eval-gate.** The judge AND-combines a deterministic policy backstop with a
  **phoenix-evals** classifier (LiteLLM → Vertex `gemini-2.5-pro`); the model can
  only *tighten*. The veto is a genuine rubric failure, not a hard-coded branch.
- **Real annotations.** Each verdict is written back with
  `client.spans.add_span_annotation(..., annotation_name="eval_gate")` — visible on
  the span in Phoenix.
- **Real experiments.** Promotion and the benchmark both call
  `client.experiments.run_experiment(...)` against server-side datasets and return
  **real experiment ids** that deep-link into Phoenix.
- **Real datasets.** `clearport-outcomes` / `clearport-accepted-baseline` are
  written via the Phoenix client as the loop runs.
- **Real MCP.** `/api/investigate` launches `@arizeai/phoenix-mcp` and calls
  `get-span-annotations` to read the verdict back — the hot path stays on the
  in-process HTTP client (no per-call npx).
- **Real drift.** The Regional Rule Overlay is a versioned rule engine we own — we
  flip *our* registry and detect the pass-rate drop; we never fake an EasyPost error.

---

## One-take fallback (offline, no keys)

If the VM or network is flaky during recording, the identical service code path
runs locally with deterministic fallbacks — Phoenix-specific artifacts (annotations,
experiments, MCP read-back) no-op cleanly offline:

```bash
uv run clearport-demo                         # narrated console walk-through (all beats)
# or the live local UI:
uv run clearport-api                          # http://localhost:8080
cd dashboard && npm install && npm run dev    # http://localhost:3000
docker compose up -d phoenix                  # optional traces at http://localhost:6006
uv run python -m clearport.eval.benchmark     # prints the benchmark table incl. false-auto-clear
```
