import pytest
from app.evaluation.judgment_validator import JudgmentValidator, normalize_quote_characters, normalize_evidence_text

# ---------------- Mock configurations ----------------

@pytest.fixture
def mock_questions_config() -> dict:
    return {
        "experiment_id": "test-exp",
        "document_id": "doc-1",
        "top_k": 10,
        "questions": [
            {
                "question_id": "q001",
                "category": "alias",
                "question": "Who was \"the woman\" whom Sherlock Holmes always remembered?"
            },
            {
                "question_id": "q002",
                "category": "causal",
                "question": "Why was Jabez Wilson paid well?"
            }
        ]
    }

@pytest.fixture
def mock_retrieval_results() -> dict:
    return {
        "results": [
            {
                "question_id": "q001",
                "candidate_story_orders": [1, 2],
                "retrieved_chunks": [
                    {
                        "rank": i,
                        "chunk_uid": f"c-1-{i}",
                        "section_order": 1 if i <= 5 else 2,
                        "section_title": "Story Title 1" if i <= 5 else "Story Title 2",
                        "chunk_order": i,
                        "token_count": 10,
                        "cosine_distance": 0.1 * i,
                        "cosine_similarity": 1.0 - (0.1 * i),
                        "chunk_text": f"Chunk {i} text content."
                    }
                    for i in range(1, 11)
                ]
            }
        ]
    }

@pytest.fixture
def mock_sections_by_order() -> dict:
    return {
        1: {
            "section_order": 1,
            "title": "Story Title 1",
            "text": "This is the complete text of story one. Holmes always remembered Irene Adler as the woman."
        },
        2: {
            "section_order": 2,
            "title": "Story Title 2",
            "text": "This is the complete text of story two. Holmes solved the mystery of the Red-Headed League."
        }
    }

@pytest.fixture
def valid_judgment_data() -> dict:
    return {
        "schema_version": "1.0",
        "question_id": "q001",
        "question": "Who was \"the woman\" whom Sherlock Holmes always remembered?",
        "question_interpretation": "Who is the woman?",
        "reference_answer": "Irene Adler",
        "confidence": 1.0,
        "overall_assessment": {
            "retrieval_quality": "excellent",
            "score_0_to_100": 95,
            "summary": "Everything was accurate."
        },
        "top_k_sufficiency": {
            "top_1": True,
            "top_3": True,
            "top_5": True,
            "top_10": True
        },
        "first_direct_evidence_rank": 1,
        "candidate_story_judgments": [
            {
                "section_order": 1,
                "section_title": "Story Title 1",
                "label": "directly_relevant",
                "reason": "Direct reference to Adler."
            },
            {
                "section_order": 2,
                "section_title": "Story Title 2",
                "label": "irrelevant",
                "reason": "Red headed league case."
            }
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
                "section_title": "Story Title 1",
                "evidence_quote": "Holmes always remembered Irene Adler",
                "reason": "Proof of the woman's name."
            }
        ]
    }

@pytest.fixture
def validator(mock_questions_config, mock_retrieval_results, mock_sections_by_order) -> JudgmentValidator:
    return JudgmentValidator(mock_questions_config, mock_retrieval_results, mock_sections_by_order)

# ----------------- Unit tests -----------------

def test_normalization_functions():
    # Quote normalization NFKC
    assert normalize_quote_characters("“woman”") == '"woman"'
    assert normalize_quote_characters("‘woman’") == "'woman'"
    
    # Evidence text normalization: folding quote and spaces
    text = "  Holmes   always  remembered \n Irene Adler.  "
    assert normalize_evidence_text(text) == "Holmes always remembered Irene Adler."

def test_valid_judgment_passes(validator, valid_judgment_data):
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert res.is_valid
    assert not res.errors
    assert not res.warnings
    assert not corrections

def test_missing_schema_keys(validator, valid_judgment_data):
    del valid_judgment_data["schema_version"]
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("Missing required top-level schema keys" in e.message for e in res.errors)

def test_filename_qid_mismatch(validator, valid_judgment_data):
    res, corrections = validator.validate_single(valid_judgment_data, "q002") # Filename q002, field question_id is q001
    assert not res.is_valid
    assert any("does not match JSON field question_id" in e.message for e in res.errors)

