import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException

from app.schemas.rag_api import RagAnswerRequest, RagAnswerApiResponse
from app.services.rag_answer_service import RagAnswerService, InvalidRagResponseError
from app.clients.groq_gpt_oss_client import GroqApiError
from app.core.exceptions import (
    InvalidRagRequestError,
    DocumentNotFoundError,
    RetrievalUnavailableError,
)
from app.api.dependencies import get_rag_service

logger = logging.getLogger("app.api.routes.rag")
router = APIRouter(prefix="/rag", tags=["rag"])

@router.post("/answer", response_model=RagAnswerApiResponse)
def answer_question(
    payload: RagAnswerRequest,
    rag_service: RagAnswerService = Depends(get_rag_service),
) -> RagAnswerApiResponse:
    request_id = uuid.uuid4()
    
    try:
        # Generate answer using synchronous flow
        response = rag_service.generate_answer(
            question=payload.question,
            document_id=payload.document_id,
            top_k=payload.top_k,
        )
    except InvalidRagRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RetrievalUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except InvalidRagResponseError as exc:
        raise HTTPException(status_code=502, detail=f"Bad Gateway (Invalid RAG Response): {exc}")
    except GroqApiError as exc:
        exc_str = str(exc).lower()
        if "timeout" in exc_str:
            raise HTTPException(status_code=504, detail=f"Gateway Timeout (Groq Timeout): {exc}")
        elif "429" in exc_str or "rate limit" in exc_str:
            raise HTTPException(status_code=429, detail=f"Too Many Requests (Groq Rate Limit): {exc}")
        else:
            raise HTTPException(status_code=502, detail=f"Bad Gateway (Groq API Error): {exc}")
    except Exception as exc:
        # Do not leak stack trace
        logger.exception("Unexpected error occurred while generating RAG answer.")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RagAnswerApiResponse(
        request_id=request_id,
        question=response.question,
        document_id=response.document_id,
        retrieval=response.retrieval,
        generation=response.generation
    )
