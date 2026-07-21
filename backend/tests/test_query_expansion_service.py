import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_query_expansion_service
from app.api.main import app
from app.core.config import settings
from app.services.alias_registry import AliasRegistry
from app.services.query_expansion_service import (
    QueryExpansionConfig,
    QueryExpansionRequestOptions,
    QueryExpansionService,
    normalize_query_with_offsets,
)


def make_member(
    uid: str,
    text: str,
    *,
    relation_type: str = "exact_name",
    safe: bool = True,
    constraints: list[str] | None = None,
) -> dict:
    return {
        "candidate_uid": uid,
        "candidate_text": text,
        "relation_type": relation_type,
        "same_entity": True,
        "member_disposition": "approved_member" if safe else "normalization_only",
        "safe_to_substitute": safe,
        "substitution_constraints": constraints or [],
        "evidence_story_ids": ["s01-a-scandal-in-bohemia"],
        "evidence_sentences": ["Example evidence."],
        "review_reason": None,
    }


def make_group(
    group_id: str,
    canonical_name: str,
    members: list[dict],
    *,
    status: str = "approved_story_scoped",
    scope: str = "story_scoped",
    entity_type: str = "PERSON",
    story_ids: list[str] | None = None,
) -> dict:
    return {
        "group_id": group_id,
        "canonical_name": canonical_name,
        "entity_type": entity_type,
        "scope": scope,
        "story_ids": story_ids if story_ids is not None else ["s01-a-scandal-in-bohemia"],
        "approval_status": status,
        "group_confidence": "high",
        "safe_for_query_substitution": True,
        "members": members,
        "removed_members": [],
        "group_review_reason": None,
    }


def make_document(groups: list[dict]) -> dict:
    dispositions = []
    for group in groups:
        for member in group["members"]:
            dispositions.append(
                {
                    "candidate_uid": member["candidate_uid"],
                    "candidate_text": member["candidate_text"],
                    "final_category": "approved_group_member" if member["safe_to_substitute"] else "normalization_only_group_member",
                    "group_id": group["group_id"],
                    "notes": None,
                }
            )
    return {
        "metadata": {
            "all_input_candidates_accounted_for": True,
            "all_output_uids_in_allowlist": True,
            "active_group_members_unique": True,
            "approved_strong_group_count": sum(1 for group in groups if group["approval_status"] == "approved_strong"),
            "approved_story_scoped_group_count": sum(1 for group in groups if group["approval_status"] == "approved_story_scoped"),
            "input_candidate_count": len(dispositions),
            "normalization_only_candidate_count": sum(
                1 for item in dispositions if item["final_category"].startswith("normalization_only")
            ),
        },
        "validation_summary": {
            "active_group_members_unique": True,
            "all_input_candidates_accounted_for": True,
            "all_output_uids_in_allowlist": True,
            "candidate_texts_match_source": True,
            "duplicate_active_memberships": [],
            "missing_source_candidates": [],
            "unknown_uids": [],
            "unresolved_status_count": 0,
        },
        "approved_groups": groups,
        "rejected_groups": [],
        "excluded_candidates": [],
        "ambiguous_candidates": [],
        "review_required_groups": [],
        "split_required": [],
        "singletons": [],
        "invalid_generated_candidates": [],
        "narrative_identity_relations": [],
        "candidate_final_dispositions": dispositions,
    }


def load_registry(tmp_path: Path, document: dict) -> AliasRegistry:
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return AliasRegistry.load(path, expected_sha256=None, strict_validation=True)


def frozen_service() -> QueryExpansionService:
    registry = AliasRegistry.load(
        settings.ALIAS_DATASET_PATH,
        expected_sha256=settings.ALIAS_DATASET_EXPECTED_SHA256,
        strict_validation=True,
    )
    return QueryExpansionService(registry, QueryExpansionConfig.from_settings(settings))


