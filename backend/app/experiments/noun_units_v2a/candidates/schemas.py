from typing import Any, Literal, TypedDict


Tier = Literal["tier_a", "tier_b", "review", "excluded"]


class CandidateRecord(TypedDict, total=False):
    candidate_uid: str
    candidate_text: str
    comparison_form: str
    tier: Tier
    tier_reasons: list[str]
    surface_forms: list[str]
    observed_unit_types: list[str]
    observed_entity_types: list[str]
    source_unit_uids: list[str]
    occurrence_count: int
    story_count: int
    story_ids: list[str]
    source_chunk_uids: list[str]
    source_chunk_count: int
    example_contexts: list[dict[str, Any]]
    content_tokens: list[str]
    content_token_count: int
    possessor_type: str
    upstream_rejected_only: bool
    embedding_eligible: bool
    quality_gate_failures: list[str]
    surface_quality_flags: dict[str, list[str]]
    quality_flags: list[str]
    normalization_actions: list[str]
    original_v2a_classes: list[str]
    baseline_question_matches: list[str]
    baseline_diagnostic_only: bool
    embedding_status: str
