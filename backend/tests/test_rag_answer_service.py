import pytest
import json
from unittest.mock import MagicMock
from app.services.rag_answer_service import RagAnswerService, InvalidRagResponseError
from app.clients.groq_gpt_oss_client import GroqGptOssClient, GroqApiError
from app.services.vector_search_service import VectorSearchService

@pytest.fixture
def mock_search_service() -> MagicMock:
    service = MagicMock(spec=VectorSearchService)
    # Return 10 mocked results
    service.search.return_value = {
        "status": "success",
        "model_name": "mock-embedding-model",
        "embedding_duration_ms": 10.0,
        "database_duration_ms": 5.0,
        "results": [
            {
                "rank": i,
                "chunk_uid": f"chunk-{i}",
                "section_order": 1,
                "section_title": f"Story Section {i}",
                "chunk_order": i,
                "token_count": 200,
                "cosine_distance": 0.1,
                "cosine_similarity": 0.9,
                "chunk_text": f"This is text for chunk {i}."
            }
            for i in range(1, 11)
        ]
    }
    return service

@pytest.fixture
def mock_groq_client() -> MagicMock:
    client = MagicMock(spec=GroqGptOssClient)
    client.MODEL_NAME = "openai/gpt-oss-120b"
    # Settings mock
    settings_mock = MagicMock()
    settings_mock.GROQ_MODEL = "openai/gpt-oss-120b"
    client._settings = settings_mock
    return client

def test_rag_service_success(mock_search_service, mock_groq_client):
    # Valid output
    valid_output = {
        "answer": "Holmes lived at 221B Baker Street.",
        "evidence_sufficient": True,
        "citations": [
            {"chunk_uid": "chunk-1", "reason": "Mentions Baker Street address."}
        ],
        "confidence": 0.98
    }
    mock_groq_client.chat_completion.return_value = {
        "content": json.dumps(valid_output),
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    }

    service = RagAnswerService(mock_search_service, mock_groq_client)
    res = service.generate_answer("Where did Holmes live?")
    
    assert res.question == "Where did Holmes live?"
    assert res.generation.answer == "Holmes lived at 221B Baker Street."
    assert res.generation.evidence_sufficient is True
    assert len(res.generation.citations) == 1
    assert res.generation.citations[0].chunk_uid == "chunk-1"
    assert res.generation.confidence == 0.98
    assert res.generation.attempt_count == 1
    assert res.generation.usage.total_tokens == 120

def test_rag_service_partial_evidence_allowed(mock_search_service, mock_groq_client):
    # evidence_sufficient=False but containing citations is allowed
    partial_output = {
        "answer": "The text mentions a goose, but does not explain how the gem got in.",
        "evidence_sufficient": False,
        "citations": [
            {"chunk_uid": "chunk-3", "reason": "Mentions the goose."}
        ],
        "confidence": 0.75
    }
    mock_groq_client.chat_completion.return_value = {
        "content": json.dumps(partial_output),
        "usage": {}
    }

    service = RagAnswerService(mock_search_service, mock_groq_client)
    res = service.generate_answer("How did the gem get in the goose?")
    
    assert res.generation.evidence_sufficient is False
    assert len(res.generation.citations) == 1
    assert res.generation.citations[0].chunk_uid == "chunk-3"

def test_rag_service_retry_on_invalid_citation_then_success(mock_search_service, mock_groq_client):
    # First response: cites invalid chunk-99
    invalid_output = {
        "answer": "Holmes lived at Baker Street.",
        "evidence_sufficient": True,
        "citations": [
            {"chunk_uid": "chunk-99", "reason": "Invalid chunk id check."}
        ],
        "confidence": 0.90
    }
    # Second response: corrects citation to chunk-1
    valid_output = {
        "answer": "Holmes lived at Baker Street.",
        "evidence_sufficient": True,
        "citations": [
            {"chunk_uid": "chunk-1", "reason": "Valid chunk."}
        ],
        "confidence": 0.95
    }
    
    mock_groq_client.chat_completion.side_effect = [
        {"content": json.dumps(invalid_output), "usage": {}},
        {"content": json.dumps(valid_output), "usage": {}}
    ]

    service = RagAnswerService(mock_search_service, mock_groq_client)
    res = service.generate_answer("Where did Holmes live?")
    
    # attempt_count must be 2
    assert res.generation.attempt_count == 2
    assert res.generation.citations[0].chunk_uid == "chunk-1"
    
    # Verify messages appended for the retry
    # 2 messages are created originally. 2 messages are appended for retry.
    # Total calls to chat_completion = 2
    assert mock_groq_client.chat_completion.call_count == 2
    
    # Inspect the final call parameters: check if retry instructions were sent
    final_messages = mock_groq_client.chat_completion.call_args[0][0]
    assert len(final_messages) == 4
    # The last message should be user message explaining the error
    assert final_messages[2]["role"] == "assistant"
    assert final_messages[3]["role"] == "user"
    assert "Citation chunk-99 is not one of the allowed chunks." in final_messages[3]["content"]
    assert "Allowed chunk IDs:" in final_messages[3]["content"]

def test_rag_service_fails_twice(mock_search_service, mock_groq_client):
    # Both responses are invalid (cites chunk-99)
    bad_output = {
        "answer": "Incorrect answer.",
        "evidence_sufficient": True,
        "citations": [
            {"chunk_uid": "chunk-99", "reason": "Incorrect chunk."}
        ],
        "confidence": 0.80
    }
    mock_groq_client.chat_completion.return_value = {
        "content": json.dumps(bad_output),
        "usage": {}
    }

    service = RagAnswerService(mock_search_service, mock_groq_client)
    with pytest.raises(InvalidRagResponseError, match="Failed to generate valid RAG answer after 2 attempts."):
        service.generate_answer("Where is Baker Street?")

def test_rag_service_fails_sufficient_but_no_citation(mock_search_service, mock_groq_client):
    # evidence_sufficient=True but no citations
    bad_output = {
        "answer": "Baker Street.",
        "evidence_sufficient": True,
        "citations": [],
        "confidence": 0.90
    }
    mock_groq_client.chat_completion.return_value = {
        "content": json.dumps(bad_output),
        "usage": {}
    }

    service = RagAnswerService(mock_search_service, mock_groq_client)
    with pytest.raises(InvalidRagResponseError, match="evidence_sufficient is true but no citations were provided."):
        service.generate_answer("Where is Baker Street?")
