import pytest
import json
import shutil
from pathlib import Path
from app.evaluation.evaluation_builder import EvaluationBuilder
from app.cli.build_baseline_evaluation import main as cli_main

# ---------------- Mock structures ----------------

@pytest.fixture
def base_dir(tmp_path) -> Path:
    return tmp_path

@pytest.fixture
def mock_document_path(base_dir) -> Path:
    path = base_dir / "document.json"
    doc_data = {
        "title": "Sherlock Holmes Mock Book",
        "author": "Arthur Conan Doyle",
        "source_name": "Project Gutenberg",
        "source_reference": "1661"
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc_data, f)
    return path

@pytest.fixture
def mock_sections_path(base_dir) -> Path:
    path = base_dir / "sections.jsonl"
    sections = [
        {"section_order": 1, "title": "Sec Title 1", "text": "Story 1 text text. Holmes always remembered Irene Adler as the woman."},
        {"section_order": 2, "title": "Sec Title 2", "text": "Story 2 text text. Red headed league case."}
    ]
    with path.open("w", encoding="utf-8") as f:
        for s in sections:
            f.write(json.dumps(s) + "\n")
    return path

@pytest.fixture
def mock_chunks_path(base_dir) -> Path:
    path = base_dir / "chunks.jsonl"
    # Create 10 chunks to match Top 10 retrieval
    chunks = []
    for i in range(1, 11):
        sec = 1 if i <= 5 else 2
        title = "Sec Title 1" if i <= 5 else "Sec Title 2"
        chunks.append({
            "chunk_id": f"c-1-{i}",
            "section_order": sec,
            "section_title": title,
            "chunk_order": i,
            "token_count": 10,
            "overlap_tokens": 0,
            "text": f"Chunk {i} text content."
        })
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    return path

@pytest.fixture
def mock_questions_config() -> dict:
    return {
        "experiment_id": "test-baseline-experiment-v1",
        "document_id": "gutenberg-1661",
        "retrieval_method": "minilm_exact_cosine",
        "top_k": 10,
        "questions": [
            {
                "question_id": "q001",
                "category": "alias",
                "question": "Who was \"the woman\" whom Sherlock Holmes always remembered?"
            }
        ]
    }

@pytest.fixture
def mock_retrieval_results() -> dict:
    return {
        "generation_id": "gen1234567890",
        "experiment_id": "test-baseline-experiment-v1",
        "document_id": "gutenberg-1661",
        "retrieval_method": "exact_cosine",
        "top_k": 10,
        "results": [
            {
                "question_id": "q001",
                "category": "alias",
                "question": "Who was \"the woman\" whom Sherlock Holmes always remembered?",
                "query_token_count": 12,
                "embedding_duration_ms": 1.5,
                "database_duration_ms": 2.5,
                "candidate_story_orders": [1, 2],
                "retrieved_chunks": [
                    {
                        "rank": i,
                        "chunk_uid": f"c-1-{i}",
                        "section_order": 1 if i <= 5 else 2,
                        "section_title": "Sec Title 1" if i <= 5 else "Sec Title 2",
                        "chunk_order": i,
                        "token_count": 10,
                        "cosine_distance": 0.05 * i,
                        "cosine_similarity": 1.0 - (0.05 * i),
                        "chunk_text": f"Chunk {i} text content."
                    }
                    for i in range(1, 11)
                ]
            }
        ]
    }

