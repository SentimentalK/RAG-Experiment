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
    coverage = Counter(row["coverage_level"] for row in coverage_rows)
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
        "baseline_coverage_counts": {
            "strong_coverage_count": coverage.get("strong", 0),
            "partial_coverage_count": coverage.get("partial", 0),
            "no_coverage_count": coverage.get("none", 0),
        },
        "candidates_created_from_multiple_source_units": sum(1 for c in candidates if len(c["source_unit_uids"]) > 1),
        "candidates_with_conflicting_entity_labels": sum(1 for c in candidates if len(c["observed_entity_types"]) > 1),
        "candidates_with_repaired_punctuation": sum(1 for c in candidates if "surrounding_punctuation_removed" in c["normalization_actions"]),
        "generic_single_nouns_excluded": sum(1 for c in candidates if c["tier"] == "excluded" and "generic_single_noun" in c["quality_flags"]),
    }
