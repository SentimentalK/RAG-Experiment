from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_expanded_retrieval_service
from app.api.main import app
from app.services.expanded_retrieval_service import (
    ExpandedRetrievalConfig,
    ExpandedRetrievalError,
    ExpandedRetrievalService,
)
from app.services.query_expansion_service import (
    QueryExpansionConfig,
    QueryExpansionTrace,
    QueryVariant,
)
from app.services.vector_search_service import VectorSearchService


def variant(idx: int, kind: str, text: str, variant_id: str | None = None) -> QueryVariant:
    return QueryVariant(
        variant_id=variant_id or ("original" if idx == 0 else f"v{idx}"),
        query_text=text,
        normalized_query_text=text.casefold(),
        variant_index=idx,
        variant_kind=kind,
        replacement_count=0 if idx == 0 else 1,
        strong_replacement_count=1 if kind.startswith("strong") else 0,
        story_scoped_replacement_count=1 if kind in {"story_scoped_single", "mixed"} else 0,
        replacements=(),
        generation_priority=0,
    )


def trace_with_variants(variants: list[QueryVariant], reason: str = "aliases_expanded") -> QueryExpansionTrace:
    return QueryExpansionTrace(
        original_query=variants[0].query_text if variants else "question",
        normalized_query=(variants[0].query_text if variants else "question").casefold(),
        config_snapshot=QueryExpansionConfig(),
        detected_mentions=(),
        selected_mentions=(),
        blocked_mentions=(),
        alternatives_by_mention={},
        generated_variants=tuple(variants),
        candidate_combination_count=0,
        invalid_combination_count=0,
        duplicate_variant_count=0,
        truncated_variant_count=0,
        expansion_applied=reason == "aliases_expanded",
        expansion_reason=reason,
    )


def hit(
    chunk_id: str,
    rank: int,
    *,
    similarity: float = 0.5,
    distance: float | None = None,
    section_title: str = "Section",
    text: str | None = None,
    document_id: str | None = None,
) -> dict:
    return {
        "rank": rank,
        "chunk_uid": chunk_id,
        "document_id": document_id,
        "section_order": 1,
        "section_title": section_title,
        "chunk_order": 1,
        "token_count": 100,
        "cosine_distance": 1.0 - similarity if distance is None else distance,
        "cosine_similarity": similarity,
        "chunk_text": text or f"Text for {chunk_id}",
    }


def search_response(results: list[dict]) -> dict:
    return {
        "status": "success",
        "model_name": "mock-embedding",
        "embedding_duration_ms": 1.0,
        "database_duration_ms": 2.0,
        "results": results,
    }


def service_for(trace: QueryExpansionTrace, responses: list[dict] | Exception, config: ExpandedRetrievalConfig | None = None):
    expansion = MagicMock()
    expansion.expand.return_value = trace
    search = MagicMock(spec=VectorSearchService)
    if isinstance(responses, Exception):
        search.search.side_effect = responses
    else:
        search.search.side_effect = responses
    registry = MagicMock()
    registry.snapshot.sha256 = "alias-sha"
    return ExpandedRetrievalService(
        alias_registry=registry,
        query_expansion_service=expansion,
        vector_search_service=search,
        config=config or ExpandedRetrievalConfig(),
    ), search


def test_no_expansion_calls_original_once_and_preserves_baseline_order():
    trace = trace_with_variants([variant(0, "original", "No alias question")], reason="no_alias_mentions")
    service, search = service_for(
        trace,
        [search_response([hit("chunk-2", 1), hit("chunk-1", 2)])],
    )

    result = service.retrieve("No alias question", document_id="doc-1")

    assert result.retrieval_reason == "baseline_only_no_variants"
    assert result.alias_retrieval_applied is False
    assert result.vector_search_call_count == 1
    assert [item.chunk_id for item in result.baseline_results] == ["chunk-2", "chunk-1"]
    assert [item.chunk_id for item in result.fused_results] == ["chunk-2", "chunk-1"]
    search.search.assert_called_once_with("No alias question", document_id="doc-1", top_k=10)


def test_strong_alias_retrieval_uses_topks_weights_and_rrf():
    trace = trace_with_variants([
        variant(0, "original", "What did Mr. Holmes discover?"),
        variant(1, "strong_single", "What did Sherlock Holmes discover?"),
    ])
    service, search = service_for(
        trace,
        [
            search_response([hit("chunk-1", 1), hit("chunk-2", 2)]),
            search_response([hit("chunk-2", 1), hit("chunk-3", 2)]),
        ],
    )

    result = service.retrieve("What did Mr. Holmes discover?", document_id="gutenberg-1661")

    assert [call.kwargs["top_k"] for call in search.search.call_args_list] == [10, 5]
    assert [call.kwargs["document_id"] for call in search.search.call_args_list] == ["gutenberg-1661", "gutenberg-1661"]
    assert result.variant_retrievals[1].variant_weight == 0.9
    chunk_2 = next(item for item in result.fused_results if item.chunk_id == "chunk-2")
    expected = 1.0 / (60 + 2) + 0.9 / (60 + 1)
    assert chunk_2.fusion_score == pytest.approx(expected)
    assert chunk_2.contributing_variant_count == 2
    assert [contrib.variant_index for contrib in chunk_2.contributions] == [0, 1]


def test_raw_similarity_does_not_drive_final_ranking():
    trace = trace_with_variants([
        variant(0, "original", "question"),
        variant(1, "strong_single", "variant one"),
        variant(2, "strong_single", "variant two"),
        variant(3, "strong_single", "variant three"),
    ])
    service, _ = service_for(
        trace,
        [
            search_response([]),
            search_response([hit("chunk-A", 5, similarity=0.95)]),
            search_response([hit("chunk-B", 1, similarity=0.70)]),
            search_response([hit("chunk-B", 2, similarity=0.70)]),
        ],
    )

    result = service.retrieve("question")

    assert result.fused_results[0].chunk_id == "chunk-B"