@pytest.fixture
def mock_judgments(base_dir) -> dict:
    judgments_data = {
        "schema_version": "1.0",
        "question_id": "q001",
        "question": "Who was \"the woman\" whom Sherlock Holmes always remembered?",
        "question_interpretation": "Identify Irene Adler",
        "reference_answer": "Irene Adler",
        "confidence": 1.0,
        "overall_assessment": {
            "retrieval_quality": "excellent",
            "score_0_to_100": 90,
            "summary": "Perfect."
        },
        "top_k_sufficiency": {
            "top_1": True,
            "top_3": True,
            "top_5": True,
            "top_10": True
        },
        "first_direct_evidence_rank": 1,
        "candidate_story_judgments": [
            {"section_order": 1, "section_title": "Sec Title 1", "label": "directly_relevant", "reason": "Reason 1"},
            {"section_order": 2, "section_title": "Sec Title 2", "label": "irrelevant", "reason": "Reason 2"}
        ],
        "retrieved_chunk_judgments": [
            {
                "rank": i,
                "chunk_uid": f"c-1-{i}",
                "label": "direct_evidence" if i == 1 else "irrelevant",
                "supports_answer": True if i == 1 else False,
                "reason": f"Rank {i} reason"
            }
            for i in range(1, 11)
        ],
        "missing_evidence_within_candidate_stories": [
            {
                "section_order": 1,
                "section_title": "Sec Title 1",
                "evidence_quote": "Holmes always remembered Irene Adler",
                "reason": "Proof name"
            }
        ]
    }
    
    # Write to judgments folder
    j_dir = base_dir / "judgments"
    j_dir.mkdir(exist_ok=True)
    with (j_dir / "q001.json").open("w", encoding="utf-8") as f:
        json.dump(judgments_data, f)
        
    return {"q001": judgments_data}

# ----------------- Unit tests -----------------

def test_evaluation_builder_successful_run(
    mock_document_path, mock_sections_path, mock_chunks_path,
    mock_questions_config, mock_retrieval_results, mock_judgments
):
    """
    Verifies that build_evaluation successfully parses data sources,
    merges chunk judgments, sorts sections/ranks, and returns consolidated JSON structure.
    """
    payload = EvaluationBuilder.build_evaluation(
        document_path=mock_document_path,
        sections_path=mock_sections_path,
        chunks_path=mock_chunks_path,
        questions_config=mock_questions_config,
        retrieval_results=mock_retrieval_results,
        judgments=mock_judgments
    )

    # 1. Verification of top-level keys
    assert payload["schema_version"] == "1.0"
    assert payload["experiment"]["experiment_id"] == "test-baseline-experiment-v1"
    assert len(payload["stories"]) == 2
    assert payload["document"]["title"] == "Sherlock Holmes Mock Book"
    
    # Verify chunks array
    assert "chunks" in payload
    assert len(payload["chunks"]) == 10
    assert payload["chunks"][0]["chunk_uid"] == "c-1-1"
    assert payload["chunks"][0]["chunk_text"] == "Chunk 1 text content."
    
    # 2. Verification of computed and merged metrics
    questions = payload["questions"]
    assert len(questions) == 1
    q001_payload = questions[0]
    assert q001_payload["question_id"] == "q001"
    assert q001_payload["computed_metrics"]["first_direct_evidence_rank"] == 1
    assert q001_payload["computed_metrics"]["direct_hit_at_1"] == 1
    assert q001_payload["computed_metrics"]["reciprocal_rank"] == 1.0

    # 3. Verification of merged retrieved chunk judgments
    retrieved = q001_payload["retrieved_chunks"]
    assert len(retrieved) == 10
    assert retrieved[0]["rank"] == 1
    assert retrieved[0]["judgment"]["label"] == "direct_evidence"
    assert retrieved[0]["judgment"]["supports_answer"] is True
    assert retrieved[0]["judgment"]["reason"] == "Rank 1 reason"
    
    # 4. Verification of subjective assessment keys
    assert q001_payload["judge_assessment"]["score_0_to_100"] == 90
    assert q001_payload["judge_assessment"]["retrieval_quality"] == "excellent"

def test_evaluation_builder_pipeline_consistency_failure(
    mock_document_path, mock_sections_path, mock_chunks_path,
    mock_questions_config, mock_retrieval_results, mock_judgments, base_dir
):
    """
    Verifies that validation throws error if reports file chunk count contradicts actual chunks count.
    """
    # Write a mock content ingestion report with chunk count mismatch (999 vs actual 10)
    report_path = base_dir / "content_ingestion_report.json"
    report_data = {
        "section_count": 2,
        "chunk_count": 999  # mismatch!
    }
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report_data, f)

    with pytest.raises(ValueError, match="content_ingestion_report chunk_count=999.*but chunks.jsonl contains 10"):
        EvaluationBuilder.build_evaluation(
            document_path=mock_document_path,
            sections_path=mock_sections_path,
            chunks_path=mock_chunks_path,
            questions_config=mock_questions_config,
            retrieval_results=mock_retrieval_results,
            judgments=mock_judgments,
            content_ingestion_report_path=report_path
        )
