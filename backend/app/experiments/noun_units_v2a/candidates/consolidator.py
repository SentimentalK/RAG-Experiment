from collections import Counter, defaultdict
from typing import Any

from app.experiments.noun_units_v2a.candidates.boundary_filter import quality_flags
from app.experiments.noun_units_v2a.candidates.comparison_normalizer import comparison_form, normalize_display, representative_surface, token_count
from app.experiments.noun_units_v2a.candidates.tier_classifier import classify_tier
from app.experiments.noun_units_v2a.candidates.writer import stable_uid


def source_occurrence_key(context: dict[str, Any], fallback: str) -> str:
    return "|".join([
        str(context.get("story_id") or ""),
        str(context.get("occurrence_uid") or ""),
        str(context.get("primary_chunk_uid") or ""),
        str(context.get("source_sentence") or fallback),
    ])


def merge_reasons(units: list[dict[str, Any]]) -> list[str]:
    reasons = {"same_comparison_form"}
    if len({u.get("unit_type") for u in units}) > 1:
        reasons.add("cross_unit_type_duplicate")
    entity_types = {etype for u in units for etype in u.get("entity_types", [])}
    if len(entity_types) > 1:
        reasons.add("cross_entity_type_duplicate")
    return sorted(reasons)


def consolidate_units(units: list[dict[str, Any]], generic_nouns: set[str], leading_noise_terms: set[str], orthographic_map: dict[str, str], config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unit_comparisons: dict[str, tuple[str, list[str]]] = {}
    for unit in units:
        comparison, actions = comparison_form(unit["canonical_text"], orthographic_map)
        grouped[comparison].append(unit)
        unit_comparisons[unit["unit_uid"]] = (comparison, actions)

    candidates: list[dict[str, Any]] = []
    merge_map: list[dict[str, Any]] = []
    for comparison, source_units in grouped.items():
        source_units = sorted(source_units, key=lambda u: u["unit_uid"])
        source_lookup = {unit["unit_uid"]: unit for unit in source_units}
        surface_forms = sorted({form for unit in source_units for form in unit.get("surface_forms", [])} | {u["canonical_text"] for u in source_units})
        flags_by_form = {}
        repaired_by_form = {}
        all_actions = set()
        for form in surface_forms:
            display, display_actions = normalize_display(form)
            form_comparison, actions = comparison_form(form, orthographic_map)
            all_actions.update(display_actions)
            all_actions.update(actions)
            flags_by_form[form] = set(quality_flags(form, form_comparison, generic_nouns, leading_noise_terms))
            repaired_by_form[form] = display != form
        candidate_text = representative_surface(surface_forms, source_lookup, flags_by_form, repaired_by_form, comparison)
        candidate_flags = set(quality_flags(candidate_text, comparison, generic_nouns, leading_noise_terms))
        for form_flags in flags_by_form.values():
            if "leading_punctuation_removed" in form_flags:
                candidate_flags.add("leading_punctuation_removed")
        contexts_by_key = {}
        for unit in source_units:
            for context in unit.get("example_contexts", []):
                contexts_by_key.setdefault(source_occurrence_key(context, unit["unit_uid"]), context)
        example_contexts = [contexts_by_key[key] for key in sorted(contexts_by_key)[:5]]
        occurrence_keys = set(contexts_by_key)
        if not occurrence_keys:
            occurrence_count = sum(unit.get("occurrence_count", 0) for unit in source_units)
        else:
            occurrence_count = max(len(occurrence_keys), max(unit.get("occurrence_count", 0) for unit in source_units))
        story_ids = sorted({story_id for unit in source_units for story_id in unit.get("story_ids", [])})
        chunk_ids = sorted({chunk_id for unit in source_units for chunk_id in unit.get("source_chunk_uids", [])})
        candidate = {
            "candidate_uid": stable_uid("nc", comparison),
            "candidate_text": candidate_text,
            "comparison_form": comparison,
            "surface_forms": surface_forms,
            "observed_unit_types": sorted({unit["unit_type"] for unit in source_units}),
            "observed_entity_types": sorted({etype for unit in source_units for etype in unit.get("entity_types", [])}),
            "source_unit_uids": [unit["unit_uid"] for unit in source_units],
            "occurrence_count": occurrence_count,
            "story_ids": story_ids,
            "story_count": len(story_ids),
            "source_chunk_uids": chunk_ids,
            "source_chunk_count": len(chunk_ids),
            "example_contexts": example_contexts,
            "classification_reasons": sorted({reason for unit in source_units for reason in unit.get("classification_reasons", [])}),
            "expandability_reasons": sorted({reason for unit in source_units for reason in unit.get("expandability_reasons", [])}),
            "quality_flags": sorted(candidate_flags),
            "normalization_actions": sorted(all_actions),
            "original_v2a_classes": sorted({unit["classification"] for unit in source_units}),
            "possessors": sorted({possessor for unit in source_units for possessor in unit.get("possessors", [])}),
            "token_count": token_count(candidate_text),
            "baseline_question_matches": [],
            "baseline_diagnostic_only": True,
            "embedding_status": "not_generated",
        }
        tier, reasons = classify_tier(candidate, config.get("exclude_generic_single_nouns", True))
        candidate["tier"] = tier
        candidate["tier_reasons"] = reasons
        candidates.append(candidate)
        merge_map.append({
            "candidate_uid": candidate["candidate_uid"],
            "comparison_form": comparison,
            "source_unit_uids": candidate["source_unit_uids"],
            "merge_reasons": merge_reasons(source_units),
        })
    return (
        sorted(candidates, key=lambda c: (c["tier"], c["comparison_form"], c["candidate_uid"])),
        sorted(merge_map, key=lambda m: (m["comparison_form"], m["candidate_uid"])),
    )
