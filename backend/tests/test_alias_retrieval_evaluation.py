import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.evaluation.alias_retrieval.corpus import compute_corpus_content_sha256
from app.evaluation.alias_retrieval.dataset import (
    AliasEvaluationDataset,
    DatasetManifest,
    validate_dataset,
)
from app.evaluation.alias_retrieval.metrics import compare_modes, compute_retrieval_metrics
from app.evaluation.alias_retrieval.runner import run_alias_retrieval_evaluation
from app.services.expanded_retrieval_service import (
    ExpandedRetrievalConfig,
    ExpandedRetrievalTrace,
    FusedChunkResult,
    VariantRetrievalHit,
    VariantRetrievalResult,
)
from app.services.query_expansion_service import QueryExpansionConfig, QueryExpansionTrace, QueryVariant


def test_corpus_hash_is_order_independent_and_content_sensitive():
    chunks = [
        {"chunk_id": "b", "section_order": 1, "chunk_order": 2, "text": "Beta"},
        {"chunk_id": "a", "section_order": 1, "chunk_order": 1, "text": "Alpha"},
    ]
    reversed_chunks = list(reversed(chunks))
    assert compute_corpus_content_sha256(chunks) == compute_corpus_content_sha256(reversed_chunks)

    changed = [dict(chunks[0], text="Different"), chunks[1]]
    assert compute_corpus_content_sha256(chunks) != compute_corpus_content_sha256(changed)


def test_metrics_alternative_chunks_new_chunk_and_new_group():
    question = _question(
        gold=[
            {"evidence_group_id": "g1", "description": "one", "alternative_chunk_uids": ["a1", "a2"]},
            {"evidence_group_id": "g2", "description": "two", "alternative_chunk_uids": ["b1"]},
        ]
    )
    baseline = compute_retrieval_metrics(question, ["a1", "x"])
    expanded = compute_retrieval_metrics(question, ["a2", "b1"])

    assert baseline.evidence_group_recall_at_10 == 0.5
    assert expanded.evidence_group_recall_at_10 == 1.0
    assert expanded.complete_evidence_at_10 is True
    assert expanded.completion_rank == 2
    comparison = compare_modes(question, baseline, expanded)
    assert comparison.comparison_category == "rescued"
    assert comparison.new_gold_chunk_uids == ("a2", "b1")
    assert comparison.newly_covered_evidence_group_ids == ("g2",)


def test_comparison_coverage_mixed_blocks_rank_comparison():
    question = _question(
        gold=[
            {"evidence_group_id": "a", "description": "A", "alternative_chunk_uids": ["a1"]},
            {"evidence_group_id": "b", "description": "B", "alternative_chunk_uids": ["b1"]},
        ]
    )
    baseline = compute_retrieval_metrics(question, ["a1"])
    expanded = compute_retrieval_metrics(question, ["b1"])

    assert compare_modes(question, baseline, expanded).comparison_category == "coverage_mixed"


def test_dataset_validation_fails_unknown_chunk_and_alias_group():
    dataset = AliasEvaluationDataset.model_validate(
        {
            "dataset_id": "d",
            "document_id": "doc",
            "questions": [
                {
                    "question_id": "q1",
                    "split": "legacy_regression",
                    "category": "entity_alias",
                    "question": "Question?",
                    "reference_answer": "Answer.",
                    "gold_evidence_groups": [
                        {"evidence_group_id": "e1", "description": "Evidence", "alternative_chunk_uids": ["missing"]}
                    ],
                    "expected_alias_group_ids": ["missing-group"],
                }
            ],
        }
    )
    manifest = DatasetManifest(
        dataset_version="v",
        annotation_status="seed",
        legacy_question_count=1,
        alias_challenge_question_count=0,
        negative_control_count=0,
        official_evaluation_ready=False,
    )
    registry = MagicMock()
    registry.snapshot.groups = ()

    with pytest.raises(ValueError, match="unknown gold chunk uid"):
        validate_dataset(dataset, manifest=manifest, known_chunk_uids=set(), alias_registry=registry)


