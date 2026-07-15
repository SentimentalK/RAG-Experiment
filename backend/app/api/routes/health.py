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
    Verifies that the embedding model is loaded, the service is initialized,
    and database connection is active.
    """
    is_ready = getattr(request.app.state, "ready", False)
    if not is_ready:
        response.status_code = 503
        return {"status": "degraded", "detail": "Application state not ready"}

    # Database check
    db_status = "disconnected"
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        db_status = "connected"
    except Exception:
        pass

    if db_status != "connected":
        response.status_code = 503
        return {
            "status": "degraded",
            "detail": "Database connection failed"
        }

    # Model status
    emb_model = "sentence-transformers/all-MiniLM-L6-v2"
    gen_model = settings.GROQ_MODEL

    return {
        "status": "ready",
        "embedding_model": emb_model,
        "generation_model": gen_model,
        "database": db_status
    }


@router.get("")
def health_alias(request: Request, response: Response):
    """Alias /health to /health/ready for backward compatibility."""
    return readiness(request, response)
