import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from app.evaluation.evaluation_builder import EvaluationBuilder

@pytest.fixture
def base_questions_config() -> dict:
    return {
        "experiment_id": "minilm-exact-baseline-v1",
        "document_id": "gutenberg-1661",
        "top_k": 10,
        "questions": [
            {"question_id": f"q{i:03d}", "question": f"Question {i}", "category": "test"}
            for i in range(1, 9)
        ]
    }

@pytest.fixture
def base_retrieval_results() -> dict:
    return {
        "generation_id": "mock_gen_id",
        "results": [
            {
                "question_id": f"q{i:03d}",
                "question": f"Question {i}",
                "query_token_count": 5,
                "embedding_duration_ms": 1.0,
                "database_duration_ms": 2.0,
                "candidate_story_orders": [1],
                "retrieved_chunks": [
                    {
                        "rank": r,
                        "chunk_uid": f"chunk-{i}-{r}",
                        "section_order": 1,
                        "section_title": "Story Section 1",
                        "chunk_order": r,
                        "token_count": 10,
                        "cosine_distance": 0.1,
                        "cosine_similarity": 0.9,
                        "chunk_text": f"Chunk text {i} {r}"
                    }
                    for r in range(1, 11)
                ]
            }
            for i in range(1, 9)
        ]
    }

@pytest.fixture
def base_judgments() -> dict:
    return {
        f"q{i:03d}": {
            "question_id": f"q{i:03d}",
            "question_interpretation": "test",
            "reference_answer": "test",
            "overall_assessment": {"retrieval_quality": "good", "score_0_to_100": 90, "summary": "test"},
            "confidence": 1.0,
            "first_direct_evidence_rank": 1,
            "top_k_sufficiency": {"top_1": True, "top_3": True, "top_5": True, "top_10": True},
            "candidate_story_judgments": [{"section_order": 1, "section_title": "Story Section 1", "label": "directly_relevant", "reason": "test"}],
            "retrieved_chunk_judgments": [
                {"rank": r, "chunk_uid": f"chunk-{i}-{r}", "label": "direct_evidence", "supports_answer": True, "reason": "test"}
                for r in range(1, 11)
            ],
            "missing_evidence_within_candidate_stories": []
        }
        for i in range(1, 9)
    }

@pytest.fixture
def base_rag_answers() -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "minilm-exact-baseline-v1",
        "generation_id": "rag_gen_id",
        "generated_at": "2026-07-15T00:00:00Z",
        "generation_model": "openai/gpt-oss-120b",
        "prompt_version": "rag-grounded-v1",
        "retrieval_results_sha256": "mock_retrieval_sha",
        "question_count": 8,
        "answers": [
            {
                "question_id": f"q{i:03d}",
                "question": f"Question {i}",
                "context": {
                    "top_k": 10,
                    "chunk_uids": [f"chunk-{i}-{r}" for r in range(1, 11)]
                },
                "generation": {
                    "model_name": "openai/gpt-oss-120b",
                    "answer": f"RAG Answer {i}",
                    "evidence_sufficient": True,
                    "citations": [{"chunk_uid": f"chunk-{i}-1", "reason": "test"}],
                    "confidence": 0.95,
                    "generation_duration_ms": 100.0,
                    "attempt_count": 1,
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}
                }
            }
            for i in range(1, 9)
        ]
    }

def test_evaluation_builder_without_rag_answers(
    base_questions_config, base_retrieval_results, base_judgments
):
    with tempfile.TemporaryDirectory() as tmp_dir:
        dir_path = Path(tmp_dir)
        doc_path = dir_path / "document.json"
        sec_path = dir_path / "sections.jsonl"
        chk_path = dir_path / "chunks.jsonl"

        with doc_path.open("w") as f:
            json.dump({"title": "Mock Book", "author": "Arthur"}, f)

        # Write sections
        with sec_path.open("w") as f:
            f.write(json.dumps({"section_order": 1, "title": "Story Section 1", "text": "Content"}) + "\n")

        # Write 80 chunks to match all questions retrieval results
        with chk_path.open("w") as f:
            for i in range(1, 9):
                for r in range(1, 11):
                    f.write(json.dumps({
                        "chunk_id": f"chunk-{i}-{r}",
                        "section_order": 1,
                        "section_title": "Story Section 1",
                        "chunk_order": r,
                        "token_count": 10,
                        "text": f"Chunk text {i} {r}"
                    }) + "\n")

        payload = EvaluationBuilder.build_evaluation(
            document_path=doc_path,
            sections_path=sec_path,
            chunks_path=chk_path,
            questions_config=base_questions_config,
            retrieval_results=base_retrieval_results,
            judgments=base_judgments,
            rag_answers=None
        )

        assert "questions" in payload
        assert len(payload["questions"]) == 8
        for q in payload["questions"]:
            assert q["rag_answer"] is None

        # Check steps: should not contain rag_generation
        step_ids = [step["step_id"] for step in payload["pipeline"]["steps"]]
        assert "rag_generation" not in step_ids

