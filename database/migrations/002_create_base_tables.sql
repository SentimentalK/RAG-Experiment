CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    source_name TEXT NOT NULL,
    source_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sections (
    section_id BIGSERIAL PRIMARY KEY,

    document_id TEXT NOT NULL
        REFERENCES documents(document_id)
        ON DELETE CASCADE,

    section_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    section_text TEXT NOT NULL,

    CHECK (section_order > 0),

    UNIQUE (document_id, section_order)
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id BIGSERIAL PRIMARY KEY,

    chunk_uid TEXT NOT NULL UNIQUE,

    section_id BIGINT NOT NULL
        REFERENCES sections(section_id)
        ON DELETE CASCADE,

    chunk_order INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    overlap_tokens INTEGER NOT NULL DEFAULT 0,
    chunk_text TEXT NOT NULL,

    CHECK (chunk_order > 0),
    CHECK (token_count > 0),
    CHECK (token_count <= 220),
    CHECK (overlap_tokens >= 0),
    CHECK (length(btrim(chunk_text)) > 0),

    UNIQUE (section_id, chunk_order)
);

CREATE TABLE IF NOT EXISTS minilm_embeddings (
    chunk_id BIGINT PRIMARY KEY
        REFERENCES chunks(chunk_id)
        ON DELETE CASCADE,

    model_name TEXT NOT NULL,
    dimensions SMALLINT NOT NULL DEFAULT 384,
    normalized BOOLEAN NOT NULL DEFAULT TRUE,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (dimensions = 384)
);
