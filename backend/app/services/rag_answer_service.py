import json
import logging
from time import perf_counter
from typing import Optional

from app.clients.groq_gpt_oss_client import GroqGptOssClient, GroqApiError
from app.services.vector_search_service import VectorSearchService
from app.services.rag_prompt_builder import RagPromptBuilder
from app.schemas.rag_answer import (
    RagAnswerResponse,
    RetrievalInfo,
    RetrievalResult,
    GenerationInfo,
    TokenUsage,
    RagModelOutput,
    Citation
)

logger = logging.getLogger("rag_answer_service")

class InvalidRagResponseError(RuntimeError):
    """Raised when the LLM response is structurally invalid or fails citation check on final attempt."""
    pass

class RagAnswerService:
    """
    Orchestrates the entire RAG pipeline: retrieval, prompt building,
    Groq completion request, parsing, citation checks, and error retry logic.
    """
    def __init__(self, search_service: VectorSearchService, groq_client: GroqGptOssClient) -> None:
        self._search_service = search_service
        self._groq_client = groq_client

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
        
        # Verify rank sequence 1 to K
        expected_ranks = list(range(1, top_k + 1))
        actual_ranks = [r["rank"] for r in retrieved_results]
        if actual_ranks != expected_ranks:
            raise RuntimeError(f"Expected ranks {expected_ranks}, got {actual_ranks}.")

        retrieved_chunk_ids = {r["chunk_uid"] for r in retrieved_results}

        # 2. Build initial RAG messages
        # Map retrieve results to the expected prompt builder format
        prompt_chunks = []
        for r in retrieved_results:
            prompt_chunks.append({
                "rank": r["rank"],
                "chunk_uid": r["chunk_uid"],
                "section_title": r["section_title"],
                "cosine_similarity": r["cosine_similarity"],
                "chunk_text": r["chunk_text"]
            })

        messages = RagPromptBuilder.build_messages(question, prompt_chunks)

        attempt_count = 0
        max_attempts = 2

        while attempt_count < max_attempts:
            attempt_count += 1
            start_time = perf_counter()
            try:
                # 3. Call Groq
                res = self._groq_client.chat_completion(messages)
            except GroqApiError as e:
                # Do not retry HTTP or network API issues as model output errors
                logger.error(f"Groq API error on attempt {attempt_count}: {e}")
                raise e

            duration_ms = (perf_counter() - start_time) * 1000
            content = res.get("content", "")
            usage_data = res.get("usage", {})

            validation_errors = []
            model_output: Optional[RagModelOutput] = None

            # 4. Parse content
            try:
                # Validate output meets Schema
                parsed_json = json.loads(content)
                model_output = RagModelOutput.model_validate(parsed_json)
            except (json.JSONDecodeError, Exception) as e:
                validation_errors.append(f"Response did not match JSON output schema: {e}")

            # 5. Citation and business rules validation
            if model_output:
                if not model_output.answer.strip():
                    validation_errors.append("Answer field cannot be empty.")

                # Validate citations
                cited_uids = []
                for idx, citation in enumerate(model_output.citations):
                    if not citation.chunk_uid.strip():
                        validation_errors.append(f"Citation index {idx} has empty chunk_uid.")
                        continue
                    if not citation.reason.strip():
                        validation_errors.append(f"Citation index {idx} ({citation.chunk_uid}) has empty reason.")
                    
                    # Must be from the allowed Top K chunk UIDs
                    if citation.chunk_uid not in retrieved_chunk_ids:
                        validation_errors.append(
                            f"Citation {citation.chunk_uid} is not one of the allowed chunks."
                        )
                    cited_uids.append(citation.chunk_uid)

                # No duplicate citations
                if len(cited_uids) != len(set(cited_uids)):
                    validation_errors.append("Duplicate citations found for the same chunk_uid.")

                # If evidence_sufficient = true, must have at least one citation
                if model_output.evidence_sufficient and not model_output.citations:
                    validation_errors.append("evidence_sufficient is true but no citations were provided.")

            # 6. Retry / Error Handling
            if validation_errors:
                err_msg = "; ".join(validation_errors)
                logger.warning(f"RAG validation failed on attempt {attempt_count}: {err_msg}")

                if attempt_count < max_attempts:
                    # Append retry instruction to prompt messages
                    messages.append({"role": "assistant", "content": content})
                    retry_user_content = (
                        "Your previous response was invalid for the following reasons:\n"
                        f"{chr(10).join(f'- {err}' for err in validation_errors)}\n\n"
                        "Return a corrected response.\n\n"
                        "Allowed chunk IDs:\n"
                        f"{chr(10).join(f'- {uid}' for uid in retrieved_chunk_ids)}"
                    )
                    messages.append({"role": "user", "content": retry_user_content})
                    continue
                else:
                    # Final attempt failed
                    raise InvalidRagResponseError(
                        f"Failed to generate valid RAG answer after {max_attempts} attempts. "
                        f"Errors: {err_msg}"
                    )

            # 7. Success! Compile final response object
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            )

            gen_info = GenerationInfo(
                model_name=self._settings_model_name(),
                answer=model_output.answer,
                evidence_sufficient=model_output.evidence_sufficient,
                citations=model_output.citations,
                confidence=model_output.confidence,
                generation_duration_ms=duration_ms,
                attempt_count=attempt_count,
                usage=usage
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
                model_name=search_res["model_name"],
                top_k=top_k,
                embedding_duration_ms=search_res["embedding_duration_ms"],
                database_duration_ms=search_res["database_duration_ms"],
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
