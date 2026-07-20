import json
from pathlib import Path

import pytest

from app.experiments.noun_units_v2a import extractor


def test_normalize_surface_and_story_id():
    assert extractor.normalize_surface("  “the   woman’s  photograph”  ") == "the woman's photograph"
    assert extractor.story_id({"section_order": 1, "title": "A Scandal in Bohemia"}) == "s01-a-scandal-in-bohemia"


def test_strip_title_and_stable_uid():
    assert extractor.strip_title(["Mr.", "Jabez", "Wilson"]) == ("Mr.", "Jabez Wilson")
    assert extractor.stable_uid("noun-unit", "proper|jabez wilson") == extractor.stable_uid("noun-unit", "proper|jabez wilson")
    assert extractor.stable_uid("noun-unit", "proper|jabez wilson") != extractor.stable_uid("noun-unit", "proper|irene adler")


def test_merge_span_candidates_combines_sources_without_dropping_nested_spans():
    candidates = [
        {
            "span_start": 10,
            "span_end": 22,
            "surface_text": "Irene Adler",
            "lemma_text": "Irene Adler",
            "source": "proper_noun",
            "entity_type": None,
            "pos_pattern": ["PROPN", "PROPN"],
            "head_text": "Adler",
            "head_lemma": "Adler",
        },
        {
            "span_start": 10,
            "span_end": 22,
            "surface_text": "Irene Adler",
            "lemma_text": "Irene Adler",
            "source": "named_entity",
            "entity_type": "PERSON",
            "pos_pattern": ["PROPN", "PROPN"],
            "head_text": "Adler",
            "head_lemma": "Adler",
        },
        {
            "span_start": 16,
            "span_end": 22,
            "surface_text": "Adler",
            "lemma_text": "Adler",
            "source": "proper_noun",
            "entity_type": None,
            "pos_pattern": ["PROPN"],
            "head_text": "Adler",
            "head_lemma": "Adler",
        },
    ]

    merged = extractor.merge_span_candidates(candidates)

    assert len(merged) == 2
    irene = [item for item in merged if item["surface_text"] == "Irene Adler"][0]
    assert irene["primary_unit_type"] == "named_entity"
    assert irene["extraction_sources"] == ["named_entity", "proper_noun"]
    assert irene["entity_types"] == ["PERSON"]


def test_chunk_interval_mapping_uses_ordered_overlap_and_original_offsets():
    text = "First line about Holmes.\n\nSecond line about Holmes. Third line about Watson."
    sections = [{"section_order": 1, "title": "Mock", "text": text}]
    chunks = [
        {"chunk_id": "g1661-s01-c0001", "section_order": 1, "chunk_order": 1, "text": "First line about Holmes. Second line about Holmes."},
        {"chunk_id": "g1661-s01-c0002", "section_order": 1, "chunk_order": 2, "text": "Second line about Holmes. Third line about Watson."},
    ]

    intervals, failures = extractor.build_chunk_intervals(sections, chunks)

    assert failures == []
    assert [item["chunk_uid"] for item in intervals[1]] == ["g1661-s01-c0001", "g1661-s01-c0002"]
    start = text.index("Second")
    occ = {
        "section_order": 1,
        "span_start": start,
        "span_end": start + len("Second line"),
        "sentence_start": start,
        "sentence_end": start + len("Second line about Holmes."),
    }
    extractor.map_occurrence_to_chunks(occ, intervals)
    assert occ["mapping_status"] == "mapped"
    assert occ["primary_chunk_uid"] == "g1661-s01-c0001"
    assert occ["containing_chunk_uids"] == ["g1661-s01-c0001", "g1661-s01-c0002"]


def test_generic_valid_common_noun_goes_to_review():
    unit = {
        "canonical_text": "woman",
        "unit_type": "common_noun",
        "occurrence_count": 3,
        "pos_patterns": [("NOUN",)],
        "head_noun": "woman",
    }

    classification, reasons, expandable, expandable_reasons = extractor.classify_unit(
        unit,
        {"woman"},
        extractor.default_config(),
    )

    assert classification == "review"
    assert "generic_single_noun" in reasons
    assert expandable == "not_expandable"


def test_baseline_question_coverage_uses_shared_normalized_keys(tmp_path):
    class FakeNlp:
        def __call__(self, text):
            return text

    def fake_extract_candidates(doc):
        if "Sherlock Holmes" in doc:
            return [
                {
                    "span_start": 0,
                    "span_end": 15,
                    "surface_text": "Sherlock Holmes",
                    "lemma_text": "Sherlock Holmes",
                    "source": "proper_noun",
                    "entity_type": None,
                    "pos_pattern": ["PROPN", "PROPN"],
                    "head_text": "Holmes",
                    "head_lemma": "Holmes",
                }
            ]
        return []

    questions_path = tmp_path / "questions.json"
    data = {"questions": [{"question_id": "q001", "question": "Who was Sherlock Holmes?"}]}
    try:
        questions_path.write_text(json.dumps(data), encoding="utf-8")
        original = extractor.extract_candidates
        extractor.extract_candidates = fake_extract_candidates
        rows = extractor.extract_question_units(questions_path, FakeNlp())
    finally:
        extractor.extract_candidates = original

    assert rows[0]["surface_text"] == "Sherlock Holmes"
    assert rows[0]["normalized_key"] == "proper_noun||sherlock holmes"


@pytest.mark.nlp_model
def test_real_spacy_pipeline_smoke():
    nlp = extractor.load_spacy_model("en_core_web_sm")
    doc = nlp("Sherlock Holmes found the blue carbuncle before Jabez Wilson arrived.")
    candidates = extractor.merge_span_candidates(extractor.extract_candidates(doc))
    surfaces = {candidate["surface_text"] for candidate in candidates}

    assert "Sherlock Holmes" in surfaces
    assert "the blue carbuncle" in surfaces
    assert "Jabez Wilson" in surfaces
