from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_uid: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RagModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    evidence_sufficient: bool
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GenerationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    answer: str
    evidence_sufficient: bool
    citations: list[Citation]
    confidence: float
    generation_duration_ms: float
    attempt_count: int
    usage: Optional[TokenUsage] = None


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    chunk_uid: str
    section_order: int
    section_title: str
    chunk_order: int
    token_count: int
    chunk_text: str
    cosine_distance: float
    cosine_similarity: float


class RetrievalInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    top_k: int
    embedding_duration_ms: float
    database_duration_ms: float
    results: list[RetrievalResult]


class RagAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    document_id: str
    retrieval: RetrievalInfo
    generation: GenerationInfo