def test_duplicate_counts_and_rank_not_renumbered():
    trace = trace_with_variants([
        variant(0, "original", "question"),
        variant(1, "strong_single", "variant"),
    ])
    service, _ = service_for(
        trace,
        [
            search_response([hit("chunk-A", 1), hit("chunk-A", 2), hit("chunk-B", 3)]),
            search_response([hit("chunk-B", 1)]),
        ],
    )

    result = service.retrieve("question")

    assert result.backend_raw_hit_count == 4
    assert result.normalized_hit_count == 3
    assert result.intra_variant_duplicate_count == 1
    assert result.cross_variant_duplicate_occurrence_count == 1
    assert result.duplicate_chunk_occurrence_count == 2
    original_hits = result.variant_retrievals[0].hits
    assert [(item.chunk_id, item.rank) for item in original_hits] == [("chunk-A", 1), ("chunk-B", 3)]


def test_alias_only_candidate_and_final_top_k():
    trace = trace_with_variants([
        variant(0, "original", "question"),
        variant(1, "strong_single", "variant"),
    ])
    original_hits = [hit(f"base-{idx}", idx) for idx in range(1, 11)]
    alias_hits = [hit("alias-only", 1), hit("base-10", 2)]
    service, _ = service_for(trace, [search_response(original_hits), search_response(alias_hits)])

    result = service.retrieve("question")

    assert result.final_result_count == 10
    alias_only = next(item for item in result.fused_results if item.chunk_id == "alias-only")
    assert alias_only.alias_only_candidate is True
    assert alias_only.appeared_in_original_query is False


def test_invariant_failures():
    config = ExpandedRetrievalConfig(max_variants=8)
    too_many = [variant(0, "original", "q")] + [variant(idx, "strong_single", f"v{idx}") for idx in range(1, 9)]
    service, _ = service_for(trace_with_variants(too_many), [])
    with pytest.raises(ExpandedRetrievalError, match="more variants"):
        service.retrieve("q")

    duplicate_id = trace_with_variants([variant(0, "original", "q"), variant(1, "strong_single", "v", "original")])
    service, _ = service_for(duplicate_id, [], config)
    with pytest.raises(ExpandedRetrievalError, match="duplicate variant_id"):
        service.retrieve("q")

    unknown_kind = trace_with_variants([variant(0, "original", "q"), variant(1, "mystery", "v")])
    service, _ = service_for(unknown_kind, [], config)
    with pytest.raises(ExpandedRetrievalError, match="unknown variant_kind"):
        service.retrieve("q")


def test_failure_modes_strict_and_non_strict():
    trace = trace_with_variants([variant(0, "original", "q"), variant(1, "strong_single", "v")])
    strict_service, _ = service_for(trace, [search_response([hit("chunk-1", 1)]), RuntimeError("db url secret")])
    with pytest.raises(ExpandedRetrievalError):
        strict_service.retrieve("q")

    non_strict_service, _ = service_for(
        trace,
        [search_response([hit("chunk-1", 1)]), RuntimeError("db url secret")],
        ExpandedRetrievalConfig(strict_variant_failures=False),
    )
    result = non_strict_service.retrieve("q")
    assert result.failed_variant_count == 1
    assert result.variant_retrievals[1].error_code == "vector_search_failed"
    assert "secret" not in result.variant_retrievals[1].error_message


def test_retrieval_disabled_skips_alias_variants_but_keeps_expansion_trace():
    trace = trace_with_variants([variant(0, "original", "q"), variant(1, "strong_single", "v")])
    service, search = service_for(trace, [search_response([hit("chunk-1", 1)])], ExpandedRetrievalConfig(enabled=False))

    result = service.retrieve("q")

    assert result.retrieval_reason == "baseline_only_retrieval_disabled"
    assert result.skipped_variant_count == 1
    assert result.alias_retrieval_applied is False
    assert result.vector_search_call_count == 1
    search.search.assert_called_once()


def test_metadata_conflict_strict_and_non_strict():
    trace = trace_with_variants([variant(0, "original", "q"), variant(1, "strong_single", "v")])
    responses = [
        search_response([hit("chunk-1", 1, section_title="Original", text="same")]),
        search_response([hit("chunk-1", 1, section_title="Alias", text="same")]),
    ]
    strict_service, _ = service_for(trace, responses)
    with pytest.raises(ExpandedRetrievalError, match="metadata conflict"):
        strict_service.retrieve("q")

    non_strict_service, _ = service_for(trace, responses, ExpandedRetrievalConfig(strict_variant_failures=False))
    result = non_strict_service.retrieve("q")
    assert result.metadata_conflict_count == 1
    assert result.fused_results[0].section_title == "Original"


def test_api_retrieve_serializes_trace():
    service = MagicMock(spec=ExpandedRetrievalService)
    real_service, _ = service_for(
        trace_with_variants([variant(0, "original", "question")], reason="no_alias_mentions"),
        [search_response([hit("chunk-1", 1)])],
    )
    service.retrieve.return_value = real_service.retrieve("question")
    app.dependency_overrides[get_expanded_retrieval_service] = lambda: service
    try:
        client = TestClient(app)
        response = client.post("/api/aliases/retrieve", json={"query": "question", "document_id": "doc-1"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["retrieval_reason"] == "baseline_only_no_variants"
        assert payload["baseline_results"][0]["chunk_id"] == "chunk-1"
        service.retrieve.assert_called_once()
    finally:
        app.dependency_overrides.clear()
