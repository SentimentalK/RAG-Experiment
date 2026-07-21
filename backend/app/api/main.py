from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.clients.groq_gpt_oss_client import GroqGptOssClient
from app.db.connection import get_connection
from app.providers.minilm_provider import MiniLMProvider
from app.services.rag_answer_service import RagAnswerService
from app.services.alias_registry import AliasRegistry
from app.services.query_expansion_service import QueryExpansionConfig, QueryExpansionService
from app.services.vector_search_service import VectorSearchService

from app.api.routes.aliases import router as aliases_router
from app.api.routes.health import router as health_router
from app.api.routes.rag import router as rag_router

logger = logging.getLogger("app.api.main")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 1. Load immutable alias registry
    alias_registry = AliasRegistry.load(
        settings.ALIAS_DATASET_PATH,
        expected_sha256=settings.ALIAS_DATASET_EXPECTED_SHA256 or None,
        strict_validation=settings.ALIAS_DATASET_STRICT_VALIDATION,
    )
    alias_status = alias_registry.get_status()
    logger.info(
        "Alias dataset loaded file=%s path=%s sha256=%s approved_strong_groups=%s "
        "approved_story_scoped_groups=%s generatable_members=%s normalization_only_members=%s warnings=%s",
        alias_status.file_name,
        alias_registry.snapshot.source_file_path,
        alias_status.sha256,
        alias_status.approved_strong_group_count,
        alias_status.approved_story_scoped_group_count,
        alias_status.generatable_member_count,
        alias_status.normalization_only_member_count,
        alias_status.validation_warning_count,
    )

    query_expansion_service = QueryExpansionService(
        alias_registry=alias_registry,
        config=QueryExpansionConfig.from_settings(settings),
    )

    # 2. Warm up embedding provider
    provider = MiniLMProvider()
    provider.encode("Sherlock Holmes")

    # 3. Verify database connection
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()

    # 4. Instantiate client and services
    groq_client = GroqGptOssClient(settings)
    search_service = VectorSearchService(provider)

    rag_service = RagAnswerService(
        search_service=search_service,
        groq_client=groq_client,
    )

    # 5. Save to app state
    app.state.alias_registry = alias_registry
    app.state.query_expansion_service = query_expansion_service
    app.state.rag_service = rag_service
    app.state.embedding_provider = provider
    app.state.ready = True

    try:
        yield
    finally:
        # 6. Clean up resources
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
    app.include_router(aliases_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(rag_router, prefix="/api")

    return app


app = create_app()
