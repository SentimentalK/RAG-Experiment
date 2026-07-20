import json
import random
from collections import Counter
from typing import Any


def table(rows: list[list[Any]], headers: list[str]) -> str:
    if not rows:
        return "_None._\n"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines) + "\n"


def deterministic_sample(candidates: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    selected: dict[str, dict[str, Any]] = {}
    strata = [
        ("tier_a_named_or_proper", [c for c in candidates if c["tier"] == "tier_a" and {"named_entity", "proper_noun"} & set(c["observed_unit_types"])]),
        ("tier_a_noun_phrase", [c for c in candidates if c["tier"] == "tier_a" and "noun_phrase" in c["observed_unit_types"]]),
        ("tier_b", [c for c in candidates if c["tier"] == "tier_b"]),
        ("review_or_excluded", [c for c in candidates if c["tier"] in {"review", "excluded"}]),
    ]
    for stratum, rows in strata:
        rows = sorted(rows, key=lambda c: c["candidate_uid"])
        rng.shuffle(rows)
        count = 0
        for candidate in rows:
            if candidate["candidate_uid"] in selected:
                continue
            selected[candidate["candidate_uid"]] = {
                "candidate_uid": candidate["candidate_uid"],
                "candidate_text": candidate["candidate_text"],
                "comparison_form": candidate["comparison_form"],
                "tier": candidate["tier"],
                "tier_reasons": candidate["tier_reasons"],
                "occurrence_count": candidate["occurrence_count"],
                "story_count": candidate["story_count"],
                "observed_unit_types": candidate["observed_unit_types"],
                "observed_entity_types": candidate["observed_entity_types"],
                "original_v2a_classes": candidate["original_v2a_classes"],
                "content_tokens": candidate["content_tokens"],
                "content_token_count": candidate["content_token_count"],
                "possessor_type": candidate["possessor_type"],
                "quality_flags": candidate["quality_flags"],
                "quality_gate_failures": candidate["quality_gate_failures"],
                "example_contexts": candidate["example_contexts"],
                "sampling_stratum": stratum,
                "sampling_seed": seed,
                "manual_review": {
                    "boundary_correct": None,
                    "meaningful_expression": None,
                    "specific_enough": None,
                    "appropriate_for_embedding": None,
                    "tier_correct": None,
                    "notes": "",
                },
            }
            count += 1
            if count >= 50:
                break
    return sorted(selected.values(), key=lambda r: (r["sampling_stratum"], r["candidate_text"].casefold(), r["candidate_uid"]))


def build_report(stats: dict[str, Any], candidates: list[dict[str, Any]], merge_map: list[dict[str, Any]], coverage_rows: list[dict[str, Any]], source_hashes: dict[str, str], config_hash: str) -> str:
    tier_rows = [[tier, count] for tier, count in sorted(stats["tier_counts"].items())]
    merge_examples = [
        [c["candidate_text"], c["comparison_form"], len(c["source_unit_uids"]), ", ".join(c["observed_unit_types"]), ", ".join(c["observed_entity_types"])]
        for c in sorted([c for c in candidates if len(c["source_unit_uids"]) > 1], key=lambda c: (-len(c["source_unit_uids"]), c["candidate_text"].casefold()))[:20]
    ]
    boundary_examples = [
        [c["candidate_text"], c["tier"], ", ".join(c["quality_flags"]), ", ".join(c["normalization_actions"])]
        for c in candidates if c["quality_flags"] or c["normalization_actions"]
    ][:30]
    examples = [
        [c["candidate_text"], c["tier"], c["occurrence_count"], c["story_count"], ", ".join(c["tier_reasons"])]
        for c in sorted(candidates, key=lambda c: (c["tier"], -c["occurrence_count"], c["candidate_text"].casefold()))[:50]
    ]
    coverage_display = [
        [
            r["question_id"], r["question_unit"], r["comparison_form"],
            r["inventory_match_type"], r["inventory_coverage_level"], r.get("inventory_matching_candidate_text") or "", r.get("inventory_candidate_tier") or "",
            r["eligible_match_type"], r["eligible_coverage_level"], r.get("eligible_matching_candidate_text") or "", r.get("eligible_candidate_tier") or "",
            r["token_coverage_ratio"],
        ]
        for r in coverage_rows
    ]
    tier_a = stats["tier_counts"].get("tier_a", 0)
    tier_b = stats["tier_counts"].get("tier_b", 0)
    structural_failures = []
    if stats.get("upstream_rejected_candidates_in_tier_a", 0) or stats.get("upstream_rejected_candidates_in_tier_b", 0):
        structural_failures.append("rejected-only candidates are embedding eligible")
    if stats.get("eligible_candidates_with_hard_flags", 0):
        structural_failures.append("hard-noise candidates are embedding eligible")
    recommendation = "Structural gates passed - complete manual sample review before embedding"
    if structural_failures:
        recommendation = "Structural gates failed - revise rules: " + "; ".join(structural_failures)
    return "\n".join([
        "# Embedding Candidate Report",
        "",
        "This candidate pool is lexical-only. Baseline question matches are diagnostic metadata only and do not affect tiering.",
        "",
        "## Input Summary",
        table([
            ["V2A normalized units", stats["input_normalized_unit_count"]],
            ["Source hashes", json.dumps(source_hashes, sort_keys=True)],
            ["Candidate configuration hash", config_hash],
        ], ["Metric", "Value"]),
        "## Consolidation Summary",
        table([
            ["Units before consolidation", stats["input_normalized_unit_count"]],
            ["Candidates after consolidation", stats["consolidated_lexical_candidate_count"]],
            ["Lexical duplicate groups", stats["lexical_duplicate_group_count"]],
            ["Cross-type duplicate groups", stats["cross_type_duplicate_count"]],
            ["Conflicting entity-label groups", stats["conflicting_entity_label_group_count"]],
        ], ["Metric", "Count"]),
        table(merge_examples, ["Candidate", "Comparison", "Source Units", "Unit Types", "Entity Types"]),
        "## Boundary Cleanup",
        table(boundary_examples, ["Candidate", "Tier", "Quality Flags", "Normalization Actions"]),
        "`" + json.dumps(stats["boundary_noise_reason_counts"], sort_keys=True) + "`",
        "",
        "## Tier Distribution",
        table(tier_rows, ["Tier", "Count"]),
        "By unit type: `" + json.dumps(stats["candidate_counts_by_unit_type"], sort_keys=True) + "`",
        "",
        "By frequency: `" + json.dumps(stats["candidate_counts_by_frequency_threshold"], sort_keys=True) + "`",
        "",
        "By token length: `" + json.dumps(stats["candidate_counts_by_token_length"], sort_keys=True) + "`",
        "",
        "By content-token count: `" + json.dumps(stats["content_token_count_distribution"], sort_keys=True) + "`",
        "",
        "By possessor type: `" + json.dumps(stats["possessor_type_distribution"], sort_keys=True) + "`",
        "",
        "Tier reasons: `" + json.dumps(stats["tier_reason_counts"], sort_keys=True) + "`",
        "",
        "Review reasons: `" + json.dumps(stats["review_reason_counts"], sort_keys=True) + "`",
        "",
        "Exclusion reasons: `" + json.dumps(stats["exclusion_reason_counts"], sort_keys=True) + "`",
        "",
        "By story count: `" + json.dumps(stats["candidate_counts_by_story_count"], sort_keys=True) + "`",
        "",
        "## Candidate Examples",
        table(examples, ["Candidate", "Tier", "Frequency", "Stories", "Reasons"]),
        "## Baseline Coverage",
        table(coverage_display, ["Question", "Question Unit", "Comparison", "Inventory Match", "Inventory Coverage", "Inventory Candidate", "Inventory Tier", "Eligible Match", "Eligible Coverage", "Eligible Candidate", "Eligible Tier", "Token Ratio"]),
        "Inventory: `" + json.dumps(stats["inventory_coverage_counts"], sort_keys=True) + "`",
        "",
        "Eligible: `" + json.dumps(stats["eligible_coverage_counts"], sort_keys=True) + "`",
        "",
        "## Structural Quality Gates",
        table([
            ["Rejected-only in Tier A", stats.get("upstream_rejected_candidates_in_tier_a", 0)],
            ["Rejected-only in Tier B", stats.get("upstream_rejected_candidates_in_tier_b", 0)],
            ["Eligible candidates with hard flags", stats.get("eligible_candidates_with_hard_flags", 0)],
            ["Eligible candidates with unresolved boundary flags", stats.get("eligible_candidates_with_unresolved_boundary_flags", 0)],
        ], ["Gate", "Count"]),
        "Manual quality decision pending. Suggested future Go criteria: Tier A boundary correctness >= 95%, appropriate-for-embedding precision >= 90%, and tier-correct precision >= 85%.",
        "",
        "## Estimated Next-Stage Workload",
        table([
            ["Tier A embedding computations", tier_a],
            ["Tier A Top-10 pairs for inspection", tier_a * 10],
            ["Tier A + Tier B embedding computations", tier_a + tier_b],
            ["Tier A + Tier B Top-10 pairs for inspection", (tier_a + tier_b) * 10],
        ], ["Workload", "Count"]),
        "Embedding computation workload is the number of candidate vectors. Human pair-review workload is the candidate count multiplied by the nearest-neighbour depth.",
        "",
        "## Recommendation",
        recommendation,
    ])