def test_query_normalization_maps_offsets_back_to_original_span():
    query = "  What did St. George’s   College publish?  "
    normalized = normalize_query_with_offsets(query)

    assert normalized.normalized_text == "what did st. george's college publish?"
    start = normalized.normalized_text.index("st. george's college")
    end = start + len("st. george's college")
    span = normalized.original_span(start, end)
    assert query[span.original_start : span.original_end] == "St. George’s   College"


def test_strong_expansion_contains_expected_holmes_variants():
    trace = frozen_service().expand("What did Mr. Holmes discover?")

    assert trace.expansion_reason == "aliases_expanded"
    assert trace.detected_mentions[0].group_id == "entity-sherlock-holmes"
    assert trace.detected_mentions[0].eligibility == "eligible_strong"
    texts = {variant.query_text for variant in trace.generated_variants}
    assert "What did Sherlock Holmes discover?" in texts
    assert "What did Holmes discover?" in texts
    assert len(trace.generated_variants) <= 8


def test_story_scoped_expansion_and_single_token_case_rules():
    trace = frozen_service().expand("Why did Hosmer Angel disappear?")

    assert trace.expansion_reason == "aliases_expanded"
    mention = trace.selected_mentions[0]
    assert mention.group_id == "entity-hosmer-angel"
    assert mention.eligibility == "eligible_story_scoped"
    assert mention.story_ids == ("s03-a-case-of-identity",)
    texts = [variant.query_text for variant in trace.generated_variants]
    assert texts[1:] == [
        "Why did Hosmer disappear?",
        "Why did Mr. Hosmer Angel disappear?",
    ]

    upper = frozen_service().expand("What did Angel promise?")
    assert upper.selected_mentions[0].single_token_story_scoped is True
    assert upper.expansion_reason == "aliases_expanded"

    lower = frozen_service().expand("Was he described as an angel?")
    assert lower.expansion_reason == "all_mentions_blocked"
    assert lower.detected_mentions[0].blocked_reason == "lowercase_single_token_story_scoped"


def test_longest_match_normalization_only_and_possessive_boundaries():
    service = frozen_service()

    longest = service.expand("What did Mr. Sherlock Holmes observe?")
    assert [mention.original_text for mention in longest.detected_mentions] == ["Mr. Sherlock Holmes"]

    blocker = service.expand("What did this K. K. K. message mean?")
    assert blocker.expansion_reason == "only_normalization_only_mentions"
    assert blocker.generated_variants[0].query_text == "What did this K. K. K. message mean?"

    possessive = service.expand("What was Holmes's conclusion?")
    assert possessive.expansion_reason == "no_alias_mentions"


def test_same_span_ambiguous_surface_blocks_expansion(tmp_path):
    document = make_document(
        [
            make_group(
                "entity-alpha",
                "Alpha One",
                [make_member("uid-alpha-one", "Alpha One"), make_member("uid-alpha", "Alpha", relation_type="shortened_name")],
                status="approved_strong",
                scope="global",
                story_ids=[],
            ),
            make_group(
                "entity-beta",
                "Beta One",
                [make_member("uid-beta-one", "Beta One"), make_member("uid-beta-alpha", "Alpha", relation_type="shortened_name")],
            ),
        ]
    )
    service = QueryExpansionService(load_registry(tmp_path, document), QueryExpansionConfig())

    trace = service.expand("What did Alpha do?")
    assert trace.expansion_reason == "all_mentions_ambiguous"
    assert trace.detected_mentions[0].eligibility == "ambiguous_surface"
    assert len(trace.generated_variants) == 1


