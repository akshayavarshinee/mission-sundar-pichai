# ClearPort — Demo Script & Storyboard (~3 minutes)

> Lead with the **eval-gate veto** money shot and the **self-heal** payoff; close
> on the **drift alert**. Everything below runs **offline** (no keys), so takes
> are reproducible. The core beats are *scripted-but-real*; the wildcard proves
> generality.

## Setup (one terminal each)

```bash
# A) backend (offline, no keys needed)
uv sync --extra dev
uv run clearport-api                 # http://localhost:8080

# B) dashboard
cd dashboard && npm install && npm run dev    # http://localhost:3000

# C) (optional) Phoenix for live traces
docker compose up -d phoenix         # http://localhost:6006
```

Or run the **fully narrated console demo** end-to-end:

```bash
uv run clearport-demo
```

---

## The story (6 beats + wildcard)

| # | On screen | What you say | What to verify |
|---|-----------|--------------|----------------|
| 0 | Dashboard at rest: 4 metric counters, empty timeline | "MSME exporters get cryptic customs rejections; a container at the dock costs **\$200–\$1,000/day**. ClearPort recovers them autonomously — with an **Arize eval-gate** as its conscience." | Four counters render; "live" dot is green. |
| 1 | Click **S4** | "A scarf shipment is rejected: missing `customs_signer`. ClearPort diagnoses, patches, the eval-gate **passes**, and it auto-buys the label." | Card shows `AUTO_RESOLVED`, eval **PASS**, diff `customs_signer: ∅→…`. |
| 2 | Click the **hard HS variant** (money shot) | "Now a tricky tariff case. The agent proposes a fix — but the **eval-gate VETOES it** against historically-accepted shipments. No money is spent; it escalates to a human." | Card ringed red, eval **VETO**, decision `ESCALATE`. **This is the hero frame.** |
| 3 | Approve the **human correction** (HS `830249`), then **Run learning** | "A human corrects it. ClearPort logs the outcome and runs a **Phoenix experiment**; because the correction **beats baseline**, the lesson is **promoted** to permanent memory." | Timeline shows `Lesson promoted`. |
| 4 | Re-fire the **same hard variant** | "Same error returns — now it **self-heals autonomously from memory**, no human, visibly faster." | Card `AUTO_RESOLVED`; `self-heal speed-up` counter rises above 1×. |
| 5 | Click **S2** | "A \$3,200 shipment needs EEI filing. ClearPort fixes it — but value crosses the **\$2,500 hard line**, so it **escalates** regardless of confidence. Oversight by design." | Card `AWAITING_APPROVAL`; reason cites the hard line. Approve it. |
| 6 | Click **Trigger drift** | "A destination **silently changes a rule**. A promoted lesson's pass-rate drops — ClearPort raises a **drift alert**, re-investigates, and **auto-heals** the new schema." | Red drift banner → turns green "auto-healed". |
| ⚡ | Click **W1** (wildcard) | "Unrehearsed: a different failure — missing contents explanation. Same loop, clean recovery." | Card `AUTO_RESOLVED`. |
| ✦ | Open **Phoenix traces ↗** | "Every step is a real trace: recall → diagnose → patch → **eval** → decide → act → learn, annotated with the decision and memory provenance." | Spans visible with `clearport.*` attributes. |

Close on the four metrics: **recovery time vs days**, **\$ demurrage saved**,
**% auto-resolved (with safe escalations)**, **self-heal speed-up**.

---

## Why each beat is honest

- **Real rejections.** S1–S4 + W1 each trip a real EasyPost (test-mode) customs
  rule; offline, the same rules run via `policy_lint` (the synthetic carrier).
- **Real eval-gate.** The judge AND-combines a deterministic policy backstop with
  the Gemini judge; the veto is a genuine rubric failure, not a hard-coded branch.
- **Real learning.** Promotion only happens when a Phoenix experiment shows the
  human correction beats the agent's baseline (`run_experiment` → `run_promotion`).
- **Real drift.** The Regional Rule Overlay is a versioned rule engine we own — we
  never fake an EasyPost error; we flip *our* registry and detect the pass-rate drop.

## One-take fallback

If the network is flaky during recording, run `uv run clearport-demo` and screen-
record the narrated console output — it executes the identical service code path.
