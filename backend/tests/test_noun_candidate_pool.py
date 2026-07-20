import json
from pathlib import Path

from app.experiments.noun_units_v2a.candidates.baseline_coverage import analyze_question_units
from app.experiments.noun_units_v2a.candidates.boundary_filter import default_leading_noise_terms, quality_flags
from app.experiments.noun_units_v2a.candidates.comparison_normalizer import comparison_form, default_orthographic_map, representative_surface
from app.experiments.noun_units_v2a.candidates.consolidator import consolidate_units
from app.experiments.noun_units_v2a.candidates.pipeline import run_candidate_pool
from app.experiments.noun_units_v2a.candidates.tier_classifier import classify_tier
from app.experiments.noun_units_v2a.candidates.writer import sha256_file


def unit(uid, text, unit_type="named_entity", entity_types=None, count=1, story="s01", chunks=None, klass="accepted"):
    return {
        "unit_uid": uid,
        "canonical_text": text,
        "surface_forms": [text],
        "unit_type": unit_type,
        "entity_types": entity_types or [],
        "occurrence_count": count,
        "story_ids": [story],
        "story_count": 1,
        "source_chunk_uids": chunks or ["c1"],
        "example_contexts": [{"occurrence_uid": f"occ-{uid}", "story_id": story, "primary_chunk_uid": (chunks or ["c1"])[0], "source_sentence": f"{text} appeared."}],
        "classification": klass,
        "classification_reasons": [klass],
        "expandability_reasons": ["test"],
        "possessors": [],
    }


def test_comparison_normalization_examples():
    ortho = default_orthographic_map()
    assert comparison_form("Encyclopædia Britannica", ortho)[0] == "encyclopaedia britannica"
    assert comparison_form("Encyclopaedia Britannica", ortho)[0] == "encyclopaedia britannica"
    assert comparison_form("“the speckled band”", ortho)[0] == "the speckled band"
    assert comparison_form(", Mr. Holmes", ortho)[0] == "mr. holmes"
    assert comparison_form("red–headed", ortho)[0] == "red-headed"


def test_consolidation_merges_cross_type_duplicates_but_not_aliases():
    units = [
        unit("u1", "Sherlock Holmes", "named_entity", ["PERSON"], 3),
        unit("u2", "SHERLOCK HOLMES", "named_entity", ["ORG"], 2),
        unit("u3", "Sherlock Holmes", "noun_phrase", [], 4),
        unit("u4", "Holmes", "named_entity", ["PERSON"], 9),
        unit("u5", "Mr. Holmes", "proper_noun", [], 5),
    ]
    candidates, merge_map = consolidate_units(units, set(), set(default_leading_noise_terms()), default_orthographic_map(), {"exclude_generic_single_nouns": True})
    by_form = {c["comparison_form"]: c for c in candidates}

    assert len(by_form["sherlock holmes"]["source_unit_uids"]) == 3
    assert set(by_form["sherlock holmes"]["observed_unit_types"]) == {"named_entity", "noun_phrase"}
    assert set(by_form["sherlock holmes"]["observed_entity_types"]) == {"PERSON", "ORG"}
    assert "holmes" in by_form
    assert "mr. holmes" in by_form
    assert by_form["sherlock holmes"]["candidate_uid"] != by_form["holmes"]["candidate_uid"]


def test_deduplicated_aggregation_uses_unions():
    shared_context = {"occurrence_uid": "same-occ", "story_id": "s01", "primary_chunk_uid": "c1", "source_sentence": "Sherlock Holmes arrived."}
    a = unit("u1", "Sherlock Holmes", "named_entity", ["PERSON"], 10, chunks=["c1", "c2"])
    b = unit("u2", "Sherlock Holmes", "noun_phrase", [], 10, chunks=["c2", "c3"])
    a["example_contexts"] = [shared_context]
    b["example_contexts"] = [shared_context]
    candidates, _ = consolidate_units([a, b], set(), set(), {}, {"exclude_generic_single_nouns": True})
    candidate = candidates[0]

    assert candidate["story_ids"] == ["s01"]
    assert candidate["story_count"] == 1
    assert candidate["source_chunk_uids"] == ["c1", "c2", "c3"]
    assert candidate["source_chunk_count"] == 3
    assert len(candidate["example_contexts"]) == 1


def test_candidate_text_prefers_clean_representative():
    forms = ["And Irene Adler", ", Irene Adler", "IRENE ADLER", "Irene Adler"]
    lookup = {
        "u1": unit("u1", "Irene Adler", "named_entity", ["PERSON"]),
    }
    flags = {"And Irene Adler": {"leading_discourse_marker"}, ", Irene Adler": {"leading_punctuation_removed"}, "IRENE ADLER": set(), "Irene Adler": set()}
    repaired = {", Irene Adler": True}

    assert representative_surface(forms, lookup, flags, repaired) == "Irene Adler"


