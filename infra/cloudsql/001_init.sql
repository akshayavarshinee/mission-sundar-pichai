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
-- Generic vector-store layout matching clearport.memory.vector_store.
-- PgVectorStore: (id, content, embedding, metadata). All domain fields
-- (source, citation, hs_chapter, …) ride inside the JSONB metadata so the same
-- code path serves the in-memory and pgvector backends identically.
CREATE TABLE IF NOT EXISTS law_chunks (
    id            TEXT PRIMARY KEY,
    content       TEXT NOT NULL,
    embedding     vector(3072),
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- NOTE: pgvector HNSW/IVFFlat indexes support at most 2000 dimensions, but
-- gemini-embedding-001 is 3072-d, so we cannot build an ANN index on the raw
-- vector column. The curated demo KB is tiny, so an exact (sequential) scan is
-- fine. (To index later: keep a halfvec(3072) copy and build hnsw on that.)

-- ── ③ DISTILLED LESSONS : always-on semantic memory (law has veto) ────────
-- Same generic layout as law_chunks. The full DistilledLesson (lane,
-- hs_chapter, error_type, pattern, recommended_fix, pass_rate, …) is stored
-- under metadata->'lesson', with error_type/lane/hs_chapter mirrored at the top
-- level of metadata for fast equality filtering during recall.
CREATE TABLE IF NOT EXISTS distilled_lessons (
    id              TEXT PRIMARY KEY,
    content         TEXT NOT NULL,
    embedding       vector(3072),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- (See note above — no HNSW index on the 3072-d embedding column.)

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
