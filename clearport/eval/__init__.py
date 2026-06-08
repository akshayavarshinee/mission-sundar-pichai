"""The Self-Healer's decision surface: eval-gate, risk tier, baseline, experiments.

    judge.py        — LLM-as-judge (Gemini) with a deterministic law backstop
    risk_tier.py    — risk score + the $2,500 hard line -> AUTO | HUMAN
    baseline.py     — the historically-accepted shipments the judge compares to
    experiments.py  — experiment-gated promotion (Phase 7)
"""
