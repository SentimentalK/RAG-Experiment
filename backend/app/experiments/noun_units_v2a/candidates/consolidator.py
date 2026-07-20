from collections import Counter, defaultdict
from typing import Any

from app.experiments.noun_units_v2a.candidates.boundary_filter import quality_flags
from app.experiments.noun_units_v2a.candidates.comparison_normalizer import comparison_form, content_tokens, normalize_display, representative_surface, token_count
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


def possessor_type(possessors: list[str], observed_unit_types: set[str]) -> str:
    if not possessors:
        return "none"
    pronouns = {"my", "your", "his", "her", "its", "our", "their"}
    seen = set()
    for possessor in possessors:
        clean = possessor.strip("'’").casefold()
        if clean in pronouns:
            seen.add("pronoun")
        elif possessor[:1].isupper() or observed_unit_types & {"named_entity", "proper_noun"}:
            seen.add("named")
        elif clean:
            seen.add("common")
        else:
            seen.add("unknown")
    if len(seen) == 1:
        return next(iter(seen))
    if "unknown" in seen:
        return "unknown"
    return "mixed"


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
        surface_quality_flags = {form: sorted(flags) for form, flags in flags_by_form.items() if flags}
        clean_same_comparison_exists = any(
            comparison_form(form, orthographic_map)[0] == comparison
            and not (flags_by_form[form] & {"leading_discourse_marker", "leading_punctuation_removed", "all_caps_fragment"})
            for form in surface_forms
        )
        if clean_same_comparison_exists:
            candidate_flags.discard("all_caps_fragment")
        contexts_by_key = {}
        for unit in source_units:
            for context in unit.get("example_contexts", []):
                contexts_by_key.setdefault(source_occurrence_key(context, unit["unit_uid"]), context)
        max_contexts = config.get("max_example_contexts_per_candidate", 5)
        example_contexts = [contexts_by_key[key] for key in sorted(contexts_by_key)[:max_contexts]]
        occurrence_keys = set(contexts_by_key)
        if not occurrence_keys:
            occurrence_count = sum(unit.get("occurrence_count", 0) for unit in source_units)
        else:
            occurrence_count = max(len(occurrence_keys), max(unit.get("occurrence_count", 0) for unit in source_units))
        story_ids = sorted({story_id for unit in source_units for story_id in unit.get("story_ids", [])})
        chunk_ids = sorted({chunk_id for unit in source_units for chunk_id in unit.get("source_chunk_uids", [])})
        observed_unit_types = sorted({unit["unit_type"] for unit in source_units})
        original_v2a_classes = sorted({unit["classification"] for unit in source_units})
        possessors = sorted({possessor for unit in source_units for possessor in unit.get("possessors", [])})
        tokens = content_tokens(candidate_text)
        candidate = {
            "candidate_uid": stable_uid("nc", comparison),
            "candidate_text": candidate_text,
            "comparison_form": comparison,
            "surface_forms": surface_forms,
            "observed_unit_types": observed_unit_types,
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
            "surface_quality_flags": surface_quality_flags,
            "normalization_actions": sorted(all_actions),
            "original_v2a_classes": original_v2a_classes,
            "upstream_rejected_only": original_v2a_classes == ["rejected"],
            "possessors": possessors,
            "possessor_type": possessor_type(possessors, set(observed_unit_types)),
            "token_count": token_count(candidate_text),
            "content_tokens": tokens,
            "content_token_count": len(tokens),
            "baseline_question_matches": [],
            "baseline_diagnostic_only": True,
            "embedding_status": "not_generated",
        }
        tier, reasons, gate_failures = classify_tier(candidate, config)
        candidate["tier"] = tier
        candidate["tier_reasons"] = reasons
        candidate["embedding_eligible"] = tier in set(config.get("eligible_tiers", ["tier_a", "tier_b"]))
        candidate["quality_gate_failures"] = gate_failures
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
