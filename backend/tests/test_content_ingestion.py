import pytest
import psycopg
from app.db.connection import get_connection
from app.services.content_ingestion_service import ContentIngestionService

@pytest.fixture(autouse=True)
def clean_database():
    """
    Autouse fixture to clean the database before and after each test.
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
    """
    Fixture that yields a psycopg database connection.
    """
    with get_connection() as conn:
        yield conn

@pytest.fixture
def service() -> ContentIngestionService:
    return ContentIngestionService()

@pytest.fixture
def sample_document() -> dict:
    return {
        "document_id": "test-doc-123",
        "title": "Test Document",
        "author": "Test Author",
        "source_name": "Test Source",
        "source_reference": "Ref-1"
    }

@pytest.fixture
def sample_sections() -> list[dict]:
    return [
        {"section_order": 1, "title": "First Section", "text": "This is first section text."},
        {"section_order": 2, "title": "Second Section", "text": "This is second section text."}
    ]

@pytest.fixture
def sample_chunks() -> list[dict]:
    return [
        {"chunk_id": "chk-1", "section_order": 1, "section_title": "First Section", "chunk_order": 1, "token_count": 10, "overlap_tokens": 0, "text": "Chunk one text."},
        {"chunk_id": "chk-2", "section_order": 1, "section_title": "First Section", "chunk_order": 2, "token_count": 15, "overlap_tokens": 5, "text": "Chunk two text."},
        {"chunk_id": "chk-3", "section_order": 2, "section_title": "Second Section", "chunk_order": 1, "token_count": 20, "overlap_tokens": 0, "text": "Chunk three text."}
    ]

# ----------------- Input validations tests (Not requiring DB) -----------------

def test_validate_data_duplicate_section_order_rejected(service, sample_document, sample_sections, sample_chunks):
    bad_sections = [
        {"section_order": 1, "title": "First Section", "text": "Text."},
        {"section_order": 1, "title": "Second Section", "text": "Text."}
    ]
    with pytest.raises(ValueError, match="Duplicate 'section_order' found"):
        service.validate_data(sample_document, bad_sections, sample_chunks)

def test_validate_data_duplicate_chunk_id_rejected(service, sample_document, sample_sections, sample_chunks):
    bad_chunks = [
        {"chunk_id": "chk-1", "section_order": 1, "section_title": "First Section", "chunk_order": 1, "token_count": 10, "text": "Text."},
        {"chunk_id": "chk-1", "section_order": 1, "section_title": "First Section", "chunk_order": 2, "token_count": 10, "text": "Text."}
    ]
    with pytest.raises(ValueError, match="Duplicate chunk_id found"):
        service.validate_data(sample_document, sample_sections, bad_chunks)

def test_validate_data_non_contiguous_section_order_rejected(service, sample_document, sample_sections, sample_chunks):
    bad_sections = [
        {"section_order": 1, "title": "First", "text": "Text."},
        {"section_order": 3, "title": "Second", "text": "Text."}
    ]
    with pytest.raises(ValueError, match="Section orders must be contiguous"):
        service.validate_data(sample_document, bad_sections, sample_chunks)

def test_validate_data_mismatched_section_title_rejected(service, sample_document, sample_sections, sample_chunks):
    bad_chunks = [
        {"chunk_id": "chk-1", "section_order": 1, "section_title": "WRONG TITLE", "chunk_order": 1, "token_count": 10, "text": "Text."}
    ]
    with pytest.raises(ValueError, match="Section title mismatch"):
        service.validate_data(sample_document, sample_sections, bad_chunks)

def test_validate_data_non_contiguous_chunk_order_rejected(service, sample_document, sample_sections, sample_chunks):
    bad_chunks = [
        {"chunk_id": "chk-1", "section_order": 1, "section_title": "First Section", "chunk_order": 1, "token_count": 10, "text": "Text."},
        {"chunk_id": "chk-2", "section_order": 1, "section_title": "First Section", "chunk_order": 3, "token_count": 10, "text": "Text."}
    ]
    with pytest.raises(ValueError, match="Chunk orders for section 1 must be contiguous starting from 1"):
        service.validate_data(sample_document, sample_sections, bad_chunks)

def test_validate_data_overlong_token_count_rejected(service, sample_document, sample_sections, sample_chunks):
    bad_chunks = [
        {"chunk_id": "chk-1", "section_order": 1, "section_title": "First Section", "chunk_order": 1, "token_count": 221, "text": "Text."}
    ]
    with pytest.raises(ValueError, match="'token_count' must be between 1 and 220"):
        service.validate_data(sample_document, sample_sections, bad_chunks)


# ----------------- DB Ingestion tests (using rollback fixture) -----------------

def test_ingest_successful(connection, service, sample_document, sample_sections, sample_chunks):
    """
    Verifies that a valid small dataset can be successfully ingested, counts verify,
    and foreign key mapping behaves correctly.
    """
    # 1. Validate
    service.validate_data(sample_document, sample_sections, sample_chunks, expected_section_count=2, expected_chunk_count=3)
    
    # 2. Ingest
    stats = service.ingest(sample_document, sample_sections, sample_chunks, replace=False)
    assert stats["status"] == "success"
    assert stats["document_count"] == 1
    assert stats["section_count"] == 2
    assert stats["chunk_count"] == 3
    assert stats["embedding_count"] == 0

    # 3. Verify mappings and data structure in database
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT c.chunk_uid, s.section_order, s.title
            FROM chunks c
            JOIN sections s ON s.section_id = c.section_id
            WHERE s.document_id = %s
            ORDER BY c.chunk_uid;
            """,
            (sample_document["document_id"],)
        )
        rows = cur.fetchall()
        assert len(rows) == 3
        # Row 1 mapping: chk-1 -> section 1 title
        assert rows[0] == ("chk-1", 1, "First Section")
        # Row 2 mapping: chk-2 -> section 1 title
        assert rows[1] == ("chk-2", 1, "First Section")
        # Row 3 mapping: chk-3 -> section 2 title
        assert rows[2] == ("chk-3", 2, "Second Section")

        # 4. Verify embeddings count remains 0
        cur.execute(
            """
            SELECT COUNT(*) FROM minilm_embeddings e
            JOIN chunks c ON c.chunk_id = e.chunk_id
            JOIN sections s ON s.section_id = c.section_id
            WHERE s.document_id = %s;
            """,
            (sample_document["document_id"],)
        )
        assert cur.fetchone()[0] == 0

