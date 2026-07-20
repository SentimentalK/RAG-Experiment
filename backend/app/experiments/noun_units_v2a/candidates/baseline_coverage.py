import json
import re
import unicodedata
from typing import Any

from app.experiments.noun_units_v2a.candidates.comparison_normalizer import comparison_form, content_tokens


def exact_text_form(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    for src, dst in {"’": "'", "‘": "'", "`": "'", "“": '"', "”": '"'}.items():
        value = value.replace(src, dst)
    value = re.sub(r"\s+", " ", value).strip().strip("\"'`“”‘’«»")
    return value.casefold()


def contiguous_span_match(query_tokens: list[str], candidate_tokens: list[str]) -> bool:
    if not candidate_tokens or len(candidate_tokens) > len(query_tokens):
        return False
    width = len(candidate_tokens)
    return any(query_tokens[index:index + width] == candidate_tokens for index in range(len(query_tokens) - width + 1))


def contained_match(query_form: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    query_tokens = query_form.split()
    query_content_tokens = [token.casefold() for token in content_tokens(query_form)]
    matches = [
        candidate for candidate in candidates
        if candidate["comparison_form"] != query_form
        and (
            contiguous_span_match(query_tokens, candidate["comparison_form"].split())
            or contiguous_span_match(query_content_tokens, [token.casefold() for token in (candidate.get("content_tokens") or content_tokens(candidate["candidate_text"]))])
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
    if match_type in {"candidate_text_exact_match", "comparison_form_match", "alternate_surface_match"}:
        return "strong"
    if match_type == "contiguous_contained_candidate":
        return "partial_phrase"
    if match_type == "head_noun_match":
        return "head_only"
    return "none"


def match_against_candidates(unit: dict[str, Any], candidates: list[dict[str, Any]], orthographic_map: dict[str, str]) -> dict[str, Any]:
    by_comparison = {candidate["comparison_form"]: candidate for candidate in candidates}
    by_candidate_text = {exact_text_form(candidate["candidate_text"]): candidate for candidate in candidates}
    by_surface = {}
    for candidate in candidates:
        for form in candidate["surface_forms"]:
            by_surface.setdefault(form.casefold(), candidate)
    qtext_form = exact_text_form(unit["surface_text"])
    qform, _ = comparison_form(unit["surface_text"], orthographic_map)
    question_tokens = qform.split()
    candidate_text_match = by_candidate_text.get(qtext_form)
    comparison_match = by_comparison.get(qform)
    surface_match = by_surface.get(unit["surface_text"].casefold())
    contained = contained_match(qform, candidates)
    head = head_match(qform, candidates)
    match_type = "no_match"
    match = None
    if candidate_text_match:
        match_type = "candidate_text_exact_match"
        match = candidate_text_match
    elif comparison_match:
        match_type = "comparison_form_match"
        match = comparison_match
    elif surface_match:
        match_type = "alternate_surface_match"
        match = surface_match
    elif contained:
        match_type = "contiguous_contained_candidate"
        match = contained
    elif head:
        match_type = "head_noun_match"
        match = head
    matched_token_count = min(len(match["comparison_form"].split()), len(question_tokens)) if match else 0
    question_token_count = len(question_tokens)
    return {
        "match_type": match_type,
        "coverage_level": coverage_level(match_type),
        "matching_candidate_uid": match["candidate_uid"] if match else None,
        "matching_candidate_text": match["candidate_text"] if match else None,
        "candidate_tier": match["tier"] if match else None,
        "matched_token_count": matched_token_count,
        "question_token_count": question_token_count,
        "token_coverage_ratio": min(1.0, round(matched_token_count / question_token_count, 4)) if question_token_count else 0.0,
    }


def analyze_question_units(question_units: list[dict[str, Any]], candidates: list[dict[str, Any]], orthographic_map: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    eligible_candidates = [candidate for candidate in candidates if candidate.get("embedding_eligible") or candidate.get("tier") in {"tier_a", "tier_b"}]
    rows = []
    candidate_matches: dict[str, list[str]] = {}
    for unit in question_units:
        qform, _ = comparison_form(unit["surface_text"], orthographic_map)
        inventory = match_against_candidates(unit, candidates, orthographic_map)
        eligible = match_against_candidates(unit, eligible_candidates, orthographic_map)
        row = {
            "question_id": unit["question_id"],
            "question": unit.get("question"),
            "question_unit": unit["surface_text"],
            "comparison_form": qform,
            "inventory_match_type": inventory["match_type"],
            "inventory_coverage_level": inventory["coverage_level"],
            "inventory_matching_candidate_uid": inventory["matching_candidate_uid"],
            "inventory_matching_candidate_text": inventory["matching_candidate_text"],
            "inventory_candidate_tier": inventory["candidate_tier"],
            "eligible_match_type": eligible["match_type"],
            "eligible_coverage_level": eligible["coverage_level"],
            "eligible_matching_candidate_uid": eligible["matching_candidate_uid"],
            "eligible_matching_candidate_text": eligible["matching_candidate_text"],
            "eligible_candidate_tier": eligible["candidate_tier"],
            "matched_token_count": eligible["matched_token_count"] or inventory["matched_token_count"],
            "question_token_count": eligible["question_token_count"] or inventory["question_token_count"],
            "token_coverage_ratio": eligible["token_coverage_ratio"] or inventory["token_coverage_ratio"],
        }
        rows.append(row)
        for uid in [inventory["matching_candidate_uid"], eligible["matching_candidate_uid"]]:
            if uid:
                candidate_matches.setdefault(uid, []).append(unit["question_id"])
    return sorted(rows, key=lambda r: (r["question_id"], r["question_unit"].casefold(), r["inventory_match_type"], r["eligible_match_type"])), candidate_matches


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
