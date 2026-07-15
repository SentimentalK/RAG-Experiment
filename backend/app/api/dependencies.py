from fastapi import Request
from app.services.rag_answer_service import RagAnswerService

def get_rag_service(request: Request) -> RagAnswerService:
    service = getattr(request.app.state, "rag_service", None)
    if service is None:
        raise RuntimeError("RAG service is not initialized.")
    return service
