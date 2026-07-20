from collections import Counter
from typing import Any


def build_statistics(input_count: int, candidates: list[dict[str, Any]], merge_map: list[dict[str, Any]], coverage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    tier_counts = Counter(candidate["tier"] for candidate in candidates)
    unit_type_counts = Counter(unit_type for candidate in candidates for unit_type in candidate["observed_unit_types"])
    frequency_counts = {
        "frequency_gte_2": sum(1 for c in candidates if c["occurrence_count"] >= 2),
        "frequency_gte_3": sum(1 for c in candidates if c["occurrence_count"] >= 3),
        "frequency_gte_5": sum(1 for c in candidates if c["occurrence_count"] >= 5),
        "frequency_gte_10": sum(1 for c in candidates if c["occurrence_count"] >= 10),
    }
    token_lengths = Counter()
    for candidate in candidates:
        length = candidate["token_count"]
        if length <= 5:
            token_lengths[str(length)] += 1
        elif length <= 8:
            token_lengths["6-8"] += 1
        else:
            token_lengths[">8"] += 1
    story_counts = Counter()
    for candidate in candidates:
        count = candidate["story_count"]
        if count == 1:
            story_counts["1"] += 1
        elif count <= 3:
            story_counts["2-3"] += 1
        elif count <= 6:
            story_counts["4-6"] += 1
        else:
            story_counts["7+"] += 1
    flags = Counter(flag for candidate in candidates for flag in candidate["quality_flags"])
    actions = Counter(action for candidate in candidates for action in candidate["normalization_actions"])
    inventory_coverage = Counter(row["inventory_coverage_level"] for row in coverage_rows)
    eligible_coverage = Counter(row["eligible_coverage_level"] for row in coverage_rows)
    tier_reason_counts = Counter(reason for candidate in candidates for reason in candidate["tier_reasons"])
    review_reason_counts = Counter(reason for candidate in candidates if candidate["tier"] == "review" for reason in candidate["tier_reasons"])
    exclusion_reason_counts = Counter(reason for candidate in candidates if candidate["tier"] == "excluded" for reason in candidate["tier_reasons"])
    original_by_tier = Counter((candidate["tier"], ",".join(candidate["original_v2a_classes"])) for candidate in candidates)
    content_counts = Counter(str(candidate.get("content_token_count", 0)) for candidate in candidates)
    possessor_counts = Counter(candidate.get("possessor_type", "none") for candidate in candidates)
    tier_possessor = Counter((candidate["tier"], candidate.get("possessor_type", "none")) for candidate in candidates)
    hard_flags = {"empty", "pronoun", "determiner", "function_word_only", "numeric_expression", "ordinal_expression", "currency_expression", "isolated_abbreviation", "punctuation_only", "suspected_sentence_fragment", "generic_single_noun"}
    eligible = [candidate for candidate in candidates if candidate["tier"] in {"tier_a", "tier_b"}]
    return {
        "input_normalized_unit_count": input_count,
        "consolidated_lexical_candidate_count": len(candidates),
        "cross_type_duplicate_count": sum(1 for row in merge_map if "cross_unit_type_duplicate" in row["merge_reasons"]),
        "lexical_duplicate_group_count": sum(1 for row in merge_map if len(row["source_unit_uids"]) > 1),
        "conflicting_entity_label_group_count": sum(1 for c in candidates if len(c["observed_entity_types"]) > 1),
        "tier_counts": dict(sorted(tier_counts.items())),
        "candidate_counts_by_unit_type": dict(sorted(unit_type_counts.items())),
        "candidate_counts_by_frequency_threshold": frequency_counts,
        "candidate_counts_by_token_length": dict(sorted(token_lengths.items())),
        "candidate_counts_by_story_count": dict(sorted(story_counts.items())),
        "boundary_noise_reason_counts": dict(sorted(flags.items())),
        "normalization_action_counts": dict(sorted(actions.items())),
        "tier_reason_counts": dict(sorted(tier_reason_counts.items())),
        "review_reason_counts": dict(sorted(review_reason_counts.items())),
        "exclusion_reason_counts": dict(sorted(exclusion_reason_counts.items())),
        "original_v2a_class_by_tier": {f"{tier}|{klass}": count for (tier, klass), count in sorted(original_by_tier.items())},
        "upstream_rejected_candidates_in_tier_a": sum(1 for c in candidates if c["tier"] == "tier_a" and c.get("upstream_rejected_only")),
        "upstream_rejected_candidates_in_tier_b": sum(1 for c in candidates if c["tier"] == "tier_b" and c.get("upstream_rejected_only")),
        "content_token_count_distribution": dict(sorted(content_counts.items())),
        "possessor_type_distribution": dict(sorted(possessor_counts.items())),
        "tier_by_possessor_type": {f"{tier}|{possessor}": count for (tier, possessor), count in sorted(tier_possessor.items())},
        "eligible_candidates_with_hard_flags": sum(1 for c in eligible if hard_flags & set(c.get("quality_flags", []))),
        "eligible_candidates_with_unresolved_boundary_flags": sum(1 for c in eligible if {"leading_discourse_marker", "excessive_punctuation", "heading_fragment"} & set(c.get("quality_flags", []))),
        "inventory_coverage_counts": {
            "inventory_strong": inventory_coverage.get("strong", 0),
            "inventory_partial_phrase": inventory_coverage.get("partial_phrase", 0),
            "inventory_head_only": inventory_coverage.get("head_only", 0),
            "inventory_none": inventory_coverage.get("none", 0),
        },
        "eligible_coverage_counts": {
            "eligible_strong": eligible_coverage.get("strong", 0),
            "eligible_partial_phrase": eligible_coverage.get("partial_phrase", 0),
            "eligible_head_only": eligible_coverage.get("head_only", 0),
            "eligible_none": eligible_coverage.get("none", 0),
        },
        "candidates_created_from_multiple_source_units": sum(1 for c in candidates if len(c["source_unit_uids"]) > 1),
        "candidates_with_conflicting_entity_labels": sum(1 for c in candidates if len(c["observed_entity_types"]) > 1),
        "candidates_with_repaired_punctuation": sum(1 for c in candidates if "surrounding_punctuation_removed" in c["normalization_actions"]),
        "generic_single_nouns_excluded": sum(1 for c in candidates if c["tier"] == "excluded" and "generic_single_noun" in c["quality_flags"]),
    }
