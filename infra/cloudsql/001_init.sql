-- ──────────────────────────────────────────────────────────────────────────
-- ClearPort — Postgres + pgvector initialization.
-- Runs automatically on first `docker compose up` (mounted into the db image).
-- Holds memory tier ① (static law) and ③ (distilled lessons) embeddings, plus
-- application state for rejections, outcomes, and the HITL approval queue.
--
-- NOTE: tier ② (episodic outcomes) lives in an Arize Phoenix DATASET, accessed
-- via the Phoenix MCP server — not in this database. tier ④ (procedural
-- prompts) lives in Phoenix prompt management. This file covers ① ③ + state.
-- ──────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS vector;

-- gemini-embedding-001 dimensionality (3072). Adjust if the embed model changes.
-- ── ① STATIC LAW : HTS / CROSS / EEI curated slices ───────────────────────
CREATE TABLE IF NOT EXISTS law_chunks (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT NOT NULL,          -- 'HTS' | 'CROSS' | 'EEI'
    citation      TEXT NOT NULL,          -- e.g. 'HTS 9404.90' or 'CROSS N123456'
    hs_chapter    TEXT,                   -- two-digit chapter when applicable
    content       TEXT NOT NULL,
    embedding     vector(3072),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS law_chunks_embedding_idx
    ON law_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS law_chunks_chapter_idx ON law_chunks (hs_chapter);

-- ── ③ DISTILLED LESSONS : always-on semantic memory (law has veto) ────────
CREATE TABLE IF NOT EXISTS distilled_lessons (
    id              BIGSERIAL PRIMARY KEY,
    lane            TEXT NOT NULL,        -- 'IN->US' etc.
    hs_chapter      TEXT,
    error_type      TEXT NOT NULL,        -- normalized_error_type
    pattern         TEXT NOT NULL,
    recommended_fix TEXT NOT NULL,
    evidence_count  INT NOT NULL DEFAULT 0,
    experiment_id   TEXT,                 -- Phoenix experiment that promoted it
    baseline_score  DOUBLE PRECISION,
    candidate_score DOUBLE PRECISION,
    pass_rate       DOUBLE PRECISION,     -- rolling; feeds drift detection
    embedding       vector(3072),
    promoted_at     TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS distilled_lessons_key_idx
    ON distilled_lessons (lane, COALESCE(hs_chapter, ''), error_type);
CREATE INDEX IF NOT EXISTS distilled_lessons_embedding_idx
    ON distilled_lessons USING hnsw (embedding vector_cosine_ops);

-- ── APPLICATION STATE : rejections, proposals, outcomes, approvals ────────
CREATE TABLE IF NOT EXISTS rejection_events (
    id            TEXT PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    source        TEXT NOT NULL,          -- 'easypost' | 'overlay'
    lane          TEXT NOT NULL,
    persona       TEXT,
    contents_type TEXT,
    restriction_type TEXT,
    customs_value DOUBLE PRECISION,
    currency      TEXT,
    error_type    TEXT NOT NULL,
    raw_error     JSONB NOT NULL,
    payload       JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS recovery_runs (
    id            TEXT PRIMARY KEY,
    rejection_id  TEXT NOT NULL REFERENCES rejection_events(id),
    trace_id      TEXT,                   -- Phoenix trace correlation
    status        TEXT NOT NULL,          -- planning|patched|evaluated|awaiting_human|acted|done|failed
    diagnosis     JSONB,
    patch         JSONB,
    eval_verdict  JSONB,
    risk          JSONB,
    outcome       JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS recovery_runs_status_idx ON recovery_runs (status);

CREATE TABLE IF NOT EXISTS approval_queue (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES recovery_runs(id),
    reasons       JSONB NOT NULL,         -- why it escalated
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected|corrected
    human_correction JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS approval_queue_status_idx ON approval_queue (status);