def test_boundary_filtering_examples():
    generic = {"thing", "woman", "case"}
    noise = set(default_leading_noise_terms())
    assert "suspected_sentence_fragment" in quality_flags("HOLMES,—I", "holmes,—i", generic, noise)
    assert "leading_discourse_marker" in quality_flags("Again Holmes", "again holmes", generic, noise)
    assert "leading_discourse_marker" in quality_flags("And Irene Adler", "and irene adler", generic, noise)
    assert "leading_discourse_marker" in quality_flags("Ah, Watson", "ah, watson", generic, noise)
    assert "currency_expression" in quality_flags("10s", "10s", generic, noise)
    assert "ordinal_expression" in quality_flags("22nd", "22nd", generic, noise)
    assert "isolated_abbreviation" in quality_flags("No", "no", generic, noise)
    assert "pronoun" in quality_flags("I.", "i.", generic, noise)
    assert "address_like" in quality_flags("221B", "221b", generic, noise)
    assert "numeric_expression" not in quality_flags("221B", "221b", generic, noise)
    assert "address_like" in quality_flags("226 Gordon Square", "226 gordon square", generic, noise)
    assert "currency_expression" in quality_flags("4d", "4d", generic, noise)


def test_generic_logic_and_tiering():
    def candidate(text, unit_type, flags=None, count=1, classes=None, possessors=None, possessor_type="none"):
        data = {
            "candidate_text": text,
            "comparison_form": comparison_form(text, {})[0],
            "observed_unit_types": [unit_type],
            "quality_flags": flags or [],
            "occurrence_count": count,
            "possessors": possessors or [],
            "possessor_type": possessor_type,
            "original_v2a_classes": classes or ["accepted"],
            "upstream_rejected_only": (classes or ["accepted"]) == ["rejected"],
        }
        data["token_count"] = len(text.split())
        from app.experiments.noun_units_v2a.candidates.comparison_normalizer import content_tokens
        data["content_tokens"] = content_tokens(text)
        data["content_token_count"] = len(data["content_tokens"])
        return data

    config = {"exclude_generic_single_nouns": True, "tier_a_min_content_tokens": 2, "tier_a_single_name_min_frequency": 2, "tier_b_common_noun_min_frequency": 2, "pronoun_possessive_min_frequency": 2, "max_clean_phrase_tokens": 6, "eligible_tiers": ["tier_a", "tier_b"]}
    assert classify_tier(candidate("Sherlock Holmes", "named_entity"), config)[0] == "tier_a"
    assert classify_tier(candidate("Holmes", "named_entity", count=2), config)[0] == "tier_a"
    assert classify_tier(candidate("Awake", "proper_noun", count=1, classes=["review"]), config)[0] != "tier_a"
    assert classify_tier(candidate("Well", "named_entity", count=1, classes=["rejected"]), config)[0] == "excluded"
    assert classify_tier(candidate("Who", "noun_phrase", ["function_word_only"], classes=["rejected"]), config)[0] == "excluded"
    assert classify_tier(candidate("the blue carbuncle", "noun_phrase", count=1), config)[0] == "tier_a"
    assert classify_tier(candidate("the deadliest snake", "noun_phrase", count=1), config)[0] == "tier_a"
    assert classify_tier(candidate("a bed", "noun_phrase", count=3), config)[0] == "tier_b"
    assert classify_tier(candidate("the morning", "noun_phrase", count=3), config)[0] == "tier_b"
    assert classify_tier(candidate("tunnel", "common_noun", count=2), config)[0] == "tier_b"
    assert classify_tier(candidate("thing", "common_noun", ["generic_single_noun"], count=10), config)[0] == "excluded"
    assert classify_tier(candidate("uncertain malformed phrase", "noun_phrase", ["leading_discourse_marker"]), config)[0] == "review"
    assert classify_tier(candidate("case", "common_noun", ["generic_single_noun"], count=5), config)[0] == "excluded"
    assert classify_tier(candidate("murder case", "noun_phrase", count=1), config)[0] == "tier_a"
    assert classify_tier(candidate("Wilson's shop", "noun_phrase", count=1, possessors=["Wilson"], possessor_type="named"), config)[0] == "tier_a"
    assert classify_tier(candidate("his hand", "noun_phrase", count=3, possessors=["his"], possessor_type="pronoun"), config)[0] == "tier_b"
    assert classify_tier(candidate("my visitor", "noun_phrase", count=1, possessors=["my"], possessor_type="pronoun"), config)[0] == "excluded"
    assert classify_tier(candidate("odd shop", "noun_phrase", count=1, possessors=["?", "his"], possessor_type="mixed"), config)[0] == "review"


