EXCLUDED_FLAGS = {
    "empty",
    "pronoun",
    "determiner",
    "function_word_only",
    "numeric_expression",
    "ordinal_expression",
    "currency_expression",
    "isolated_abbreviation",
    "punctuation_only",
    "suspected_sentence_fragment",
}
HARD_FLAGS = EXCLUDED_FLAGS | {"generic_single_noun"}
REVIEW_FLAGS = {"leading_discourse_marker", "excessive_punctuation", "heading_fragment"}


def has_recovery(candidate: dict) -> bool:
    flags = set(candidate.get("quality_flags", []))
    actions = set(candidate.get("normalization_actions", []))
    return "address_like" in flags or "orthographic_map_applied" in actions


def classify_tier(candidate: dict, config: dict) -> tuple[str, list[str], list[str]]:
    flags = set(candidate.get("quality_flags", []))
    unit_types = set(candidate.get("observed_unit_types", []))
    count = candidate.get("occurrence_count", 0)
    content_count = candidate.get("content_token_count", 0)
    words = candidate.get("token_count", 0)
    possessor_type = candidate.get("possessor_type", "none")
    gate_failures: list[str] = []
    exclude_generic_single_nouns = config.get("exclude_generic_single_nouns", True)

    if candidate.get("upstream_rejected_only") and not has_recovery(candidate):
        gate_failures.append("upstream_rejected_only")
        return "excluded", ["upstream_rejected_only"], gate_failures
    if exclude_generic_single_nouns and "generic_single_noun" in flags and content_count <= 1:
        gate_failures.append("generic_single_noun")
        return "excluded", ["generic_single_noun"], gate_failures
    hard = sorted((flags & EXCLUDED_FLAGS) - {"numeric_expression"} if "address_like" in flags else flags & EXCLUDED_FLAGS)
    if hard:
        gate_failures.extend(hard)
        return "excluded", hard, gate_failures
    if "common_noun" in unit_types and unit_types == {"common_noun"} and count < config.get("tier_b_common_noun_min_frequency", 2):
        gate_failures.append("singleton_common_noun_low_priority")
        return "excluded", ["singleton_common_noun_low_priority"], gate_failures
    if flags & REVIEW_FLAGS:
        return "review", sorted(flags & REVIEW_FLAGS), gate_failures
    if words > config.get("max_clean_phrase_tokens", 6):
        return "review", ["long_or_complex_phrase"], gate_failures
    if possessor_type in {"mixed", "unknown"}:
        return "review", [f"{possessor_type}_possessor"], gate_failures
    if possessor_type == "pronoun":
        if count >= config.get("pronoun_possessive_min_frequency", 2) and content_count >= 1:
            return "tier_b", ["pronoun_possessive_frequency_gte_threshold"], gate_failures
        gate_failures.append("low_priority_pronoun_possessive")
        return "excluded", ["low_priority_pronoun_possessive"], gate_failures
    if unit_types & {"named_entity", "proper_noun"}:
        if content_count >= 2:
            return "tier_a", ["clean_multiword_named_or_proper_expression"], gate_failures
        if count >= config.get("tier_a_single_name_min_frequency", 2):
            return "tier_a", ["clean_repeated_single_token_name"], gate_failures
        return "tier_b", ["rare_clean_single_token_name"], gate_failures
    if "noun_phrase" in unit_types and content_count >= config.get("tier_a_min_content_tokens", 2):
        return "tier_a", ["specific_content_phrase"], gate_failures
    if "noun_phrase" in unit_types and content_count == 1:
        return "tier_b", ["valid_one_content_token_phrase"], gate_failures
    if "common_noun" in unit_types and count >= config.get("tier_b_common_noun_min_frequency", 2):
        return "tier_b", ["clean_common_noun_frequency_gte_threshold"], gate_failures
    if count >= 2:
        return "tier_b", ["clean_lower_confidence_candidate"], gate_failures
    gate_failures.append("low_priority_singleton")
    return "excluded", ["low_priority_singleton"], gate_failures
