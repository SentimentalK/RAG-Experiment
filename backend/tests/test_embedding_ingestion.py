import pytest
import psycopg
import hashlib
import numpy as np
from app.db.connection import get_connection
from app.services.embedding_ingestion_service import EmbeddingIngestionService
from app.services.content_ingestion_service import ContentIngestionService

@pytest.fixture(autouse=True)
def clean_database():
    """
    Autouse fixture that runs before and after each test to ensure the database is clean.
    """
    def _clear():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE document_id LIKE 'test-%' OR document_id LIKE 'doc-%';")
            conn.commit()
    _clear()
    yield
    _clear()

@pytest.fixture
def connection():
    with get_connection() as conn:
        yield conn

@pytest.fixture
def service() -> EmbeddingIngestionService:
    return EmbeddingIngestionService()

@pytest.fixture
def doc_id() -> str:
    return "test-doc-123"

@pytest.fixture
def sample_texts() -> list[str]:
    return [
        "First sentence text.",
        "Second sentence text.",
        "Third sentence text."
    ]

@pytest.fixture
def pre_ingested_db(connection, sample_texts, doc_id):
    """
    Ingests document, sections, and chunks in the DB to prepare for embedding ingestion.
    """
    document = {
        "document_id": doc_id,
        "title": "Test Book",
        "author": "Author",
        "source_name": "Source"
    }
    sections = [
        {"section_order": 1, "title": "Sec 1", "text": "Sec text 1"},
        {"section_order": 2, "title": "Sec 2", "text": "Sec text 2"}
    ]
    chunks = [
        {"chunk_id": "c-1", "section_order": 1, "section_title": "Sec 1", "chunk_order": 1, "token_count": 5, "text": sample_texts[0]},
        {"chunk_id": "c-2", "section_order": 1, "section_title": "Sec 1", "chunk_order": 2, "token_count": 5, "text": sample_texts[1]},
        {"chunk_id": "c-3", "section_order": 2, "section_title": "Sec 2", "chunk_order": 1, "token_count": 5, "text": sample_texts[2]}
    ]
    content_service = ContentIngestionService()
    content_service.ingest(document, sections, chunks, replace=False)
    
    # Return expected chunks fingerprint mapping
    def make_sha(t):
        return hashlib.sha256(t.encode("utf-8")).hexdigest()

    expected_chunks = {
        c["chunk_id"]: {
            "section_order": c["section_order"],
            "section_title": c["section_title"],
            "chunk_order": c["chunk_order"],
            "token_count": c["token_count"],
            "text_sha256": make_sha(c["text"])
        }
        for c in chunks
    }
    return expected_chunks

# ----------------- Input validations tests (Not requiring DB) -----------------

