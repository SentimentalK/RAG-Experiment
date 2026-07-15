import pytest
import json
import shutil
from pathlib import Path
from app.cli.prepare_baseline_packets import prepare_baseline_packets

# ----------------- Fakes for testing -----------------

class FakeProvider:
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name

class FakeVectorSearchService:
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2", raise_error_on_qid=None):
        self.search_call_count = 0
        self._provider = FakeProvider(model_name)
        self.raise_error_on_qid = raise_error_on_qid

    def search(self, question, document_id, top_k=10):
        self.search_call_count += 1
        
        # Simulates error for testing failure cleanup
        if self.raise_error_on_qid and f"q00{self.search_call_count}" == self.raise_error_on_qid:
            raise RuntimeError(f"Simulated search error for question index {self.search_call_count}")

        results = []
        for i in range(1, 11):
            dist = 0.05 * i
            sim = 1.0 - dist
            # Alternating stories 1 and 2
            sec_order = 1 if i % 2 == 1 else 2
            sec_title = "Sec Title 1" if sec_order == 1 else "Sec Title 2"
            results.append({
                "rank": i,
                "chunk_uid": f"chunk-q{self.search_call_count}-{i}",
                "section_order": sec_order,
                "section_title": sec_title,
                "chunk_order": i,
                "token_count": 10,
                "cosine_distance": dist,
                "cosine_similarity": sim,
                "chunk_text": f"Fake chunk text for Q{self.search_call_count} rank {i}."
            })
        return {
            "question": question,
            "document_id": document_id,
            "model_name": self._provider.model_name,
            "search_mode": "exact_cosine",
            "query_token_count": 5,
            "query_dimensions": 384,
            "query_vector_norm": 1.0,
            "embedding_duration_ms": 1.0,
            "database_duration_ms": 2.0,
            "top_k": top_k,
            "available_chunk_count": 10,
            "available_embedding_count": 10,
            "results": results
        }

# ----------------- Fixtures for mock files -----------------

@pytest.fixture
def base_dir(tmp_path) -> Path:
    return tmp_path

