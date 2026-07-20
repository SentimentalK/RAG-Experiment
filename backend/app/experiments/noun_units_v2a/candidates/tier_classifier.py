from app.experiments.noun_units_v2a.candidates.comparison_normalizer import token_count


EXCLUDED_FLAGS = {
    "empty",
    "pronoun",
    "determiner",
    "stop_word_only",
    "numeric_expression",
    "ordinal_expression",
    "currency_expression",
    "isolated_abbreviation",
    "punctuation_only",
    "suspected_sentence_fragment",
}
REVIEW_FLAGS = {"leading_discourse_marker", "excessive_punctuation"}


def classify_tier(candidate: dict, exclude_generic_single_nouns: bool = True) -> tuple[str, list[str]]:
    flags = set(candidate.get("quality_flags", []))
    unit_types = set(candidate.get("observed_unit_types", []))
    count = candidate.get("occurrence_count", 0)
    text = candidate["candidate_text"]
    words = token_count(text)

    if exclude_generic_single_nouns and "generic_single_noun" in flags and words == 1:
        return "excluded", ["generic_single_noun"]
    if flags & EXCLUDED_FLAGS:
        return "excluded", sorted(flags & EXCLUDED_FLAGS)
    if flags & REVIEW_FLAGS:
        return "review", sorted(flags & REVIEW_FLAGS)
    if words > 6:
        return "review", ["long_or_complex_phrase"]
    if unit_types & {"named_entity", "proper_noun"}:
        return "tier_a", ["clean_named_or_proper_expression"]
    if candidate.get("possessors"):
        return "review", ["possessive_relation"]
    if "noun_phrase" in unit_types and 2 <= words <= 6 and count >= 2:
        return "tier_a", ["specific_2_to_6_token_noun_phrase", "frequency_gte_2"]
    if "noun_phrase" in unit_types and count >= 2:
        return "tier_b", ["clean_lower_confidence_noun_phrase_frequency_gte_2"]
    if "common_noun" in unit_types and count >= 2:
        return "tier_b", ["clean_common_noun_frequency_gte_2"]
    if count >= 2:
        return "tier_b", ["clean_lower_confidence_candidate"]
    return "review", ["single_occurrence_lower_confidence_candidate"]
