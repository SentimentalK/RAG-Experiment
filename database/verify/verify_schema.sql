SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';

SELECT
    table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

SELECT
    column_name,
    data_type,
    udt_name
FROM information_schema.columns
WHERE table_name = 'minilm_embeddings'
ORDER BY ordinal_position;

BEGIN;

INSERT INTO documents (
    document_id,
    title,
    author,
    source_name
)
VALUES (
    'schema-test',
    'Schema Test',
    'Test Author',
    'Local'
);

INSERT INTO sections (
    document_id,
    section_order,
    title,
    section_text
)
VALUES (
    'schema-test',
    1,
    'Test Section',
    'Test section text.'
);

INSERT INTO chunks (
    chunk_uid,
    section_id,
    chunk_order,
    token_count,
    overlap_tokens,
    chunk_text
)
SELECT
    'schema-test-chunk',
    section_id,
    1,
    5,
    0,
    'Test chunk text.'
FROM sections
WHERE document_id = 'schema-test'
  AND section_order = 1;

INSERT INTO minilm_embeddings (
    chunk_id,
    model_name,
    dimensions,
    normalized,
    embedding
)
SELECT
    chunk_id,
    'schema-test-model',
    384,
    TRUE,
    array_prepend(
        1.0::real,
        array_fill(0.0::real, ARRAY[383])
    )::vector(384)
FROM chunks
WHERE chunk_uid = 'schema-test-chunk';

SELECT
    c.chunk_uid,
    vector_dims(e.embedding) AS dimensions,
    vector_norm(e.embedding) AS norm
FROM minilm_embeddings e
JOIN chunks c
    ON c.chunk_id = e.chunk_id
WHERE c.chunk_uid = 'schema-test-chunk';

ROLLBACK;
