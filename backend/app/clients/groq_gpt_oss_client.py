import httpx
from app.core.config import Settings

class GroqApiError(RuntimeError):
    """Raised when the Groq API returns a non-200 response or encounters a network issue."""
    pass

class GroqGptOssClient:
    MODEL_NAME = "openai/gpt-oss-120b"

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.Client | None = None,
    ) -> None:
        # Check API Key
        if not settings.GROQ_API_KEY.strip():
            raise GroqApiError("GROQ_API_KEY is not configured.")

        self._settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=settings.GROQ_BASE_URL.rstrip("/"),
            timeout=httpx.Timeout(
                connect=10.0,
                read=120.0,
                write=30.0,
                pool=10.0,
            ),
        )

    def chat_completion(self, messages: list[dict]) -> dict:
        """
        Sends chat completion request to Groq with response_format matching the strict JSON schema.
        Returns a dict containing:
          - "response_body": parsed JSON body of the LLM response
          - "duration_ms": float time in ms for the request
          - "usage": dict of tokens usage details
        """
        payload = {
            "model": self._settings.GROQ_MODEL,
            "messages": messages,
            "temperature": 0.0,
            "reasoning_effort": "low",
            "max_completion_tokens": 800,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "rag_answer",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "answer": {
                                "type": "string",
                            },
                            "evidence_sufficient": {
                                "type": "boolean",
                            },
                            "citations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "chunk_uid": {
                                            "type": "string",
                                        },
                                        "reason": {
                                            "type": "string",
                                        },
                                    },
                                    "required": [
                                        "chunk_uid",
                                        "reason",
                                    ],
                                    "additionalProperties": False,
                                },
                            },
                            "confidence": {
                                "type": "number",
                            },
                        },
                        "required": [
                            "answer",
                            "evidence_sufficient",
                            "citations",
                            "confidence",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
        }

        try:
            response = self._client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as e:
            raise GroqApiError(f"Network error during chat completion: {e}") from e

        if response.status_code != 200:
            raise GroqApiError(
                f"Groq API returned error status {response.status_code}: {response.text}"
            )

        try:
            res_json = response.json()
            choice = res_json["choices"][0]
            content = choice["message"]["content"]
            usage = res_json.get("usage", {})
        except (KeyError, ValueError) as e:
            raise GroqApiError(f"Failed to parse Groq API response structure: {e}. Raw response: {response.text}")

        return {
            "content": content,
            "usage": usage
        }

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
