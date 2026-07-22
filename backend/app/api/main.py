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
from app.services.answer_generation_service import AnswerGenerationService
from app.services.expanded_retrieval_service import ExpandedRetrievalConfig, ExpandedRetrievalService
from app.services.experimental_answer_service import ExperimentalAnswerConfig, ExperimentalAnswerService
from app.services.query_expansion_service import QueryExpansionConfig, QueryExpansionService
from app.services.vector_search_service import VectorSearchService
from app.repositories.experiment_repository import ExperimentRepository

from app.api.routes.aliases import router as aliases_router
from app.api.routes.experiments import router as experiments_router
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
        curation_path=settings.ALIAS_CURATION_PATH,
        curation_required=settings.ALIAS_CURATION_REQUIRED,
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
    logger.info(
        "Alias curation loaded loaded=%s file=%s sha256=%s version=%s explicit_records=%s "
        "showcase_groups=%s reviewed_high=%s reviewed_low=%s pending_groups=%s",
        alias_status.curation_loaded,
        alias_status.curation_file_name,
        alias_status.curation_sha256,
        alias_status.curation_version,
        alias_status.explicit_curation_record_count,
        alias_status.showcase_group_count,
        alias_status.high_value_group_count,
        alias_status.low_value_group_count,
        alias_status.pending_group_count,
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
    answer_generation_service = AnswerGenerationService(groq_client)
    expanded_retrieval_service = ExpandedRetrievalService(
        alias_registry=alias_registry,
        query_expansion_service=query_expansion_service,
        vector_search_service=search_service,
        config=ExpandedRetrievalConfig.from_settings(settings),
    )
    experiment_repository = ExperimentRepository()
    experimental_answer_service = ExperimentalAnswerService(
        alias_registry=alias_registry,
        expanded_retrieval_service=expanded_retrieval_service,
        answer_generation_service=answer_generation_service,
        experiment_repository=experiment_repository,
        config=ExperimentalAnswerConfig.from_settings(settings),
    )

    rag_service = RagAnswerService(
        search_service=search_service,
        groq_client=groq_client,
    )

    # 5. Save to app state
    app.state.alias_registry = alias_registry
    app.state.query_expansion_service = query_expansion_service
    app.state.expanded_retrieval_service = expanded_retrieval_service
    app.state.answer_generation_service = answer_generation_service
    app.state.experiment_repository = experiment_repository
    app.state.experimental_answer_service = experimental_answer_service
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
    app.include_router(experiments_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(rag_router, prefix="/api")

    return app


app = create_app()