def test_evaluation_builder_with_valid_rag_answers(
    base_questions_config, base_retrieval_results, base_judgments, base_rag_answers
):
    with tempfile.TemporaryDirectory() as tmp_dir:
        dir_path = Path(tmp_dir)
        doc_path = dir_path / "document.json"
        sec_path = dir_path / "sections.jsonl"
        chk_path = dir_path / "chunks.jsonl"

        with doc_path.open("w") as f:
            json.dump({"title": "Mock Book", "author": "Arthur"}, f)

        with sec_path.open("w") as f:
            f.write(json.dumps({"section_order": 1, "title": "Story Section 1", "text": "Content"}) + "\n")

        with chk_path.open("w") as f:
            for i in range(1, 9):
                for r in range(1, 11):
                    f.write(json.dumps({
                        "chunk_id": f"chunk-{i}-{r}",
                        "section_order": 1,
                        "section_title": "Story Section 1",
                        "chunk_order": r,
                        "token_count": 10,
                        "text": f"Chunk text {i} {r}"
                    }) + "\n")

        payload = EvaluationBuilder.build_evaluation(
            document_path=doc_path,
            sections_path=sec_path,
            chunks_path=chk_path,
            questions_config=base_questions_config,
            retrieval_results=base_retrieval_results,
            judgments=base_judgments,
            rag_answers=base_rag_answers,
            retrieval_results_sha256="mock_retrieval_sha"
        )

        assert "questions" in payload
        assert len(payload["questions"]) == 8
        for idx, q in enumerate(payload["questions"], start=1):
            assert q["rag_answer"] is not None
            assert q["rag_answer"]["answer"] == f"RAG Answer {idx}"
            assert q["rag_answer"]["evidence_sufficient"] is True
            assert q["rag_answer"]["confidence"] == 0.95
            assert len(q["rag_answer"]["citations"]) == 1
            assert q["rag_answer"]["citations"][0]["chunk_uid"] == f"chunk-{idx}-1"

        # Check steps: should contain rag_generation
        step_ids = [step["step_id"] for step in payload["pipeline"]["steps"]]
        assert "rag_generation" in step_ids
        rag_step = [s for s in payload["pipeline"]["steps"] if s["step_id"] == "rag_generation"][0]
        assert rag_step["model"] == "openai/gpt-oss-120b"
        assert rag_step["question_count"] == 8

def test_evaluation_builder_invalid_rag_hash_mismatch(
    base_questions_config, base_retrieval_results, base_judgments, base_rag_answers
):
    with tempfile.TemporaryDirectory() as tmp_dir:
        dir_path = Path(tmp_dir)
        doc_path = dir_path / "document.json"
        sec_path = dir_path / "sections.jsonl"
        chk_path = dir_path / "chunks.jsonl"

        with doc_path.open("w") as f:
            json.dump({"title": "Mock Book", "author": "Arthur"}, f)
        with sec_path.open("w") as f:
            f.write(json.dumps({"section_order": 1, "title": "Story Section 1", "text": "Content"}) + "\n")
        with chk_path.open("w") as f:
            for i in range(1, 9):
                for r in range(1, 11):
                    f.write(json.dumps({
                        "chunk_id": f"chunk-{i}-{r}",
                        "section_order": 1,
                        "section_title": "Story Section 1",
                        "chunk_order": r,
                        "token_count": 10,
                        "text": f"Chunk text {i} {r}"
                    }) + "\n")

        with pytest.raises(ValueError, match="RAG answers file SHA-256 signature mismatch"):
            EvaluationBuilder.build_evaluation(
                document_path=doc_path,
                sections_path=sec_path,
                chunks_path=chk_path,
                questions_config=base_questions_config,
                retrieval_results=base_retrieval_results,
                judgments=base_judgments,
                rag_answers=base_rag_answers,
                retrieval_results_sha256="mismatch_retrieval_sha"
            )

def test_evaluation_builder_invalid_chunks_mismatch(
    base_questions_config, base_retrieval_results, base_judgments, base_rag_answers
):
    # Modify context chunk_uids in base_rag_answers to mismatch retrieved chunks
    base_rag_answers["answers"][0]["context"]["chunk_uids"] = [f"mismatch-{r}" for r in range(1, 11)]

    with tempfile.TemporaryDirectory() as tmp_dir:
        dir_path = Path(tmp_dir)
        doc_path = dir_path / "document.json"
        sec_path = dir_path / "sections.jsonl"
        chk_path = dir_path / "chunks.jsonl"

        with doc_path.open("w") as f:
            json.dump({"title": "Mock Book", "author": "Arthur"}, f)
        with sec_path.open("w") as f:
            f.write(json.dumps({"section_order": 1, "title": "Story Section 1", "text": "Content"}) + "\n")
        with chk_path.open("w") as f:
            for i in range(1, 9):
                for r in range(1, 11):
                    f.write(json.dumps({
                        "chunk_id": f"chunk-{i}-{r}",
                        "section_order": 1,
                        "section_title": "Story Section 1",
                        "chunk_order": r,
                        "token_count": 10,
                        "text": f"Chunk text {i} {r}"
                    }) + "\n")

        with pytest.raises(ValueError, match="RAG answer context chunks mismatch for 'q001'"):
            EvaluationBuilder.build_evaluation(
                document_path=doc_path,
                sections_path=sec_path,
                chunks_path=chk_path,
                questions_config=base_questions_config,
                retrieval_results=base_retrieval_results,
                judgments=base_judgments,
                rag_answers=base_rag_answers,
                retrieval_results_sha256="mock_retrieval_sha"
            )
