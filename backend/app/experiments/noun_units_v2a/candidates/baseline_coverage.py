import json
from typing import Any

from app.experiments.noun_units_v2a.candidates.comparison_normalizer import comparison_form


def contained_match(query_form: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    query_tokens = query_form.split()
    matches = [
        candidate for candidate in candidates
        if candidate["comparison_form"] != query_form
        and (
            candidate["comparison_form"] in query_form
            or all(token in query_tokens for token in candidate["comparison_form"].split())
        )
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda c: (-len(c["comparison_form"]), c["comparison_form"]))[0]


def head_match(query_form: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    head = query_form.split()[-1] if query_form.split() else query_form
    if not head:
        return None
    matches = [candidate for candidate in candidates if candidate["comparison_form"].split()[-1:] == [head]]
    if not matches:
        return None
    return sorted(matches, key=lambda c: (-c["occurrence_count"], c["comparison_form"]))[0]


def coverage_level(match_type: str) -> str:
    if match_type in {"exact_surface_match", "comparison_form_match"}:
        return "strong"
    if match_type in {"longest_contained_candidate", "head_noun_match"}:
        return "partial"
    return "none"


def analyze_question_units(question_units: list[dict[str, Any]], candidates: list[dict[str, Any]], orthographic_map: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    by_comparison = {candidate["comparison_form"]: candidate for candidate in candidates}
    by_surface = {}
    for candidate in candidates:
        for form in candidate["surface_forms"]:
            by_surface.setdefault(form.casefold(), candidate)
    rows = []
    candidate_matches: dict[str, list[str]] = {}
    for unit in question_units:
        qform, _ = comparison_form(unit["surface_text"], orthographic_map)
        surface_match = by_surface.get(unit["surface_text"].casefold())
        comparison_match = by_comparison.get(qform)
        contained = contained_match(qform, candidates)
        head = head_match(qform, candidates)
        match_type = "no_match"
        match = None
        if surface_match:
            match_type = "exact_surface_match"
            match = surface_match
        elif comparison_match:
            match_type = "comparison_form_match"
            match = comparison_match
        elif contained:
            match_type = "longest_contained_candidate"
            match = contained
        elif head:
            match_type = "head_noun_match"
            match = head
        level = coverage_level(match_type)
        row = {
            "question_id": unit["question_id"],
            "question": unit.get("question"),
            "question_unit": unit["surface_text"],
            "comparison_form": qform,
            "match_type": match_type,
            "coverage_level": level,
            "matching_candidate_uid": match["candidate_uid"] if match else None,
            "matching_candidate_text": match["candidate_text"] if match else None,
            "candidate_tier": match["tier"] if match else None,
        }
        rows.append(row)
        if match:
            candidate_matches.setdefault(match["candidate_uid"], []).append(unit["question_id"])
    return sorted(rows, key=lambda r: (r["question_id"], r["question_unit"].casefold(), r["match_type"])), candidate_matches


def extract_question_units_with_spacy(questions_path, model_name: str) -> list[dict[str, Any]]:
    from app.experiments.noun_units_v2a.extractor import extract_candidates, load_spacy_model, merge_span_candidates

    nlp = load_spacy_model(model_name)
    data = json.loads(questions_path.read_text(encoding="utf-8"))
    rows = []
    for question in data.get("questions", []):
        doc = nlp(question["question"])
        for candidate in merge_span_candidates(extract_candidates(doc)):
            rows.append({
                "question_id": question["question_id"],
                "question": question["question"],
                "surface_text": candidate["surface_text"],
                "unit_type": candidate["primary_unit_type"],
            })
    return sorted(rows, key=lambda r: (r["question_id"], r["surface_text"].casefold()))
