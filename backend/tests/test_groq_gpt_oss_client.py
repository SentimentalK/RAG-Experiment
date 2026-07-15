import httpx
import pytest
import json
from app.core.config import Settings
from app.clients.groq_gpt_oss_client import GroqGptOssClient, GroqApiError

@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        GROQ_API_KEY="mock-api-key",
        GROQ_MODEL="mock-model",
        GROQ_BASE_URL="https://mock.groq.com/v1"
    )

def test_missing_api_key():
    bad_settings = Settings(
        GROQ_API_KEY="",
        GROQ_MODEL="mock-model",
        GROQ_BASE_URL="https://mock.groq.com/v1"
    )
    with pytest.raises(GroqApiError, match="GROQ_API_KEY is not configured."):
        GroqGptOssClient(bad_settings)

def test_chat_completions_headers_and_payload(test_settings):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        # Check URL
        assert request.url.path.endswith("/chat/completions")
        assert request.url.host == "mock.groq.com"
        
        # Check Headers
        assert request.headers["Authorization"] == "Bearer mock-api-key"
        assert request.headers["Content-Type"] == "application/json"
        
        # Check Body / Payload
        payload = json.loads(request.read())
        assert payload["model"] == "mock-model"
        assert payload["temperature"] == 0.0
        assert payload["reasoning_effort"] == "low"
        assert payload["max_completion_tokens"] == 800
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        
        # Returns mock response
        mock_res = {
            "choices": [
                {
                    "message": {
                        "content": '{"answer": "Holmes lived in Baker Street.", "evidence_sufficient": true, "citations": [], "confidence": 0.95}'
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120
            }
        }
        return httpx.Response(200, json=mock_res)

    mock_client = httpx.Client(
        transport=httpx.MockTransport(mock_handler),
        base_url="https://mock.groq.com/v1"
    )
    client = GroqGptOssClient(test_settings, http_client=mock_client)
    
    messages = [{"role": "user", "content": "Where did Holmes live?"}]
    res = client.chat_completion(messages)
    
    assert "content" in res
    assert "usage" in res
    assert res["usage"]["prompt_tokens"] == 100
    assert res["usage"]["completion_tokens"] == 20
    assert res["usage"]["total_tokens"] == 120

def test_api_error_responses(test_settings):
    # Test 401 Unauthorized
    def mock_handler_401(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized API Key")

    mock_client_401 = httpx.Client(
        transport=httpx.MockTransport(mock_handler_401),
        base_url="https://mock.groq.com/v1"
    )
    client_401 = GroqGptOssClient(test_settings, http_client=mock_client_401)
    with pytest.raises(GroqApiError, match="Groq API returned error status 401: Unauthorized API Key"):
        client_401.chat_completion([])

    # Test 429 Rate Limit
    def mock_handler_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate Limit Exceeded")

    mock_client_429 = httpx.Client(
        transport=httpx.MockTransport(mock_handler_429),
        base_url="https://mock.groq.com/v1"
    )
    client_429 = GroqGptOssClient(test_settings, http_client=mock_client_429)
    with pytest.raises(GroqApiError, match="Groq API returned error status 429: Rate Limit Exceeded"):
        client_429.chat_completion([])