def test_runner_derives_baseline_from_expanded_modes_without_extra_search(tmp_path):
    questions_path, chunks_path = _write_dataset(tmp_path)
    service = FakeRetrievalService()
    registry = _registry()

    result = run_alias_retrieval_evaluation(
        questions_path=questions_path,
        output_root=tmp_path / "runs",
        modes=("baseline", "strong_only", "strong_story"),
        run_id="run-1",
        chunks_path=chunks_path,
        alias_registry=registry,
        retrieval_service=service,
    )

    assert result.run_status == "completed"
    assert result.retrieval_execution_count == 2
    assert [call["allow_story"] for call in service.calls] == [True, False]
    final_dir = tmp_path / "runs" / "run-1"
    rows = [json.loads(line) for line in (final_dir / "question_results.jsonl").read_text().splitlines()]
    assert rows[0]["mode_results"][0]["mode"] == "baseline"
    assert (final_dir / "traces" / "q1_strong_story.json").exists()


def test_runner_baseline_only_executes_once(tmp_path):
    questions_path, chunks_path = _write_dataset(tmp_path)
    service = FakeRetrievalService()

    result = run_alias_retrieval_evaluation(
        questions_path=questions_path,
        output_root=tmp_path / "runs",
        modes=("baseline",),
        run_id="baseline-only",
        chunks_path=chunks_path,
        alias_registry=_registry(),
        retrieval_service=service,
    )

    assert result.retrieval_execution_count == 1
    assert service.calls[0]["enabled"] is False


def test_runner_strong_only_invariant_fails_and_does_not_publish_completed(tmp_path):
    questions_path, chunks_path = _write_dataset(tmp_path)
    service = FakeRetrievalService(strong_only_story_variant=True)

    with pytest.raises(ValueError, match="story-scoped variants"):
        run_alias_retrieval_evaluation(
            questions_path=questions_path,
            output_root=tmp_path / "runs",
            modes=("strong_only",),
            run_id="bad-run",
            chunks_path=chunks_path,
            alias_registry=_registry(),
            retrieval_service=service,
        )

    assert not (tmp_path / "runs" / "bad-run").exists()
    assert (tmp_path / "runs" / "bad-run_failed").exists()


def test_runner_existing_run_id_is_not_overwritten(tmp_path):
    questions_path, chunks_path = _write_dataset(tmp_path)
    output = tmp_path / "runs"
    (output / "same").mkdir(parents=True)

    with pytest.raises(FileExistsError):
        run_alias_retrieval_evaluation(
            questions_path=questions_path,
            output_root=output,
            modes=("baseline",),
            run_id="same",
            chunks_path=chunks_path,
            alias_registry=_registry(),
            retrieval_service=FakeRetrievalService(),
        )


class FakeRetrievalService:
    def __init__(self, *, strong_only_story_variant: bool = False) -> None:
        self.calls = []
        self._config = ExpandedRetrievalConfig()
        self._query_expansion_service = MagicMock()
        self._query_expansion_service._config = QueryExpansionConfig()
        self.strong_only_story_variant = strong_only_story_variant

    def retrieve(self, query, *, document_id, expansion_options=None):
        allow_story = expansion_options is None or expansion_options.allow_story_scoped is not False
        enabled = expansion_options is None or expansion_options.enabled is not False
        self.calls.append({"query": query, "document_id": document_id, "allow_story": allow_story, "enabled": enabled})
        if not enabled:
            variants = [_variant(0, "original", query)]
            reason = "expansion_disabled"
        elif allow_story:
            variants = [_variant(0, "original", query), _variant(1, "story_scoped_single", "Alias")]
            reason = "aliases_expanded"
        elif self.strong_only_story_variant:
            variants = [_variant(0, "original", query), _variant(1, "story_scoped_single", "Bad")]
            reason = "aliases_expanded"
        else:
            variants = [_variant(0, "original", query), _variant(1, "strong_single", "Strong")]
            reason = "aliases_expanded"
        return _trace(query, document_id, variants, reason)


def _question(gold):
    return _question_dataset(gold=gold).questions[0]


def _question_dataset(gold=None):
    return AliasEvaluationDataset.model_validate(
        {
            "dataset_id": "d",
            "document_id": "doc",
            "questions": [
                {
                    "question_id": "q1",
                    "split": "legacy_regression",
                    "category": "entity_alias",
                    "question": "Question?",
                    "reference_answer": "Answer.",
                    "gold_evidence_groups": gold
                    or [{"evidence_group_id": "e1", "description": "Evidence", "alternative_chunk_uids": ["chunk-1"]}],
                    "expected_alias_group_ids": ["group-1"],
                    "expected_query_mentions": ["Question"],
                }
            ],
        }
    )


