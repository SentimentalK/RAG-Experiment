import hashlib
import json
import logging
import re
import time
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.clients.groq_gpt_oss_client import GroqApiError, GroqGptOssClient
from app.schemas.rag_answer import Citation, RagModelOutput, TokenUsage
from app.services.rag_prompt_builder import RagPromptBuilder


logger = logging.getLogger("app.services.answer_generation")


class InvalidRagResponseError(RuntimeError):
    """Raised when the LLM response is structurally invalid after retries."""


class AnswerContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_uid: str
    rank: int
    chunk_text: str
    section_title: str
    cosine_similarity: float = 0.0
    cosine_distance: float | None = None
    document_id: str | None = None
    section_id: str | None = None
    section_order: int | None = None
    chunk_index: int | None = None
    chunk_order: int | None = None
    token_count: int | None = None


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer_text: str
    evidence_sufficient: bool
    citations: tuple[Citation, ...]
    confidence: float
    model_name: str
    provider: str
    prompt_template_sha256: str
    rendered_prompt_sha256: str
    context_snapshot_sha256: str
    prompt_context_snapshot: tuple[dict[str, Any], ...]
    context_records: tuple[dict[str, Any], ...]
    input_token_count: int | None
    output_token_count: int | None
    generation_duration_ms: float
    attempt_count: int
    usage: TokenUsage
    raw_provider_request_id: str | None = None
    generation_config: dict[str, Any]


class AnswerGenerationService:
    def __init__(self, groq_client: GroqGptOssClient) -> None:
        self._groq_client = groq_client

    def generate(self, question: str, contexts: tuple[AnswerContext, ...]) -> GeneratedAnswer:
        _validate_context_ranks(contexts)
        prompt_chunks = [_prompt_chunk(context) for context in contexts]
        messages = RagPromptBuilder.build_messages(question, prompt_chunks)
        prompt_template_sha256 = _prompt_template_sha256()
        rendered_prompt_sha256 = _json_sha256(messages)
        prompt_context_snapshot = tuple(_prompt_snapshot_item(item) for item in prompt_chunks)
        context_snapshot_sha256 = _json_sha256(prompt_context_snapshot)
        context_records = tuple(_context_record(context) for context in contexts)
        allowed_chunk_uids = {context.chunk_uid for context in contexts}

        attempt_count = 0
        max_attempts = 2
        max_api_attempts_per_validation_attempt = 3
        last_duration_ms = 0.0

        while attempt_count < max_attempts:
            attempt_count += 1
            start_time = perf_counter()
            response = None
            for api_attempt in range(1, max_api_attempts_per_validation_attempt + 1):
                try:
                    response = self._groq_client.chat_completion(messages)
                    break
                except GroqApiError as exc:
                    retry_after = _groq_retry_after_seconds(str(exc))
                    if retry_after is None or api_attempt == max_api_attempts_per_validation_attempt:
                        logger.exception("Groq API error during answer generation attempt=%s api_attempt=%s", attempt_count, api_attempt)
                        raise
                    logger.warning(
                        "Groq rate limit during answer generation attempt=%s api_attempt=%s retry_after_seconds=%.2f",
                        attempt_count,
                        api_attempt,
                        retry_after,
                    )
                    time.sleep(retry_after)
            assert response is not None
            last_duration_ms = (perf_counter() - start_time) * 1000
            content = response.get("content", "")
            usage_data = response.get("usage", {})

            validation_errors: list[str] = []
            model_output: RagModelOutput | None = None
            try:
                model_output = RagModelOutput.model_validate(json.loads(content))
            except (json.JSONDecodeError, Exception) as exc:
                validation_errors.append(f"Response did not match JSON output schema: {exc}")

            if model_output is not None:
                validation_errors.extend(_validate_model_output(model_output, allowed_chunk_uids))

            if validation_errors:
                message = "; ".join(validation_errors)
                logger.warning("RAG validation failed on attempt=%s: %s", attempt_count, message)
                if attempt_count < max_attempts:
                    messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was invalid for the following reasons:\n"
                                f"{chr(10).join(f'- {err}' for err in validation_errors)}\n\n"
                                "Return a corrected response.\n\n"
                                "Allowed chunk IDs:\n"
                                f"{chr(10).join(f'- {uid}' for uid in allowed_chunk_uids)}"
                            ),
                        }
                    )
                    continue
                raise InvalidRagResponseError(
                    f"Failed to generate valid RAG answer after {max_attempts} attempts. Errors: {message}"
                )

            assert model_output is not None
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
            return GeneratedAnswer(
                answer_text=model_output.answer,
                evidence_sufficient=model_output.evidence_sufficient,
                citations=tuple(model_output.citations),
                confidence=model_output.confidence,
                model_name=self._settings_model_name(),
                provider="groq",
                prompt_template_sha256=prompt_template_sha256,
                rendered_prompt_sha256=rendered_prompt_sha256,
                context_snapshot_sha256=context_snapshot_sha256,
                prompt_context_snapshot=prompt_context_snapshot,
                context_records=context_records,
                input_token_count=usage.prompt_tokens,
                output_token_count=usage.completion_tokens,
                generation_duration_ms=last_duration_ms,
                attempt_count=attempt_count,
                usage=usage,
                raw_provider_request_id=response.get("request_id"),
                generation_config=self.generation_config(),
            )

        raise InvalidRagResponseError("Failed to generate a valid RAG answer.")

    def generation_config(self) -> dict[str, Any]:
        return {
            "model": self._settings_model_name(),
            "temperature": 0.0,
            "reasoning_effort": "low",
            "max_completion_tokens": 800,
            "response_format": "json_schema:rag_answer",
        }

    def prompt_template_sha256(self) -> str:
        return _prompt_template_sha256()

    def _settings_model_name(self) -> str:
        return getattr(self._groq_client._settings, "GROQ_MODEL", "openai/gpt-oss-120b")


