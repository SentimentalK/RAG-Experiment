import pytest
import uuid
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.dependencies import get_rag_service
from app.services.rag_answer_service import RagAnswerService, InvalidRagResponseError
from app.clients.groq_gpt_oss_client import GroqApiError
from app.core.exceptions import (
    InvalidRagRequestError,
    DocumentNotFoundError,
    RetrievalUnavailableError,
)
from app.schemas.rag_answer import RagAnswerResponse, RetrievalInfo, GenerationInfo, TokenUsage, Citation

# Mock service to avoid loading the real MiniLM model during tests
@pytest.fixture
def mock_rag_service():
    service = MagicMock(spec=RagAnswerService)
    
    # Setup a dummy response structure
    retrieval_info = RetrievalInfo(
        model_name="mock_emb",
        top_k=10,
        embedding_duration_ms=1.2,
        database_duration_ms=2.3,
        results=[]
    )
    
    generation_info = GenerationInfo(
        model_name="mock_gen",
        answer="Sherlock Holmes was a private investigator.",
        evidence_sufficient=True,
        citations=[Citation(chunk_uid="uid-1", reason="test")],
        confidence=0.99,
        generation_duration_ms=250.0,
        attempt_count=1,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    )
    
    response = RagAnswerResponse(
        question="Who was Sherlock Holmes?",
        document_id="gutenberg-1661",
        retrieval=retrieval_info,
        generation=generation_info
    )
    
    service.generate_answer.return_value = response
    return service

@pytest.fixture
def client(mock_rag_service):
    # Setup dependency override
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    
    # Temporarily force app state ready
    app.state.ready = True
    
    # We use context manager to trigger lifespan but override state in fixture
    with TestClient(app) as test_client:
        yield test_client
        
    app.dependency_overrides.clear()

# ----------------- Health Probe Tests -----------------

def test_liveness_endpoint(client):
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_readiness_endpoint_when_not_ready():
    # Create client without calling lifespan to verify ready flag works
    with TestClient(app) as local_client:
        app.state.ready = False
        response = local_client.get("/api/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"

def test_readiness_endpoint_db_failure(client):
    # Mock connection failure by replacing get_connection with a failure mock
    import app.api.routes.health as health_module
    old_get_conn = health_module.get_connection
    health_module.get_connection = MagicMock(side_effect=Exception("DB Down"))
    
    try:
        response = client.get("/api/health/ready")
        assert response.status_code == 503
        assert "Database connection failed" in response.json()["detail"]
    finally:
        health_module.get_connection = old_get_conn

def test_health_alias(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

# ----------------- Request Validation Tests -----------------

def test_rag_answer_empty_question(client):
    # Empty string should fail pydantic/custom validator
    response = client.post("/api/rag/answer", json={"question": ""})
    assert response.status_code == 422

def test_rag_answer_spaces_question(client):
    # Blank string should fail our strip validator
    response = client.post("/api/rag/answer", json={"question": "    "})
    assert response.status_code == 422

def test_rag_answer_too_long_question(client):
    # More than 2000 chars should fail validation
    long_question = "a" * 2001
    response = client.post("/api/rag/answer", json={"question": long_question})
    assert response.status_code == 422

def test_rag_answer_invalid_top_k(client):
    # top_k must be 10 (Literal)
    response = client.post("/api/rag/answer", json={"question": "Test?", "top_k": 5})
    assert response.status_code == 422

# ----------------- Exception Mappings Tests -----------------

def test_exception_invalid_rag_request(client, mock_rag_service):
    mock_rag_service.generate_answer.side_effect = InvalidRagRequestError("Bad request parameters")
    response = client.post("/api/rag/answer", json={"question": "Test?"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Bad request parameters"

def test_exception_document_not_found(client, mock_rag_service):
    mock_rag_service.generate_answer.side_effect = DocumentNotFoundError("Book not found")
    response = client.post("/api/rag/answer", json={"question": "Test?"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Book not found"

def test_exception_retrieval_unavailable(client, mock_rag_service):
    mock_rag_service.generate_answer.side_effect = RetrievalUnavailableError("Coverage check failed")
    response = client.post("/api/rag/answer", json={"question": "Test?"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Coverage check failed"

def test_exception_invalid_rag_response(client, mock_rag_service):
    mock_rag_service.generate_answer.side_effect = InvalidRagResponseError("Semantic citation failure")
    response = client.post("/api/rag/answer", json={"question": "Test?"})
    assert response.status_code == 502
    assert "Invalid RAG Response" in response.json()["detail"]

def test_exception_groq_api_error(client, mock_rag_service):
    mock_rag_service.generate_answer.side_effect = GroqApiError("Failed connecting to Groq")
    response = client.post("/api/rag/answer", json={"question": "Test?"})
    assert response.status_code == 502
    assert "Groq API Error" in response.json()["detail"]

def test_exception_groq_timeout_error(client, mock_rag_service):
    mock_rag_service.generate_answer.side_effect = GroqApiError("Request timeout on chat endpoint")
    response = client.post("/api/rag/answer", json={"question": "Test?"})
    assert response.status_code == 504
    assert "Groq Timeout" in response.json()["detail"]

def test_exception_groq_rate_limit_error(client, mock_rag_service):
    mock_rag_service.generate_answer.side_effect = GroqApiError("Status 429: rate limit exceeded")
    response = client.post("/api/rag/answer", json={"question": "Test?"})
    assert response.status_code == 429
    assert "Groq Rate Limit" in response.json()["detail"]

def test_exception_internal_server_error(client, mock_rag_service):
    mock_rag_service.generate_answer.side_effect = Exception("Crash!")
    response = client.post("/api/rag/answer", json={"question": "Test?"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal Server Error"

# ----------------- CORS Pre-Flight Options Tests -----------------

def test_cors_headers(client):
    response = client.options(
        "/api/rag/answer",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