def test_canonical_question_match_and_quote_correction(validator, valid_judgment_data):
    # Change straight double quotes to straight single quotes (fixable error)
    valid_judgment_data["question"] = "Who was 'the woman' whom Sherlock Holmes always remembered?"
    
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert res.is_valid
    assert len(corrections) == 1
    assert corrections[0]["type"] == "quote_style_correction"
    assert corrections[0]["original_value"] == "Who was 'the woman' whom Sherlock Holmes always remembered?"
    assert corrections[0]["corrected_value"] == "Who was \"the woman\" whom Sherlock Holmes always remembered?"
    
    # Assert judgment question was updated in place
    assert valid_judgment_data["question"] == "Who was \"the woman\" whom Sherlock Holmes always remembered?"
    # Assert a warning was logged
    assert len(res.warnings) == 1
    assert "Quote style mismatch corrected" in res.warnings[0].message

def test_canonical_question_unfixable_mismatch(validator, valid_judgment_data):
    # Change words
    valid_judgment_data["question"] = "Who did Sherlock Holmes remember as the woman?"
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("does not match the canonical question text" in e.message for e in res.errors)

def test_chunk_ranks_broken_sequence(validator, valid_judgment_data):
    # Make rank 3 into rank 2 (duplicate rank 2, missing rank 3)
    valid_judgment_data["retrieved_chunk_judgments"][2]["rank"] = 2
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("Duplicate rank 2" in e.message for e in res.errors)
    assert any("Missing rank 3" in e.message for e in res.errors)

def test_chunk_uid_mismatch(validator, valid_judgment_data):
    # Corrupt chunk_uid at rank 4
    valid_judgment_data["retrieved_chunk_judgments"][3]["chunk_uid"] = "corrupted-id"
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("Chunk UID mismatch at Rank 4" in e.message for e in res.errors)

def test_candidate_stories_missing(validator, valid_judgment_data):
    # Candidate stories for q001 are sections 1 and 2, let's delete section 2
    valid_judgment_data["candidate_story_judgments"].pop()
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("Candidate stories mismatch" in e.message for e in res.errors)

def test_label_supports_answer_mismatch(validator, valid_judgment_data):
    # Set label as irrelevant but supports_answer = True
    valid_judgment_data["retrieved_chunk_judgments"][1]["label"] = "irrelevant"
    valid_judgment_data["retrieved_chunk_judgments"][1]["supports_answer"] = True
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("supports_answer must be false for chunk at Rank 2 with label 'irrelevant'" in e.message for e in res.errors)

def test_first_direct_evidence_rank_mismatch(validator, valid_judgment_data):
    # Compute first direct evidence rank is 1 (since Rank 1 is direct_evidence)
    # Let's set it to 3 in judgment config
    valid_judgment_data["first_direct_evidence_rank"] = 3
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("first_direct_evidence_rank mismatch" in e.message for e in res.errors)

def test_sufficiency_monotonicity_violation(validator, valid_judgment_data):
    # top_1 is True, top_3 is False
    valid_judgment_data["top_k_sufficiency"]["top_3"] = False
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("top_k_sufficiency monotonicity violated" in e.message for e in res.errors)

def test_missing_evidence_quote_not_found(validator, valid_judgment_data):
    # Evidence quote not found in story
    valid_judgment_data["missing_evidence_within_candidate_stories"][0]["evidence_quote"] = "Sherlock Holmes wore a modern baseball hat"
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert not res.is_valid
    assert any("evidence_quote for section 1 not found in story source text" in e.message for e in res.errors)

def test_out_of_order_warnings(validator, valid_judgment_data):
    # Swap elements in retrieved_chunk_judgments array to trigger out of order warning
    chunks = valid_judgment_data["retrieved_chunk_judgments"]
    chunks[0], chunks[1] = chunks[1], chunks[0]
    
    res, corrections = validator.validate_single(valid_judgment_data, "q001")
    assert res.is_valid
    assert len(res.warnings) == 1
    assert "retrieved_chunk_judgments array is not sorted by rank 1-10" in res.warnings[0].message
