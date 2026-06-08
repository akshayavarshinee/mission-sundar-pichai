"""Tiered memory (Design B).

    ① law_store   — static customs law (HTS / CROSS / EEI), pgvector, has VETO
    ② episodic    — outcomes, a Phoenix dataset reached over MCP
    ③ lessons     — distilled, promoted-only lessons, pgvector, semantic-first
    ④ prompts     — procedural prompts, managed in Phoenix

``recall`` composes them: semantic ③ → law ① veto → ② precedent.
"""
