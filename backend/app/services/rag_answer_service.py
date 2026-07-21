import logging

from app.clients.groq_gpt_oss_client import GroqGptOssClient
from app.services.answer_generation_service import (
    AnswerGenerationService,
    InvalidRagResponseError,
    contexts_from_retrieval_results,
)
from app.services.vector_search_service import VectorSearchService
from app.schemas.rag_answer import (
    RagAnswerResponse,
    RetrievalInfo,
    RetrievalResult,
    GenerationInfo,
)

logger = logging.getLogger("rag_answer_service")

class RagAnswerService:
    """
    Orchestrates the entire RAG pipeline: retrieval, prompt building,
    Groq completion request, parsing, citation checks, and error retry logic.
    """
    def __init__(self, search_service: VectorSearchService, groq_client: GroqGptOssClient) -> None:
        self._search_service = search_service
        self._groq_client = groq_client
        self._answer_generation_service = AnswerGenerationService(groq_client)

    def generate_answer(
        self,
        question: str,
        document_id: str = "gutenberg-1661",
        top_k: int = 10
    ) -> RagAnswerResponse:
        """
        Executes search, builds prompt, requests and validates structured output with one correction retry.
        """
        # 1. Vector Search
        search_res = self._search_service.search(question, document_id=document_id, top_k=top_k)
        retrieved_results = search_res.get("results", [])
        
        retrieval_meta = {
            "model_name": search_res["model_name"],
            "top_k": top_k,
            "embedding_duration_ms": search_res["embedding_duration_ms"],
            "database_duration_ms": search_res["database_duration_ms"]
        }

        return self._generate_answer_common(
            question=question,
            retrieved_results=retrieved_results,
            document_id=document_id,
            retrieval_meta=retrieval_meta
        )

    def generate_answer_from_context(
        self,
        question: str,
        retrieved_chunks: list[dict],
        document_id: str,
        retrieval_meta: dict
    ) -> RagAnswerResponse:
        """
        Generates answer bypassing the database search, directly using pre-retrieved context chunks.
        """
        return self._generate_answer_common(
            question=question,
            retrieved_results=retrieved_chunks,
            document_id=document_id,
            retrieval_meta=retrieval_meta
        )

    def _generate_answer_common(
        self,
        question: str,
        retrieved_results: list[dict],
        document_id: str,
        retrieval_meta: dict
    ) -> RagAnswerResponse:
        """
        Common execution path for RAG generation, validation, and correction retry.
        """
        top_k = retrieval_meta["top_k"]
        generated = self._answer_generation_service.generate(
            question=question,
            contexts=contexts_from_retrieval_results(retrieved_results),
        )

        gen_info = GenerationInfo(
            model_name=generated.model_name,
            answer=generated.answer_text,
            evidence_sufficient=generated.evidence_sufficient,
            citations=list(generated.citations),
            confidence=generated.confidence,
            generation_duration_ms=generated.generation_duration_ms,
            attempt_count=generated.attempt_count,
            usage=generated.usage
        )

        # Map search results to RetrievalInfo
        mapped_results = []
        for r in retrieved_results:
            mapped_results.append(
                RetrievalResult(
                    rank=r["rank"],
                    chunk_uid=r["chunk_uid"],
                    section_order=r["section_order"],
                    section_title=r["section_title"],
                    chunk_order=r["chunk_order"],
                    token_count=r["token_count"],
                    chunk_text=r["chunk_text"],
                    cosine_distance=r["cosine_distance"],
                    cosine_similarity=r["cosine_similarity"]
                )
            )

        ret_info = RetrievalInfo(
            model_name=retrieval_meta["model_name"],
            top_k=top_k,
            embedding_duration_ms=retrieval_meta["embedding_duration_ms"],
            database_duration_ms=retrieval_meta["database_duration_ms"],
            results=mapped_results
        )

        return RagAnswerResponse(
            question=question,
            document_id=document_id,
            retrieval=ret_info,
            generation=gen_info
        )

    def _settings_model_name(self) -> str:
        return getattr(self._groq_client._settings, "GROQ_MODEL", "openai/gpt-oss-120b")
