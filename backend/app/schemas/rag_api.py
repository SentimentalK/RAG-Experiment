from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.schemas.rag_answer import RagAnswerResponse

class RagAnswerRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )
    document_id: str = Field(
        default="gutenberg-1661",
        min_length=1,
        max_length=100,
    )
    top_k: Literal[10] = 10

    @field_validator("question", "document_id")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value


class RagAnswerApiResponse(RagAnswerResponse):
    request_id: UUID