def test_validate_inputs_bad_dimensions(service):
    embeddings = np.zeros((3, 383), dtype=np.float32)
    index = [{"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5}]
    with pytest.raises(ValueError, match="Expected 384 dimensions"):
        service.validate_inputs(embeddings, index)

def test_validate_inputs_bad_dtype(service):
    embeddings = np.zeros((1, 384), dtype=np.float64)
    # L2 normalize first
    embeddings[0, 0] = 1.0
    index = [{"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5}]
    with pytest.raises(ValueError, match="Expected float32"):
        service.validate_inputs(embeddings, index)

def test_validate_inputs_non_finite(service):
    embeddings = np.zeros((1, 384), dtype=np.float32)
    embeddings[0, 0] = np.nan
    index = [{"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5}]
    with pytest.raises(ValueError, match="Embedding matrix contains invalid values"):
        service.validate_inputs(embeddings, index)

def test_validate_inputs_unnormalized(service):
    embeddings = np.zeros((1, 384), dtype=np.float32)
    embeddings[0, 0] = 0.5  # norm is 0.5, not 1.0
    index = [{"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5}]
    with pytest.raises(ValueError, match="One or more embeddings are not normalized"):
        service.validate_inputs(embeddings, index)

def test_validate_inputs_bad_index_count(service):
    embeddings = np.zeros((2, 384), dtype=np.float32)
    embeddings[:, 0] = 1.0
    index = [{"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5}]
    with pytest.raises(ValueError, match="does not match matrix row count"):
        service.validate_inputs(embeddings, index)

def test_validate_inputs_duplicate_row_index(service):
    embeddings = np.zeros((2, 384), dtype=np.float32)
    embeddings[:, 0] = 1.0
    index = [
        {"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5},
        {"row_index": 0, "chunk_id": "c-2", "section_order": 1, "section_title": "A", "chunk_order": 2, "token_count": 5}
    ]
    with pytest.raises(ValueError, match="Duplicate row_index found"):
        service.validate_inputs(embeddings, index)

def test_validate_inputs_duplicate_chunk_id(service):
    embeddings = np.zeros((2, 384), dtype=np.float32)
    embeddings[:, 0] = 1.0
    index = [
        {"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5},
        {"row_index": 1, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 2, "token_count": 5}
    ]
    with pytest.raises(ValueError, match="Duplicate chunk_id found"):
        service.validate_inputs(embeddings, index)

def test_validate_inputs_non_contiguous_row_index(service):
    embeddings = np.zeros((2, 384), dtype=np.float32)
    embeddings[:, 0] = 1.0
    index = [
        {"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5},
        {"row_index": 2, "chunk_id": "c-2", "section_order": 1, "section_title": "A", "chunk_order": 2, "token_count": 5}
    ]
    with pytest.raises(ValueError, match="Row indices must be contiguous"):
        service.validate_inputs(embeddings, index)

def test_validate_inputs_forbidden_fields(service):
    embeddings = np.zeros((1, 384), dtype=np.float32)
    embeddings[0, 0] = 1.0
    index = [{"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "A", "chunk_order": 1, "token_count": 5, "text": "forbidden text"}]
    with pytest.raises(ValueError, match="forbidden field 'text'"):
        service.validate_inputs(embeddings, index)

# ----------------- DB Ingestion tests (using autouse db cleanup) -----------------

def test_ingest_embeddings_successful(connection, service, doc_id, pre_ingested_db):
    """
    Verifies that embeddings can be successfully ingested and verified,
    maintaining correct dimensions and norms.
    """
    expected_chunks = pre_ingested_db

    # Create 3x384 matrix
    matrix = np.zeros((3, 384), dtype=np.float32)
    matrix[:, 0] = 1.0 # set L2 norm = 1.0

    index_records = [
        {"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "Sec 1", "chunk_order": 1, "token_count": 5},
        {"row_index": 1, "chunk_id": "c-2", "section_order": 1, "section_title": "Sec 1", "chunk_order": 2, "token_count": 5},
        {"row_index": 2, "chunk_id": "c-3", "section_order": 2, "section_title": "Sec 2", "chunk_order": 1, "token_count": 5}
    ]

    stats = service.ingest(
        document_id=doc_id,
        embeddings=matrix,
        index_records=index_records,
        expected_chunks=expected_chunks,
        model_name="all-MiniLM-L6-v2",
        replace=False,
        expected_count=3
    )

    assert stats["status"] == "success"
    assert stats["inserted_embedding_count"] == 3
    assert np.isclose(stats["minimum_vector_norm"], 1.0, atol=1e-5)
    assert np.isclose(stats["maximum_vector_norm"], 1.0, atol=1e-5)

    # Double check Postgres counts
    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM minilm_embeddings;")
        assert cur.fetchone()[0] == 3

def test_ingest_embeddings_replace_and_duplicate(connection, service, doc_id, pre_ingested_db):
    """
    Verifies that re-ingesting without replace raises error,
    and with replace it deletes minilm_embeddings without deleting chunks.
    """
    expected_chunks = pre_ingested_db

    matrix = np.zeros((3, 384), dtype=np.float32)
    matrix[:, 0] = 1.0

    index_records = [
        {"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "Sec 1", "chunk_order": 1, "token_count": 5},
        {"row_index": 1, "chunk_id": "c-2", "section_order": 1, "section_title": "Sec 1", "chunk_order": 2, "token_count": 5},
        {"row_index": 2, "chunk_id": "c-3", "section_order": 2, "section_title": "Sec 2", "chunk_order": 1, "token_count": 5}
    ]

    # First ingest
    service.ingest(doc_id, matrix, index_records, expected_chunks, "all-MiniLM-L6-v2", replace=False)

    # Second ingest without replace -> raise ValueError
    with pytest.raises(ValueError, match="already exist"):
        service.ingest(doc_id, matrix, index_records, expected_chunks, "all-MiniLM-L6-v2", replace=False)

    # Second ingest with replace -> success, verify chunks are not deleted (chunks count == 3)
    service.ingest(doc_id, matrix, index_records, expected_chunks, "all-MiniLM-L6-v2", replace=True)

    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM minilm_embeddings;")
        assert cur.fetchone()[0] == 3
        cur.execute("SELECT COUNT(*) FROM chunks;")
        assert cur.fetchone()[0] == 3

class BrokenEmbeddingIngestionService(EmbeddingIngestionService):
    def _build_insert_rows(self, embeddings, ordered_records, database_chunk_ids, model_name):
        rows = super()._build_insert_rows(embeddings, ordered_records, database_chunk_ids, model_name)
        if rows:
            # Change the dimension metadata to 383 on the last row to trigger database constraint
            rows[-1]["dimensions"] = 383
        return rows

def test_database_level_atomicity_on_dimension_constraint(connection, doc_id, pre_ingested_db):
    """
    Verifies that if a database CheckViolation occurs during insert, the entire transaction rolls back.
    Uses BrokenEmbeddingIngestionService which alters the last row dimension to 383.
    """
    expected_chunks = pre_ingested_db
    broken_service = BrokenEmbeddingIngestionService()

    matrix = np.zeros((3, 384), dtype=np.float32)
    matrix[:, 0] = 1.0

    index_records = [
        {"row_index": 0, "chunk_id": "c-1", "section_order": 1, "section_title": "Sec 1", "chunk_order": 1, "token_count": 5},
        {"row_index": 1, "chunk_id": "c-2", "section_order": 1, "section_title": "Sec 1", "chunk_order": 2, "token_count": 5},
        {"row_index": 2, "chunk_id": "c-3", "section_order": 2, "section_title": "Sec 2", "chunk_order": 1, "token_count": 5}
    ]

    with pytest.raises(psycopg.Error):
        broken_service.ingest(doc_id, matrix, index_records, expected_chunks, "all-MiniLM-L6-v2", replace=False)

    # Verify atomicity: minilm_embeddings must remain completely empty for this document
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM minilm_embeddings e
            JOIN chunks c ON c.chunk_id = e.chunk_id
            JOIN sections s ON s.section_id = c.section_id
            WHERE s.document_id = %s;
            """,
            (doc_id,)
        )
        assert cur.fetchone()[0] == 0