def contexts_from_retrieval_results(results: list[dict[str, Any]]) -> tuple[AnswerContext, ...]:
    return tuple(
        AnswerContext(
            chunk_uid=item["chunk_uid"],
            rank=item["rank"],
            chunk_text=item["chunk_text"],
            section_title=item["section_title"],
            cosine_similarity=item.get("cosine_similarity", 0.0),
            cosine_distance=item.get("cosine_distance"),
            document_id=item.get("document_id"),
            section_id=item.get("section_id"),
            section_order=item.get("section_order"),
            chunk_index=item.get("chunk_index", item.get("chunk_order")),
            chunk_order=item.get("chunk_order"),
            token_count=item.get("token_count"),
        )
        for item in results
    )


def _validate_context_ranks(contexts: tuple[AnswerContext, ...]) -> None:
    expected = list(range(1, len(contexts) + 1))
    actual = [context.rank for context in contexts]
    if actual != expected:
        raise RuntimeError(f"Expected ranks {expected}, got {actual}.")


def _prompt_chunk(context: AnswerContext) -> dict[str, Any]:
    return {
        "rank": context.rank,
        "chunk_uid": context.chunk_uid,
        "section_title": context.section_title,
        "cosine_similarity": context.cosine_similarity,
        "chunk_text": context.chunk_text,
    }


def _prompt_snapshot_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": item["rank"],
        "chunk_uid": item["chunk_uid"],
        "section_title": item["section_title"],
        "cosine_similarity": item.get("cosine_similarity", 0.0),
        "chunk_text": item["chunk_text"],
    }


def _context_record(context: AnswerContext) -> dict[str, Any]:
    return {
        "rank": context.rank,
        "chunk_uid": context.chunk_uid,
        "chunk_text": context.chunk_text,
        "section_title": context.section_title,
        "raw_similarity": context.cosine_similarity,
        "raw_distance": context.cosine_distance,
        "document_id": context.document_id,
        "section_id": context.section_id,
        "section_order": context.section_order,
        "chunk_index": context.chunk_index,
        "chunk_order": context.chunk_order,
        "token_count": context.token_count,
    }


def _validate_model_output(model_output: RagModelOutput, allowed_chunk_uids: set[str]) -> list[str]:
    errors: list[str] = []
    if not model_output.answer.strip():
        errors.append("Answer field cannot be empty.")
    cited_uids: list[str] = []
    for idx, citation in enumerate(model_output.citations):
        if not citation.chunk_uid.strip():
            errors.append(f"Citation index {idx} has empty chunk_uid.")
            continue
        if not citation.reason.strip():
            errors.append(f"Citation index {idx} ({citation.chunk_uid}) has empty reason.")
        if citation.chunk_uid not in allowed_chunk_uids:
            errors.append(f"Citation {citation.chunk_uid} is not one of the allowed chunks.")
        cited_uids.append(citation.chunk_uid)
    if len(cited_uids) != len(set(cited_uids)):
        errors.append("Duplicate citations found for the same chunk_uid.")
    if model_output.evidence_sufficient and not model_output.citations:
        errors.append("evidence_sufficient is true but no citations were provided.")
    return errors


def _groq_retry_after_seconds(message: str) -> float | None:
    if "status 429" not in message and "rate_limit" not in message:
        return None
    match = re.search(r"try again in ([0-9]+(?:\.[0-9]+)?)s", message, flags=re.IGNORECASE)
    if match:
        return min(30.0, max(0.5, float(match.group(1)) + 0.25))
    return 2.0


def _prompt_template_sha256() -> str:
    template_payload = {
        "system_prompt": RagPromptBuilder.SYSTEM_PROMPT,
        "chunk_renderer": (
            '<retrieved_chunk rank="{rank}" chunk_uid="{chunk_uid}" '
            'section_title="{section_title}" cosine_similarity="{cosine_similarity}">'
        ),
        "user_prompt": "Question + Retrieved context + Answer instruction",
    }
    return _json_sha256(template_payload)


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalized_answer_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