def _write_dataset(tmp_path: Path):
    dataset = _question_dataset()
    qpath = tmp_path / "questions.json"
    mpath = tmp_path / "dataset_manifest.json"
    cpath = tmp_path / "chunks.jsonl"
    qpath.write_text(json.dumps(dataset.model_dump(mode="json")), encoding="utf-8")
    mpath.write_text(
        json.dumps(
            {
                "dataset_version": "v",
                "annotation_status": "seed",
                "legacy_question_count": 1,
                "alias_challenge_question_count": 0,
                "negative_control_count": 0,
                "official_evaluation_ready": False,
            }
        ),
        encoding="utf-8",
    )
    cpath.write_text(
        json.dumps({"chunk_id": "chunk-1", "section_order": 1, "chunk_order": 1, "text": "Evidence"}) + "\n",
        encoding="utf-8",
    )
    return qpath, cpath


def _registry():
    group = MagicMock()
    group.group_id = "group-1"
    registry = MagicMock()
    registry.snapshot.groups = (group,)
    registry.snapshot.sha256 = "alias-sha"
    return registry


def _variant(idx: int, kind: str, text: str):
    return QueryVariant(
        variant_id="original" if idx == 0 else f"v{idx}",
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


def _hit(chunk_id: str, rank: int):
    return VariantRetrievalHit(
        chunk_id=chunk_id,
        document_id="doc",
        chunk_text=f"Text {chunk_id}",
        rank=rank,
        section_order=1,
        section_title="Section",
        chunk_order=rank,
    )


def _variant_result(variant: QueryVariant, hits):
    return VariantRetrievalResult(
        variant_id=variant.variant_id,
        variant_index=variant.variant_index,
        variant_kind=variant.variant_kind,
        query_text=variant.query_text,
        variant_weight=1.0,
        requested_top_k=10 if variant.variant_index == 0 else 5,
        backend_raw_hit_count=len(hits),
        hits=tuple(hits),
        search_duration_ms=1.0,
        total_duration_ms=1.0,
        success=True,
    )


def _fused(chunk_id: str, rank: int):
    hit = _hit(chunk_id, rank)
    return FusedChunkResult(
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        chunk_text=hit.chunk_text,
        final_rank=rank,
        fusion_score=1.0 / rank,
        contributing_variant_count=1,
        contributions=(),
        appeared_in_original_query=True,
        original_query_rank=rank,
        best_individual_rank=rank,
        best_variant_id="original",
        best_variant_rank=rank,
        alias_only_candidate=False,
    )


def _trace(query: str, document_id: str, variants, reason: str):
    expansion = QueryExpansionTrace(
        original_query=query,
        normalized_query=query.casefold(),
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
    baseline_hits = (_hit("chunk-1", 1),)
    variant_results = tuple(_variant_result(variant, baseline_hits if variant.variant_index == 0 else [_hit("chunk-2", 1)]) for variant in variants)
    return ExpandedRetrievalTrace(
        original_query=query,
        document_id=document_id,
        alias_dataset_sha256="alias-sha",
        expansion_config_snapshot=QueryExpansionConfig(),
        retrieval_config_snapshot=ExpandedRetrievalConfig(),
        expansion_trace=expansion,
        variant_retrievals=variant_results,
        baseline_results=baseline_hits,
        fused_results=(_fused("chunk-1", 1), _fused("chunk-2", 2)) if len(variants) > 1 else (_fused("chunk-1", 1),),
        total_variant_count=len(variants),
        successful_variant_count=len(variants),
        failed_variant_count=0,
        skipped_variant_count=0,
        backend_raw_hit_count=len(variant_results),
        normalized_hit_count=len(variant_results),
        intra_variant_duplicate_count=0,
        unique_candidate_chunk_count=len(variant_results),
        cross_variant_duplicate_occurrence_count=0,
        duplicate_chunk_occurrence_count=0,
        final_result_count=2,
        embedding_input_count=len(variant_results),
        embedding_call_count=None,
        vector_search_call_count=len(variant_results),
        metadata_conflict_count=0,
        validation_warnings=(),
        expansion_duration_ms=1.0,
        retrieval_duration_ms=1.0,
        fusion_duration_ms=1.0,
        total_duration_ms=3.0,
        alias_retrieval_applied=len(variants) > 1,
        retrieval_reason="alias_expanded_retrieval" if len(variants) > 1 else "baseline_only_no_variants",
    )

