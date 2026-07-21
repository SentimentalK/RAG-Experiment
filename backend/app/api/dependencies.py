from fastapi import Request
from app.services.rag_answer_service import RagAnswerService
from app.services.alias_registry import AliasRegistry
from app.services.query_expansion_service import QueryExpansionService

def get_rag_service(request: Request) -> RagAnswerService:
    service = getattr(request.app.state, "rag_service", None)
    if service is None:
        raise RuntimeError("RAG service is not initialized.")
    return service


def get_alias_registry(request: Request) -> AliasRegistry:
    registry = getattr(request.app.state, "alias_registry", None)
    if registry is None:
        raise RuntimeError("Alias registry is not initialized.")
    return registry


def get_query_expansion_service(request: Request) -> QueryExpansionService:
    service = getattr(request.app.state, "query_expansion_service", None)
    if service is None:
        raise RuntimeError("Query expansion service is not initialized.")
    return service
