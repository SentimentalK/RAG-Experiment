CREATE TABLE IF NOT EXISTS experiment_sessions (
    id UUID PRIMARY KEY,
    schema_version TEXT NOT NULL DEFAULT '1',

    query_text TEXT NOT NULL,
    requested_modes JSONB NOT NULL,

    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,

    alias_dataset_sha256 TEXT NOT NULL,
    corpus_content_sha256 TEXT NULL,
    git_commit TEXT NULL,
    metadata_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,

    embedding_model TEXT NULL,
    vector_metric TEXT NULL,

    answer_model TEXT NULL,
    answer_provider TEXT NULL,

    query_expansion_config JSONB NOT NULL,
    retrieval_config JSONB NOT NULL,
    generation_config JSONB NOT NULL,

    prompt_template_sha256 TEXT NULL,

    requested_mode_count INTEGER NOT NULL DEFAULT 0,
    retrieval_execution_count INTEGER NOT NULL DEFAULT 0,
    answer_generation_count INTEGER NOT NULL DEFAULT 0,
    total_vector_search_call_count INTEGER NOT NULL DEFAULT 0,

    error_code TEXT NULL,
    error_message TEXT NULL,

    CHECK (status IN ('running', 'completed', 'partial', 'failed')),
    CHECK (requested_mode_count >= 0),
    CHECK (retrieval_execution_count >= 0),
    CHECK (answer_generation_count >= 0),
    CHECK (total_vector_search_call_count >= 0)
);

CREATE TABLE IF NOT EXISTS experiment_mode_runs (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL
        REFERENCES experiment_sessions(id)
        ON DELETE CASCADE,
    schema_version TEXT NOT NULL DEFAULT '1',
    trace_schema_version TEXT NOT NULL DEFAULT '1',

    mode TEXT NOT NULL,
    status TEXT NOT NULL,

    retrieval_executed BOOLEAN NOT NULL DEFAULT TRUE,
    retrieval_source_mode TEXT NULL,
    retrieval_source_mode_run_id UUID NULL
        REFERENCES experiment_mode_runs(id)
        ON DELETE SET NULL,

    retrieval_reason TEXT NULL,
    generated_variant_count INTEGER NOT NULL DEFAULT 0,
    vector_search_call_count INTEGER NOT NULL DEFAULT 0,
    final_context_count INTEGER NOT NULL DEFAULT 0,

    retrieval_duration_ms DOUBLE PRECISION NULL,
    generation_duration_ms DOUBLE PRECISION NULL,
    total_duration_ms DOUBLE PRECISION NULL,

    context_chunk_uids JSONB NOT NULL DEFAULT '[]'::jsonb,
    context_records JSONB NOT NULL DEFAULT '[]'::jsonb,
    prompt_context_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
    context_snapshot_sha256 TEXT NULL,

    answer_text TEXT NULL,
    answer_payload JSONB NULL,

    expansion_trace JSONB NULL,
    retrieval_trace JSONB NULL,
    retrieval_summary JSONB NOT NULL DEFAULT '{}'::jsonb,

    prompt_template_sha256 TEXT NULL,
    rendered_prompt_sha256 TEXT NULL,

    input_token_count INTEGER NULL,
    output_token_count INTEGER NULL,

    error_code TEXT NULL,
    error_message TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,

    UNIQUE (session_id, mode),
    CHECK (mode IN ('baseline', 'strong_only', 'strong_story')),
    CHECK (status IN ('pending', 'running', 'retrieval_completed', 'completed', 'failed')),
    CHECK (retrieval_source_mode IS NULL OR retrieval_source_mode IN ('baseline', 'strong_only', 'strong_story')),
    CHECK (generated_variant_count >= 0),
    CHECK (vector_search_call_count >= 0),
    CHECK (final_context_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_experiment_sessions_started_at
    ON experiment_sessions (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_experiment_sessions_status_started_at
    ON experiment_sessions (status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_experiment_mode_runs_session_id
    ON experiment_mode_runs (session_id);

CREATE INDEX IF NOT EXISTS idx_experiment_mode_runs_mode_created_at
    ON experiment_mode_runs (mode, created_at DESC);