def test_story_scoped_target_must_be_unique(tmp_path):
    document = make_document(
        [
            make_group(
                "entity-full",
                "Full Unique Name",
                [
                    make_member("uid-full", "Full Unique Name", relation_type="exact_name"),
                    make_member("uid-short", "Short", relation_type="shortened_name"),
                    make_member("uid-mr", "Mr. Unique Name", relation_type="title_variant"),
                ],
            ),
            make_group(
                "entity-other",
                "Other Short",
                [
                    make_member("uid-other", "Other Short", relation_type="exact_name"),
                    make_member("uid-other-short", "Short", relation_type="shortened_name"),
                ],
            ),
        ]
    )
    service = QueryExpansionService(load_registry(tmp_path, document), QueryExpansionConfig())

    trace = service.expand("Why did Full Unique Name vanish?")
    alternatives = trace.alternatives_by_mention[trace.selected_mentions[0].mention_id]
    assert [alt.candidate_text for alt in alternatives] == ["Mr. Unique Name"]


def test_repeated_mentions_have_distinct_offsets_and_budget():
    trace = frozen_service().expand("Holmes asked Watson whether Holmes was correct.")

    holmes_mentions = [mention for mention in trace.detected_mentions if mention.original_text == "Holmes"]
    assert len(holmes_mentions) == 2
    assert holmes_mentions[0].start_offset != holmes_mentions[1].start_offset
    assert len(trace.selected_mentions) <= 3
    assert len(trace.generated_variants) <= 8


def test_request_override_only_tightens_server_config():
    service = frozen_service()
    server_disabled = service.expand(
        "What did Mr. Holmes discover?",
        QueryExpansionRequestOptions(enabled=True, max_query_variants=8),
    )
    assert server_disabled.expansion_reason == "aliases_expanded"

    disabled_config = QueryExpansionConfig(enabled=False, max_query_variants=4, allow_story_scoped=False)
    registry = AliasRegistry.load(
        settings.ALIAS_DATASET_PATH,
        expected_sha256=settings.ALIAS_DATASET_EXPECTED_SHA256,
        strict_validation=True,
    )
    locked_service = QueryExpansionService(registry, disabled_config)
    trace = locked_service.expand(
        "Why did Hosmer Angel disappear?",
        QueryExpansionRequestOptions(enabled=True, max_query_variants=8, allow_story_scoped=True),
    )
    assert trace.expansion_reason == "expansion_disabled"
    assert len(trace.generated_variants) == 1
    assert trace.config_snapshot.max_query_variants == 4
    assert trace.config_snapshot.allow_story_scoped is False


def test_budget_deduplication_and_determinism(tmp_path):
    strong_members = [
        make_member("uid-source", "Source Name", relation_type="exact_name"),
        make_member("uid-a", "Target A", relation_type="exact_name"),
        make_member("uid-b", "Target B", relation_type="exact_name"),
        make_member("uid-c", "Target C", relation_type="exact_name"),
        make_member("uid-d", "Target D", relation_type="exact_name"),
        make_member("uid-e", "Target E", relation_type="exact_name"),
        make_member("uid-f", "Target F", relation_type="exact_name"),
    ]
    document = make_document(
        [
            make_group("entity-source", "Source Name", strong_members, status="approved_strong", scope="global", story_ids=[]),
        ]
    )
    service = QueryExpansionService(
        load_registry(tmp_path, document),
        QueryExpansionConfig(max_query_variants=4, max_strong_alternatives_per_mention=6),
    )

    first = service.expand("Where was Source Name?")
    second = service.expand("Where was Source Name?")
    assert [variant.model_dump() for variant in first.generated_variants] == [
        variant.model_dump() for variant in second.generated_variants
    ]
    assert len(first.generated_variants) == 4
    assert first.truncated_variant_count > 0


def test_api_expand_and_isolation_from_rag_dependencies():
    service = MagicMock(spec=QueryExpansionService)
    service.expand.return_value = frozen_service().expand("What did Mr. Holmes discover?")
    app.dependency_overrides[get_query_expansion_service] = lambda: service
    try:
        client = TestClient(app)
        response = client.post(
            "/api/aliases/expand",
            json={"query": "What did Mr. Holmes discover?", "options": {"max_query_variants": 4}},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["expansion_reason"] == "aliases_expanded"
        assert payload["generated_variants"][0]["variant_kind"] == "original"
        service.expand.assert_called_once()
    finally:
        app.dependency_overrides.clear()
