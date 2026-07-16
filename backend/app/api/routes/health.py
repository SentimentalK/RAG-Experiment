from fastapi import APIRouter, Request, Response
from app.db.connection import get_connection
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/live")
def liveness():
    """Simple probe to verify the application process is alive."""
    return {"status": "ok"}


@router.get("/ready")
def readiness(request: Request, response: Response):
    """
    Checks if the application is fully ready to serve traffic.
    Verifies FastAPI initialization, MiniLM model preloading, database connectivity,
    dataset completeness, embedding model metadata, and Groq environment configuration.
    """
    # 1. FastAPI Initialization Completed
    is_ready = getattr(request.app.state, "ready", False)
    if not is_ready:
        response.status_code = 503
        return {
            "status": "not_ready",
            "database": "unknown",
            "dataset": "not_initialized",
            "expected_chunks": 909,
            "actual_chunks": 0,
            "expected_embeddings": 909,
            "actual_embeddings": 0
        }

    # 2. Groq Configuration exists
    if not settings.GROQ_API_KEY or not settings.GROQ_MODEL or not settings.GROQ_BASE_URL:
        response.status_code = 503
        return {
            "status": "not_ready",
            "database": "unknown",
            "dataset": "missing_groq_config",
            "expected_chunks": 909,
            "actual_chunks": 0,
            "expected_embeddings": 909,
            "actual_embeddings": 0
        }

    # 3. Database connectivity and dataset structural check
    db_status = "disconnected"
    doc_count = 0
    sec_count = 0
    chunk_count = 0
    emb_count = 0
    missing_emb_count = 0
    emb_metadata_correct = True

    try:
        with get_connection() as conn:
            db_status = "connected"
            with conn.cursor() as cur:
                # Query counts in one fast roundtrip
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM documents WHERE document_id = 'gutenberg-1661') AS doc_count,
                        (SELECT COUNT(*) FROM sections WHERE document_id = 'gutenberg-1661') AS sec_count,
                        (SELECT COUNT(*) FROM chunks c JOIN sections s ON s.section_id = c.section_id WHERE s.document_id = 'gutenberg-1661') AS chunk_count,
                        (SELECT COUNT(*) FROM minilm_embeddings e JOIN chunks c ON c.chunk_id = e.chunk_id JOIN sections s ON s.section_id = c.section_id WHERE s.document_id = 'gutenberg-1661') AS emb_count,
                        (SELECT COUNT(*) FROM chunks c JOIN sections s ON s.section_id = c.section_id LEFT JOIN minilm_embeddings e ON e.chunk_id = c.chunk_id WHERE s.document_id = 'gutenberg-1661' AND e.chunk_id IS NULL) AS missing_emb_count;
                """)
                counts = cur.fetchone()
                if counts:
                    doc_count, sec_count, chunk_count, emb_count, missing_emb_count = counts

                # Query metadata validation
                cur.execute("""
                    SELECT DISTINCT model_name, dimensions, normalized
                    FROM minilm_embeddings e
                    JOIN chunks c ON c.chunk_id = e.chunk_id
                    JOIN sections s ON s.section_id = c.section_id
                    WHERE s.document_id = 'gutenberg-1661';
                """)
                rows = cur.fetchall()
                for model_name, dimensions, normalized in rows:
                    if model_name != "sentence-transformers/all-MiniLM-L6-v2" or dimensions != 384 or not normalized:
                        emb_metadata_correct = False

    except Exception:
        db_status = "disconnected"

    # Verify database connection succeeds
    if db_status != "connected":
        response.status_code = 503
        return {
            "status": "not_ready",
            "database": "disconnected",
            "dataset": "unknown",
            "expected_chunks": 909,
            "actual_chunks": 0,
            "expected_embeddings": 909,
            "actual_embeddings": 0
        }

    # Verify counts and metadata are correct
    dataset_complete = (
        doc_count == 1 and
        sec_count == 12 and
        chunk_count == 909 and
        emb_count == 909 and
        missing_emb_count == 0 and
        emb_metadata_correct
    )

    if not dataset_complete:
        response.status_code = 503
        return {
            "status": "not_ready",
            "database": "connected",
            "dataset": "incomplete",
            "expected_chunks": 909,
            "actual_chunks": chunk_count,
            "expected_embeddings": 909,
            "actual_embeddings": emb_count
        }

    # All checks pass
    return {
        "status": "ready",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "generation_model": settings.GROQ_MODEL,
        "database": "connected"
    }


@router.get("")
def health_alias(request: Request, response: Response):
    """Alias /health to /health/ready for backward compatibility."""
    return readiness(request, response)
