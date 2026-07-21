import json

from app.clients.groq_gpt_oss_client import GroqApiError
from app.services.answer_generation_service import AnswerContext, AnswerGenerationService
import app.services.answer_generation_service as answer_generation_module
from app.services.rag_prompt_builder import RagPromptBuilder


def test_answer_generation_uses_existing_prompt_builder_and_hashes_are_prompt_visible_only():
    client = FakeGroqClient()
    service = AnswerGenerationService(client)
    contexts = (
        AnswerContext(
            chunk_uid="chunk-1",
            rank=1,
            chunk_text="Holmes saw the evidence.",
            section_title="A Story",
            cosine_similarity=0.75,
            document_id="doc",
        ),
    )

    answer = service.generate("What happened?", contexts)

    messages = client.calls[0]
    expected = RagPromptBuilder.build_messages(
        "What happened?",
        [
            {
                "rank": 1,
                "chunk_uid": "chunk-1",
                "section_title": "A Story",
                "cosine_similarity": 0.75,
                "chunk_text": "Holmes saw the evidence.",
            }
        ],
    )
    assert messages == expected
    rendered_hash = answer.rendered_prompt_sha256
    context_hash = answer.context_snapshot_sha256

    changed_ui_only = (
        AnswerContext(
            chunk_uid="chunk-1",
            rank=1,
            chunk_text="Holmes saw the evidence.",
            section_title="A Story",
            cosine_similarity=0.75,
            document_id="different-ui-only",
        ),
    )
    answer_same_prompt = service.generate("What happened?", changed_ui_only)
    assert answer_same_prompt.context_snapshot_sha256 == context_hash
    assert answer_same_prompt.rendered_prompt_sha256 == rendered_hash

    changed_prompt_text = (
        AnswerContext(
            chunk_uid="chunk-1",
            rank=1,
            chunk_text="Different text.",
            section_title="A Story",
            cosine_similarity=0.75,
        ),
    )
    answer_changed = service.generate("What happened?", changed_prompt_text)
    assert answer_changed.context_snapshot_sha256 != context_hash
    assert answer_changed.rendered_prompt_sha256 != rendered_hash


def test_answer_generation_prompt_excludes_experiment_metadata():
    client = FakeGroqClient()
    service = AnswerGenerationService(client)

    service.generate(
        "Why?",
        (
            AnswerContext(
                chunk_uid="chunk-1",
                rank=1,
                chunk_text="Plain source text.",
                section_title="Section",
                cosine_similarity=0.1,
            ),
        ),
    )

    prompt = json.dumps(client.calls[0])
    assert "strong_story" not in prompt
    assert "alias group" not in prompt.casefold()
    assert "variant" not in prompt.casefold()
    assert "fusion" not in prompt.casefold()
    assert "gold evidence" not in prompt.casefold()


def test_answer_generation_retries_groq_rate_limit(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(answer_generation_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    client = FakeGroqClient(fail_first_with_rate_limit=True)
    service = AnswerGenerationService(client)

    answer = service.generate(
        "What happened?",
        (
            AnswerContext(
                chunk_uid="chunk-1",
                rank=1,
                chunk_text="Holmes saw the evidence.",
                section_title="A Story",
                cosine_similarity=0.75,
            ),
        ),
    )

    assert answer.answer_text == "Supported answer."
    assert len(client.calls) == 2
    assert sleep_calls == [0.75]


class FakeGroqClient:
    def __init__(self, *, fail_first_with_rate_limit=False):
        self.calls = []
        self.fail_first_with_rate_limit = fail_first_with_rate_limit
        self._settings = type("Settings", (), {"GROQ_MODEL": "test-model"})()

    def chat_completion(self, messages):
        self.calls.append(messages)
        if self.fail_first_with_rate_limit and len(self.calls) == 1:
            raise GroqApiError(
                'Groq API returned error status 429: {"error":{"message":"Rate limit reached. Please try again in 0.5s","code":"rate_limit_exceeded"}}'
            )
        return {
            "content": json.dumps(
                {
                    "answer": "Supported answer.",
                    "evidence_sufficient": True,
                    "citations": [{"chunk_uid": "chunk-1", "reason": "It says so."}],
                    "confidence": 0.9,
                }
            ),
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
