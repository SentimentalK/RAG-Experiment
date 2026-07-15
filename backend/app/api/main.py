from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.clients.groq_gpt_oss_client import GroqGptOssClient
from app.db.connection import get_connection
from app.providers.minilm_provider import MiniLMProvider
from app.services.rag_answer_service import RagAnswerService
from app.services.vector_search_service import VectorSearchService

from app.api.routes.health import router as health_router
from app.api.routes.rag import router as rag_router

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 1. Warm up embedding provider
    provider = MiniLMProvider()
    provider.encode("Sherlock Holmes")

    # 2. Verify database connection
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()

    # 3. Instantiate client and services
    groq_client = GroqGptOssClient(settings)
    search_service = VectorSearchService(provider)

    rag_service = RagAnswerService(
        search_service=search_service,
        groq_client=groq_client,
    )

    # 4. Save to app state
    app.state.rag_service = rag_service
    app.state.embedding_provider = provider
    app.state.ready = True

    try:
        yield
    finally:
        # 5. Clean up resources
        app.state.ready = False
        groq_client.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Include Routers
    app.include_router(health_router, prefix="/api")
    app.include_router(rag_router, prefix="/api")

    return app


app = create_app()
