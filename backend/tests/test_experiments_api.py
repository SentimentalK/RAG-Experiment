from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_experimental_answer_service
from app.api.main import app
from app.schemas.experiments import (
    ExperimentCompareResponse,
    ExperimentContextRecord,
    ExperimentModeResult,
    ExperimentRetrievalSummary,
    ExperimentSessionDetail,
    ExperimentSessionSummary,
    ExperimentTiming,
    ExperimentalAnswerResponse,
)
from app.services.experimental_answer_service import ExperimentalAnswerError


def test_experimental_answer_and_compare_api_serialize_compact_results():
    service = MagicMock()
    mode_result = _mode_result()
    service.answer.return_value = ExperimentalAnswerResponse(
        session_id=uuid4(),
        mode_run_id=mode_result.mode_run_id,
        persisted=True,
        query="Question?",
        mode="strong_story",
        result=mode_result,
    )
    service.compare.return_value = ExperimentCompareResponse(
        session_id=uuid4(),
        persisted=True,
        query="Question?",
        status="completed",
        results={"strong_story": mode_result},
        comparisons=(),
        requested_mode_count=1,
        retrieval_execution_count=1,
        answer_generation_count=1,
        total_vector_search_call_count=2,
    )
    app.dependency_overrides[get_experimental_answer_service] = lambda: service
    try:
        client = TestClient(app)
        answer_response = client.post("/api/experiments/answer", json={"query": "Question?", "mode": "strong_story"})
        assert answer_response.status_code == 200
        assert answer_response.json()["result"]["trace"] is None

        compare_response = client.post("/api/experiments/compare", json={"query": "Question?", "modes": ["strong_story"]})
        assert compare_response.status_code == 200
        assert compare_response.json()["retrieval_execution_count"] == 1
    finally:
        app.dependency_overrides.clear()


def test_experiment_read_api_defaults_hide_trace_and_context_text():
    service = MagicMock()
    session_id = uuid4()
    mode_run = _mode_result(chunk_text=None)
    service.list_sessions.return_value = [
        ExperimentSessionSummary(
            session_id=session_id,
            query="Question?",
            requested_modes=("baseline",),
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            requested_mode_count=1,
            retrieval_execution_count=1,
            answer_generation_count=1,
            total_vector_search_call_count=1,
        )
    ]
    service.get_session_detail.return_value = ExperimentSessionDetail(
        session=service.list_sessions.return_value[0],
        modes=(mode_run,),
        alias_dataset_sha256="alias-sha",
        query_expansion_config={},
        retrieval_config={},
        generation_config={},
    )
    service.get_mode_run_detail.return_value = mode_run
    app.dependency_overrides[get_experimental_answer_service] = lambda: service
    try:
        client = TestClient(app)
        list_response = client.get("/api/experiments/sessions")
        assert list_response.status_code == 200
        assert "sessions" in list_response.json()

        detail_response = client.get(f"/api/experiments/sessions/{session_id}")
        assert detail_response.status_code == 200

        mode_response = client.get(f"/api/experiments/mode-runs/{mode_run.mode_run_id}")
        assert mode_response.status_code == 200
        payload = mode_response.json()
        assert payload["trace"] is None
        assert payload["contexts"][0]["chunk_text"] is None
        service.get_mode_run_detail.assert_called_with(mode_run.mode_run_id, include_trace=False, include_context_text=False)
    finally:
        app.dependency_overrides.clear()


def test_experimental_api_errors_are_safe():
    service = MagicMock()
    service.answer.side_effect = ExperimentalAnswerError(
        "answer_generation_failed",
        "Answer generation failed.",
        session_id=uuid4(),
        failed_mode="strong_only",
    )
    app.dependency_overrides[get_experimental_answer_service] = lambda: service
    try:
        client = TestClient(app)
        response = client.post("/api/experiments/answer", json={"query": "Question?", "mode": "strong_only"})
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["error_code"] == "answer_generation_failed"
        assert detail["failed_mode"] == "strong_only"
        assert "Traceback" not in str(detail)
    finally:
        app.dependency_overrides.clear()


def _mode_result(chunk_text="Text"):
    mode_run_id = uuid4()
    return ExperimentModeResult(
        mode="strong_story",
        mode_run_id=mode_run_id,
        status="completed",
        answer="Answer.",
        evidence_sufficient=True,
        confidence=0.9,
        contexts=(
            ExperimentContextRecord(
                rank=1,
                chunk_uid="chunk-1",
                section_title="Section",
                chunk_text=chunk_text,
            ),
        ),
        context_chunk_uids=("chunk-1",),
        context_snapshot_sha256="context-sha",
        prompt_template_sha256="template-sha",
        rendered_prompt_sha256="rendered-sha",
        retrieval_summary=ExperimentRetrievalSummary(
            retrieval_reason="alias_expanded_retrieval",
            generated_variant_count=2,
            vector_search_call_count=2,
            final_context_count=1,
            retrieval_executed=True,
        ),
        timing=ExperimentTiming(retrieval_duration_ms=1.0, generation_duration_ms=2.0, total_duration_ms=3.0),
    )