def test_ingest_already_exists_behavior(connection, service, sample_document, sample_sections, sample_chunks):
    """
    Verifies that re-ingesting an existing document_id is rejected by default,
    but is accepted and cleanly replaced when replace=True is passed.
    """
    # Ingest once
    service.ingest(sample_document, sample_sections, sample_chunks, replace=False)
    
    # Re-ingest without replace must raise ValueError
    with pytest.raises(ValueError, match="already exists"):
        service.ingest(sample_document, sample_sections, sample_chunks, replace=False)
        
    # Re-ingest with replace must succeed
    stats = service.ingest(sample_document, sample_sections, sample_chunks, replace=True)
    assert stats["status"] == "success"

def test_database_level_atomicity_on_unique_constraint(connection, service, sample_document, sample_sections, sample_chunks):
    """
    Verifies that if a database unique constraint fails during executemany, the entire transaction is rolled back.
    - Pre-inserts a document 'doc-existing' with a chunk having 'conflict-chunk' uid.
    - Attempts to insert a new document 'doc-new' whose last chunk also uses 'conflict-chunk'.
    - Confirms that 'doc-new' was rolled back completely, leaving only 'doc-existing'.
    """
    # 1. Pre-insert document A with 'conflict-chunk' chunk_uid
    doc_a = {
        "document_id": "doc-existing",
        "title": "Doc Existing",
        "author": "Author",
        "source_name": "Source"
    }
    sec_a = [{"section_order": 1, "title": "Sec A", "text": "Sec Text"}]
    chk_a = [{"chunk_id": "conflict-chunk", "section_order": 1, "section_title": "Sec A", "chunk_order": 1, "token_count": 10, "text": "Chunk text."}]
    
    service.ingest(doc_a, sec_a, chk_a, replace=False)

    # 2. Prepare document B with a duplicate chunk_uid on the last chunk
    doc_b = {
        "document_id": "doc-new",
        "title": "Doc New",
        "author": "Author",
        "source_name": "Source"
    }
    sec_b = [
        {"section_order": 1, "title": "Sec B1", "text": "Sec Text"},
        {"section_order": 2, "title": "Sec B2", "text": "Sec Text"}
    ]
    # Memory validation passes since 'conflict-chunk' is unique within the batch of B
    chk_b = [
        {"chunk_id": "chk-unique-b1", "section_order": 1, "section_title": "Sec B1", "chunk_order": 1, "token_count": 10, "text": "Chunk text."},
        {"chunk_id": "conflict-chunk", "section_order": 2, "section_title": "Sec B2", "chunk_order": 1, "token_count": 15, "text": "Duplicate chunk text."}
    ]

    # Ingestion should fail on the database unique constraint for chunks.chunk_uid
    with pytest.raises(psycopg.Error):
        service.ingest(doc_b, sec_b, chk_b, replace=False)

    # 3. Assert atomicity: doc-new has no residues whatsoever
    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents WHERE document_id = 'doc-new';")
        assert cur.fetchone()[0] == 0
        
        cur.execute("SELECT COUNT(*) FROM sections WHERE document_id = 'doc-new';")
        assert cur.fetchone()[0] == 0

        # Verify doc-existing remains completely intact
        cur.execute("SELECT COUNT(*) FROM documents WHERE document_id = 'doc-existing';")
        assert cur.fetchone()[0] == 1
        
        cur.execute("SELECT COUNT(*) FROM chunks c JOIN sections s ON s.section_id = c.section_id WHERE s.document_id = 'doc-existing';")
        assert cur.fetchone()[0] == 1