def test_baseline_coverage_levels():
    candidates = [
        {"candidate_uid": "nc0", "candidate_text": "Mr. Sherlock Holmes", "comparison_form": "mr. sherlock holmes", "surface_forms": ["Sherlock Holmes"], "tier": "tier_a", "occurrence_count": 1, "embedding_eligible": True},
        {"candidate_uid": "nc1", "candidate_text": "Sherlock Holmes", "comparison_form": "sherlock holmes", "surface_forms": ["Sherlock Holmes"], "tier": "tier_a", "occurrence_count": 1, "embedding_eligible": True},
        {"candidate_uid": "nc2", "candidate_text": "Encyclopædia Britannica", "comparison_form": "encyclopaedia britannica", "surface_forms": ["Encyclopædia Britannica"], "tier": "tier_a", "occurrence_count": 1, "embedding_eligible": True},
        {"candidate_uid": "nc3", "candidate_text": "the speckled band", "comparison_form": "the speckled band", "surface_forms": ["the speckled band"], "tier": "tier_a", "occurrence_count": 1, "embedding_eligible": True},
        {"candidate_uid": "nc4", "candidate_text": "the blue carbuncle", "comparison_form": "the blue carbuncle", "surface_forms": ["the blue carbuncle"], "tier": "tier_a", "occurrence_count": 1, "embedding_eligible": True},
        {"candidate_uid": "nc5", "candidate_text": "woman", "comparison_form": "woman", "surface_forms": ["woman"], "tier": "excluded", "occurrence_count": 1, "embedding_eligible": False},
        {"candidate_uid": "nc6", "candidate_text": "them", "comparison_form": "them", "surface_forms": ["they"], "tier": "excluded", "occurrence_count": 1, "embedding_eligible": False},
    ]
    question_units = [
        {"question_id": "q0", "question": "", "surface_text": "Sherlock Holmes"},
        {"question_id": "q1", "question": "", "surface_text": "Encyclopaedia Britannica"},
        {"question_id": "q2", "question": "", "surface_text": "the speckled band"},
        {"question_id": "q3", "question": "", "surface_text": "the stolen blue carbuncle"},
        {"question_id": "q4", "question": "", "surface_text": "woman"},
        {"question_id": "q5", "question": "", "surface_text": "they"},
    ]

    rows, matches = analyze_question_units(question_units, candidates, default_orthographic_map())
    levels = {row["question_id"]: row["inventory_coverage_level"] for row in rows}
    eligible = {row["question_id"]: row["eligible_coverage_level"] for row in rows}
    types = {row["question_id"]: row["inventory_match_type"] for row in rows}
    inventory_candidates = {row["question_id"]: row["inventory_matching_candidate_text"] for row in rows}

    assert types["q0"] == "candidate_text_exact_match"
    assert inventory_candidates["q0"] == "Sherlock Holmes"
    assert levels["q1"] == "strong"
    assert types["q1"] == "comparison_form_match"
    assert levels["q2"] == "strong"
    assert levels["q3"] == "partial_phrase"
    assert types["q3"] == "contiguous_contained_candidate"
    assert levels["q4"] == "strong"
    assert eligible["q4"] == "none"
    assert types["q5"] == "alternate_surface_match"


def test_pipeline_preserves_source_hashes_and_outputs(tmp_path):
    v2a = tmp_path / "noun_units_v2a"
    generated = v2a / "generated"
    config = v2a / "config"
    generated.mkdir(parents=True)
    config.mkdir()
    units = [
        unit("u1", "Sherlock Holmes", "named_entity", ["PERSON"], 2),
        unit("u2", "SHERLOCK HOLMES", "noun_phrase", [], 2),
        unit("u3", "thing", "common_noun", [], 5),
    ]
    for name in ["noun_units_normalized.jsonl", "noun_units_accepted.jsonl", "noun_units_review.jsonl"]:
        (generated / name).write_text("\n".join(json.dumps(u) for u in units) + "\n", encoding="utf-8")
    (generated / "noun_unit_manifest.json").write_text("{}\n", encoding="utf-8")
    (generated / "noun_unit_statistics.json").write_text("{}\n", encoding="utf-8")
    (config / "generic_nouns.txt").write_text("thing\n", encoding="utf-8")
    questions = tmp_path / "questions.json"
    questions.write_text('{"questions":[]}\n', encoding="utf-8")
    before = sha256_file(generated / "noun_units_normalized.jsonl")

    result = run_candidate_pool(v2a, v2a / "candidates", questions, skip_baseline_extraction=True)

    assert before == sha256_file(generated / "noun_units_normalized.jsonl")
    assert result["statistics"]["consolidated_lexical_candidate_count"] == 2
    assert (v2a / "candidates/generated/noun_embedding_candidates_all.jsonl").exists()
    sample_rows = [json.loads(line) for line in (v2a / "candidates/review/noun_candidate_manual_sample.jsonl").read_text().splitlines()]
    assert len({row["candidate_uid"] for row in sample_rows}) == len(sample_rows)