@pytest.fixture
def mock_questions_path(base_dir) -> Path:
    path = base_dir / "questions.json"
    questions_data = {
        "experiment_id": "test-baseline-experiment-v1",
        "document_id": "test-doc-id",
        "retrieval_method": "minilm_exact_cosine",
        "top_k": 10,
        "questions": [
            {"question_id": f"q00{i}", "category": f"cat_{i}", "question": f"Question text {i}?"}
            for i in range(1, 9)
        ]
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(questions_data, f)
    return path

@pytest.fixture
def mock_sections_path(base_dir) -> Path:
    path = base_dir / "sections.jsonl"
    sections = [
        {"section_order": 1, "title": "Sec Title 1", "text": "This is complete text for story one."},
        {"section_order": 2, "title": "Sec Title 2", "text": "This is complete text for story two."}
    ]
    with path.open("w", encoding="utf-8") as f:
        for s in sections:
            f.write(json.dumps(s) + "\n")
    return path

@pytest.fixture
def mock_prompt_path(base_dir) -> Path:
    path = base_dir / "judge_prompt.md"
    path.write_text("Mock evaluation instruction and JSON schema here.")
    return path

@pytest.fixture
def results_output_path(base_dir) -> Path:
    return base_dir / "results" / "retrieval_results.json"

@pytest.fixture
def packets_output_dir(base_dir) -> Path:
    return base_dir / "results" / "packets"

# ----------------- Unit tests -----------------

def test_questions_file_validation_missing_fields(
    mock_questions_path, mock_sections_path, results_output_path, mock_prompt_path, packets_output_dir
):
    """
    Verifies that questions.json configuration with missing experiment_id or document_id is rejected.
    """
    # 1. Clear experiment_id
    with mock_questions_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data["experiment_id"] = ""
    with mock_questions_path.open("w", encoding="utf-8") as f:
        json.dump(data, f)
        
    service = FakeVectorSearchService()
    with pytest.raises(ValueError, match="'experiment_id' cannot be empty"):
        prepare_baseline_packets(
            mock_questions_path, mock_sections_path, results_output_path, mock_prompt_path, packets_output_dir, service
        )

def test_questions_file_validation_duplicate_ids(
    mock_questions_path, mock_sections_path, results_output_path, mock_prompt_path, packets_output_dir
):
    """
    Verifies that duplicate question IDs in configuration are rejected.
    """
    with mock_questions_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Make q002 duplicate of q001
    data["questions"][1]["question_id"] = "q001"
    with mock_questions_path.open("w", encoding="utf-8") as f:
        json.dump(data, f)
        
    service = FakeVectorSearchService()
    with pytest.raises(ValueError, match="Duplicate 'question_id' found"):
        prepare_baseline_packets(
            mock_questions_path, mock_sections_path, results_output_path, mock_prompt_path, packets_output_dir, service
        )

def test_questions_file_validation_incorrect_count(
    mock_questions_path, mock_sections_path, results_output_path, mock_prompt_path, packets_output_dir
):
    """
    Verifies that configurations not having exactly 8 questions are rejected.
    """
    with mock_questions_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Remove last question
    data["questions"].pop()
    with mock_questions_path.open("w", encoding="utf-8") as f:
        json.dump(data, f)
        
    service = FakeVectorSearchService()
    with pytest.raises(ValueError, match="must have exactly 8 questions"):
        prepare_baseline_packets(
            mock_questions_path, mock_sections_path, results_output_path, mock_prompt_path, packets_output_dir, service
        )

def test_prepare_baseline_packets_successful_run(
    mock_questions_path, mock_sections_path, results_output_path, mock_prompt_path, packets_output_dir
):
    """
    Verifies that the entire packet generation process runs successfully with correct mappings,
    unique generation IDs, and structured candidate stories.
    """
    service = FakeVectorSearchService()
    
    stats = prepare_baseline_packets(
        mock_questions_path,
        mock_sections_path,
        results_output_path,
        mock_prompt_path,
        packets_output_dir,
        service
    )

    # 1. Assert service call statistics
    assert service.search_call_count == 8
    assert stats["question_count"] == 8
    assert stats["output_json"].exists()
    assert stats["output_packets_dir"].exists()

    # 2. Verify retrieval_results.json contents
    with stats["output_json"].open("r", encoding="utf-8") as f:
        res_data = json.load(f)
    
    assert "generation_id" in res_data
    assert len(res_data["generation_id"]) == 32
    assert res_data["experiment_id"] == "test-baseline-experiment-v1"
    assert res_data["document_id"] == "test-doc-id"
    assert len(res_data["results"]) == 8
    
    # 3. Verify packets output contents
    for idx in range(1, 9):
        md_file = stats["output_packets_dir"] / f"q00{idx}.md"
        assert md_file.exists()
        
        md_text = md_file.read_text(encoding="utf-8")
        # Assert generation ID exists
        assert f"- Generation ID: {res_data['generation_id']}" in md_text
        # Assert question exists
        assert f"Question text {idx}?" in md_text
        # Assert structured retrieved chunk tags exist
        assert f'<retrieved_chunk rank="1" chunk_uid="chunk-q{idx}-1" section_order="1" section_title="Sec Title 1">' in md_text
        assert "</retrieved_chunk>" in md_text
        
        # Assert complete candidate stories tags exist and occur exactly once
        assert '<candidate_story section_order="1" section_title="Sec Title 1">' in md_text
        assert md_text.count('<candidate_story section_order="1"') == 1
        assert "This is complete text for story one." in md_text
        
        # Assert judge prompt content exists
        assert "Mock evaluation instruction and JSON schema here." in md_text

def test_staging_failure_protection_keeps_original_files(
    mock_questions_path, mock_sections_path, results_output_path, mock_prompt_path, packets_output_dir
):
    """
    Verifies that if one search fails midway, no new outputs are written,
    old files are intact, and staging folder is deleted.
    """
    # 1. Precreate a dummy retrieval_results.json to represent "old" run results
    results_output_path.parent.mkdir(parents=True, exist_ok=True)
    results_output_path.write_text("ORIGINAL CONTENT", encoding="utf-8")

    # 2. Inject a service that will raise error on question index 5 (q005)
    failing_service = FakeVectorSearchService(raise_error_on_qid="q005")

    with pytest.raises(RuntimeError, match="Simulated search error for question index 5"):
        prepare_baseline_packets(
            mock_questions_path,
            mock_sections_path,
            results_output_path,
            mock_prompt_path,
            packets_output_dir,
            failing_service
        )

    # 3. Assert original results output file was NOT overwritten or deleted
    assert results_output_path.exists()
    assert results_output_path.read_text(encoding="utf-8") == "ORIGINAL CONTENT"

    # 4. Assert staging folder was cleaned up
    staging_dir = results_output_path.parent / ".staging"
    assert not staging_dir.exists()
