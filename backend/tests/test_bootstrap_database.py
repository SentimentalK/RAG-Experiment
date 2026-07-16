import pytest
import numpy as np
import psycopg
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.db.connection import get_connection
from app.core.config import settings
from app.api.main import create_app
from app.cli.bootstrap_database import run_bootstrap, verify_schema_exists

# Fixture to clear DB Gutenberg document before and after each test
@pytest.fixture(autouse=True)
def clean_gutenberg_doc():
    def _delete():
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM documents WHERE document_id = 'gutenberg-1661';")
                    cur.execute("DELETE FROM documents WHERE document_id = 'dummy-doc';")
    _delete()
    yield
    _delete()

def test_bootstrap_database_empty_and_idempotency():
    # 1. Test empty database imports all records successfully
    run_bootstrap()
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents WHERE document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT COUNT(*) FROM sections WHERE document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 12
            cur.execute("SELECT COUNT(*) FROM chunks c JOIN sections s ON s.section_id = c.section_id WHERE s.document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 909
            cur.execute("SELECT COUNT(*) FROM minilm_embeddings e JOIN chunks c ON c.chunk_id = e.chunk_id JOIN sections s ON s.section_id = c.section_id WHERE s.document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 909

    # 2. Test second execution succeeds without duplicate inserts (idempotent)
    with patch("app.services.content_ingestion_service.ContentIngestionService.ingest") as mock_content_ingest, \
         patch("app.services.embedding_ingestion_service.EmbeddingIngestionService.ingest") as mock_emb_ingest:
        
        run_bootstrap()
        
        # Verify no ingestion calls are made because data matches perfectly
        mock_content_ingest.assert_not_called()
        mock_emb_ingest.assert_not_called()

def test_bootstrap_database_partial_embedding_repair():
    # Seed the content first
    run_bootstrap()

    # Delete embeddings so state is partial (chunks=909, embeddings=0)
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM minilm_embeddings e
                    USING chunks c, sections s
                    WHERE e.chunk_id = c.chunk_id
                      AND c.section_id = s.section_id
                      AND s.document_id = 'gutenberg-1661';
                """)

    # Verify we have chunks but 0 embeddings
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM minilm_embeddings e
                JOIN chunks c ON c.chunk_id = e.chunk_id
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = 'gutenberg-1661';
            """)
            assert cur.fetchone()[0] == 0

    # Running bootstrap now should only trigger embedding repair (no content ingest)
    with patch("app.services.content_ingestion_service.ContentIngestionService.ingest") as mock_content_ingest:
        run_bootstrap()
        mock_content_ingest.assert_not_called()

    # Verify embeddings are successfully restored to 909
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM minilm_embeddings e
                JOIN chunks c ON c.chunk_id = e.chunk_id
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = 'gutenberg-1661';
            """)
            assert cur.fetchone()[0] == 909

def test_bootstrap_database_partial_content_repair():
    # Seed document & sections, but only ingest 5 sections (incomplete content)
    run_bootstrap()
    
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # Deleting some sections triggers cascade delete of chunks and embeddings
                cur.execute("DELETE FROM sections WHERE document_id = 'gutenberg-1661' AND section_order > 5;")

    # Verify we have fewer than 12 sections
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sections WHERE document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 5

    # Seeder should recognize partial content state (no conflicts) and trigger a full replacement repair
    run_bootstrap()

    # Verify everything is repaired successfully
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sections WHERE document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 12
            cur.execute("SELECT COUNT(*) FROM chunks c JOIN sections s ON s.section_id = c.section_id WHERE s.document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 909
            cur.execute("SELECT COUNT(*) FROM minilm_embeddings e JOIN chunks c ON c.chunk_id = e.chunk_id JOIN sections s ON s.section_id = c.section_id WHERE s.document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 909

def test_bootstrap_database_conflict_rejection():
    # Insert conflicting document info
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO documents (document_id, title, author, source_name)
                    VALUES ('gutenberg-1661', 'Conflicting Book Title', 'Arthur Conan Doyle', 'Project Gutenberg');
                """)

    # Running seeder should raise system exit due to title conflict
    with pytest.raises(SystemExit) as exc_info:
        run_bootstrap()
    assert exc_info.value.code == 1

