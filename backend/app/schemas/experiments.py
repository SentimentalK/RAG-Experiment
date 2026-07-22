from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.rag_answer import Citation
from app.services.query_expansion_service import QueryExpansionRequestOptions


RetrievalMode = Literal["baseline", "strong_only", "strong_story"]
SessionStatus = Literal["running", "completed", "partial", "failed"]
ModeRunStatus = Literal["pending", "running", "retrieval_completed", "completed", "failed"]
VariantExecutionStatus = Literal["generated", "searched", "skipped", "failed"]


class ExperimentPersistenceCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    required: bool


class ExperimentExpansionCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    max_query_variants: int
    allow_story_scoped: bool
    allow_story_scoped_single_token: bool


class ExperimentCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    available_modes: tuple[RetrievalMode, ...]
    persistence: ExperimentPersistenceCapabilities
    expansion: ExperimentExpansionCapabilities
    trace_persistence_enabled: bool
    evaluation_catalog_available: bool = False
    admin_auth_required: bool = True


class ExperimentAdminVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret: str = ""


class ExperimentAdminVerifyResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    authenticated: bool


class ExperimentDeleteSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    deleted: bool
    session_id: UUID


class ExperimentVariantStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    variant_index: int
    variant_kind: str
    status: VariantExecutionStatus
    error_code: str | None = None
    error_message: str | None = None


class ExperimentalAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    mode: RetrievalMode = "strong_story"
    document_id: str = Field(default="gutenberg-1661", min_length=1, max_length=100)
    expansion_options: QueryExpansionRequestOptions | None = None
    persist: bool = True
    include_trace: bool = False

    @field_validator("query", "document_id")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value


class ExperimentCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    modes: tuple[RetrievalMode, ...] = ("baseline", "strong_only", "strong_story")
    document_id: str = Field(default="gutenberg-1661", min_length=1, max_length=100)
    expansion_options: QueryExpansionRequestOptions | None = None
    persist: bool = True
    include_trace: bool = False

    @field_validator("query", "document_id")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value

    @field_validator("modes")
    @classmethod
    def unique_modes(cls, value: tuple[RetrievalMode, ...]) -> tuple[RetrievalMode, ...]:
        if not value:
            raise ValueError("At least one mode is required.")
        if len(value) != len(set(value)):
            raise ValueError("Modes must not be duplicated.")
        if len(value) > 3:
            raise ValueError("At most three modes are supported.")
        return value


class ExperimentContextRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank: int
    chunk_uid: str
    section_title: str
    chunk_text: str | None = None
    raw_similarity: float | None = None
    raw_distance: float | None = None
    document_id: str | None = None
    section_id: str | None = None
    section_order: int | None = None
    chunk_index: int | None = None
    chunk_order: int | None = None
    token_count: int | None = None
    alias_only_candidate: bool = False


class ExperimentRetrievalSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    retrieval_reason: str | None = None
    generated_variant_count: int
    vector_search_call_count: int
    final_context_count: int
    retrieval_executed: bool
    retrieval_source_mode: RetrievalMode | None = None
    retrieval_reused: bool = False
    variant_statuses: tuple[ExperimentVariantStatus, ...] = ()


class ExperimentTiming(BaseModel):
    model_config = ConfigDict(frozen=True)

    retrieval_duration_ms: float | None = None
    generation_duration_ms: float | None = None
    total_duration_ms: float | None = None


class ExperimentModeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: RetrievalMode
    mode_run_id: UUID | None
    status: ModeRunStatus
    answer: str | None
    evidence_sufficient: bool | None = None
    citations: tuple[Citation, ...] = ()
    confidence: float | None = None
    contexts: tuple[ExperimentContextRecord, ...]
    context_chunk_uids: tuple[str, ...]
    context_snapshot_sha256: str | None
    prompt_template_sha256: str | None
    rendered_prompt_sha256: str | None
    retrieval_summary: ExperimentRetrievalSummary
    timing: ExperimentTiming
    trace: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None


class ModeComparisonSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_mode: RetrievalMode
    compared_mode: RetrievalMode
    shared_context_count: int
    new_context_count: int
    displaced_context_count: int
    context_jaccard_at_10: float
    new_chunk_uids: tuple[str, ...]
    displaced_chunk_uids: tuple[str, ...]
    alias_only_context_count: int
    answer_text_equal: bool
    answer_text_normalized_equal: bool
    validation_warnings: tuple[str, ...] = ()


class ExperimentalAnswerResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: UUID | None
    mode_run_id: UUID | None
    persisted: bool
    query: str
    mode: RetrievalMode
    result: ExperimentModeResult
    warnings: tuple[str, ...] = ()


class ExperimentCompareResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: UUID | None
    persisted: bool
    query: str
    status: SessionStatus
    results: dict[RetrievalMode, ExperimentModeResult]
    comparisons: tuple[ModeComparisonSummary, ...]
    requested_mode_count: int
    retrieval_execution_count: int
    answer_generation_count: int
    total_vector_search_call_count: int
    warnings: tuple[str, ...] = ()


class ExperimentSessionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: UUID
    query: str
    requested_modes: tuple[RetrievalMode, ...]
    status: SessionStatus
    started_at: datetime
    completed_at: datetime | None
    requested_mode_count: int
    retrieval_execution_count: int
    answer_generation_count: int
    total_vector_search_call_count: int


class ExperimentSessionDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    session: ExperimentSessionSummary
    modes: tuple[ExperimentModeResult, ...]
    alias_dataset_sha256: str
    corpus_content_sha256: str | None = None
    git_commit: str | None = None
    query_expansion_config: dict[str, Any]
    retrieval_config: dict[str, Any]
    generation_config: dict[str, Any]
