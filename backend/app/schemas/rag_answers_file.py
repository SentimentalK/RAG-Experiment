from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from app.schemas.rag_answer import Citation, TokenUsage

class RagAnswersContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_k: int
    chunk_uids: list[str]


class RagAnswersGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    answer: str
    evidence_sufficient: bool
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
    generation_duration_ms: float
    attempt_count: int
    usage: TokenUsage


class RagAnswerItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    context: RagAnswersContext
    generation: RagAnswersGeneration


class RagAnswersFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    generation_model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    retrieval_results_sha256: str = Field(min_length=1)
    question_count: int
    answers: list[RagAnswerItem]