def test_bootstrap_database_chunk_text_conflict():
    run_bootstrap()

    # Update a single chunk text to conflict with image
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE chunks c
                    SET chunk_text = 'Conflicting text content'
                    FROM sections s
                    WHERE c.section_id = s.section_id
                      AND s.document_id = 'gutenberg-1661'
                      AND c.chunk_uid = 'g1661-s01-c0001';
                """)

    # Running seeder should raise system exit due to chunk text mismatch
    with pytest.raises(SystemExit) as exc_info:
        run_bootstrap()
    assert exc_info.value.code == 1

def test_bootstrap_database_document_isolation():
    # 1. Insert a dummy separate document
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO documents (document_id, title, source_name)
                    VALUES ('dummy-doc', 'Dummy Title', 'Dummy Source');
                """)
                cur.execute("""
                    INSERT INTO sections (document_id, section_order, title, section_text)
                    VALUES ('dummy-doc', 1, 'Sec 1', 'Sec text')
                    RETURNING section_id;
                """)
                sec_id = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO chunks (chunk_uid, section_id, chunk_order, token_count, chunk_text)
                    VALUES ('dummy-chunk-1', %s, 1, 10, 'Chunk text')
                    RETURNING chunk_id;
                """, (sec_id,))
                chunk_id = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO minilm_embeddings (chunk_id, model_name, dimensions, normalized, embedding)
                    VALUES (%s, 'dummy-model', 384, TRUE, %s);
                """, (chunk_id, [0.0]*384))

    # 2. Run bootstrap (empty database scenario for Gutenberg)
    run_bootstrap()

    # 3. Verify Gutenberg was successfully seeded
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks c JOIN sections s ON s.section_id = c.section_id WHERE s.document_id = 'gutenberg-1661';")
            assert cur.fetchone()[0] == 909

            # 4. Verify dummy document and its associated records were NOT modified or deleted
            cur.execute("SELECT COUNT(*) FROM documents WHERE document_id = 'dummy-doc';")
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT chunk_text FROM chunks WHERE chunk_uid = 'dummy-chunk-1';")
            assert cur.fetchone()[0] == "Chunk text"

def test_bootstrap_database_concurrency_lock():
    # Verify we can run verify_schema_exists
    verify_schema_exists()

    # Attempting to run a second bootstrap process concurrently should fail
    # We will simulate this by holding the session lock in a separate connection
    lock_conn = psycopg.connect(settings.DATABASE_URL)
    lock_conn.autocommit = True
    try:
        with lock_conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtext('rag-bootstrap:gutenberg-1661'));")
            assert cur.fetchone()[0] is True

        # Now, call the seeder script's entrypoint main() which should fail to acquire lock and exit 1
        with patch("sys.exit") as mock_exit:
            from app.cli.bootstrap_database import main as cli_main
            cli_main()
            mock_exit.assert_called_once_with(1)

    finally:
        with lock_conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(hashtext('rag-bootstrap:gutenberg-1661'));")
        lock_conn.close()

# ----------------- Readiness Endpoint Tests -----------------

def test_readiness_endpoint_states():
    app = create_app()
    with TestClient(app) as client:
        # Mock settings to have groq config present
        settings.GROQ_API_KEY = "test-key"
        settings.GROQ_MODEL = "test-model"
        settings.GROQ_BASE_URL = "test-url"

        # 1. State: Completely Empty DB
        # Readiness should return 503 and status "not_ready"
        response = client.get("/api/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "connected"
        assert data["dataset"] == "incomplete"
        assert data["actual_chunks"] == 0
        assert data["actual_embeddings"] == 0

        # 2. State: Fully Populated DB
        # Seed the database
        run_bootstrap()
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

        # 3. State: Missing embeddings (partial)
        # Delete embeddings
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM minilm_embeddings e
                        USING chunks c, sections s
                        WHERE e.chunk_id = c.chunk_id
                          AND c.section_id = s.section_id
                          AND s.document_id = 'gutenberg-1661';
                    """)
        response = client.get("/api/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["actual_chunks"] == 909
        assert data["actual_embeddings"] == 0

        # 4. State: Database unavailable
        with patch("app.api.routes.health.get_connection", side_effect=Exception("DB Down")):
            response = client.get("/api/health/ready")
            assert response.status_code == 503
            assert response.json()["database"] == "disconnected"
