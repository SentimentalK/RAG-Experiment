import json
from uuid import uuid4

import pytest

from app.schemas.experiments import ExperimentContextRecord
from app.services.answer_generation_service import GeneratedAnswer
from app.services.experimental_answer_service import (
    ExperimentalAnswerConfig,
    ExperimentalAnswerError,
    ExperimentalAnswerService,
    build_execution_plan,
)
from app.services.expanded_retrieval_service import (
    ExpandedRetrievalConfig,
    ExpandedRetrievalTrace,
    FusedChunkResult,
    VariantRetrievalHit,
    VariantRetrievalResult,
)
from app.services.query_expansion_service import QueryExpansionConfig, QueryExpansionTrace, QueryVariant
from app.schemas.rag_answer import Citation, TokenUsage


@pytest.mark.parametrize(
    ("modes", "retrieval_modes", "baseline_source"),
    [
        (("baseline",), ("baseline",), "baseline"),
        (("baseline", "strong_only"), ("strong_only",), "strong_only"),
        (("baseline", "strong_story"), ("strong_story",), "strong_story"),
        (("strong_only", "strong_story"), ("strong_story", "strong_only"), "strong_story"),
        (("baseline", "strong_only", "strong_story"), ("strong_story", "strong_only"), "strong_story"),
    ],
)
def test_execution_plan_matrix(modes, retrieval_modes, baseline_source):
    plan = build_execution_plan(modes)
    assert plan.retrieval_modes == retrieval_modes
    assert plan.baseline_source_mode == baseline_source


def test_compare_all_modes_reuses_baseline_and_accounts_costs():
    service, retrieval, answer, repo = service_for()

    result = service.compare(
        query="Why did Hosmer Angel disappear?",
        modes=("baseline", "strong_only", "strong_story"),
        persist=True,
    )

    assert result.status == "completed"
    assert result.retrieval_execution_count == 2
    assert result.answer_generation_count == 3
    assert [call["mode"] for call in retrieval.calls] == ["strong_story", "strong_only"]
    assert len(answer.calls) == 3
    baseline = result.results["baseline"]
    assert baseline.retrieval_summary.retrieval_executed is False
    assert baseline.retrieval_summary.vector_search_call_count == 0
    assert baseline.retrieval_summary.retrieval_source_mode == "strong_story"
    assert repo.mode_rows["baseline"]["retrieval_executed"] is False
    assert repo.mode_rows["baseline"]["vector_search_call_count"] == 0
    assert repo.finalized["retrieval_execution_count"] == 2
    assert repo.finalized["answer_generation_count"] == 3


def test_strong_only_story_variant_fails_with_safe_code():
    service, retrieval, _, _ = service_for(story_variant_in_strong_only=True)

    with pytest.raises(ExperimentalAnswerError) as exc:
        service.compare(query="Question", modes=("strong_only",), persist=False)

    assert exc.value.error_code == "invalid_retrieval_trace"


def test_persistence_required_rejects_persist_false():
    service, _, _, _ = service_for(config=ExperimentalAnswerConfig(persistence_required=True))

    with pytest.raises(ExperimentalAnswerError) as exc:
        service.compare(query="Question", modes=("baseline",), persist=False)

    assert exc.value.error_code == "persistence_required"


def test_capabilities_disable_persistence_when_schema_is_missing():
    service, _, _, repo = service_for()
    repo.schema_ready = False

    capabilities = service.get_capabilities()

    assert capabilities.persistence.enabled is False
    assert capabilities.persistence.required is False


def test_answer_generation_failure_preserves_retrieved_contexts():
    service, _, answer, _ = service_for(answer_fail_modes={"strong_story"})

    result = service.compare(query="Question", modes=("baseline", "strong_story"), persist=False)

    assert result.status == "partial"
    assert result.answer_generation_count == 1
    assert result.results["strong_story"].status == "failed"
    assert result.results["strong_story"].answer is None
    assert result.results["strong_story"].contexts
    assert result.results["strong_story"].error_code == "answer_generation_failed"
    assert "strong_story" in result.warnings[0]
    assert len(answer.calls) == 2


def test_comparison_metrics_use_chunk_sets_and_answer_equality():
    service, _, _, _ = service_for()

    result = service.compare(query="Question", modes=("baseline", "strong_story"), persist=False)
    comparison = result.comparisons[0]

    assert comparison.shared_context_count == 1
    assert comparison.new_context_count == 1
    assert comparison.displaced_context_count == 0
    assert comparison.context_jaccard_at_10 == pytest.approx(0.5)
    assert comparison.answer_text_equal is True
    assert comparison.answer_text_normalized_equal is True


def test_read_api_defaults_hide_trace_and_context_text():
    service, _, _, repo = service_for()
    response = service.compare(query="Question", modes=("baseline",), persist=True)

    detail = service.get_mode_run_detail(response.results["baseline"].mode_run_id)

    assert detail.trace is None
    assert detail.contexts[0].chunk_text is None


class FakeRetrievalService:
    def __init__(self, *, story_variant_in_strong_only=False):
        self.calls = []
        self._config = ExpandedRetrievalConfig()
        self._query_expansion_service = type("Expansion", (), {"_config": QueryExpansionConfig()})()
        self.story_variant_in_strong_only = story_variant_in_strong_only

    def retrieve(self, query, *, document_id, expansion_options=None):
        if expansion_options and expansion_options.enabled is False:
            mode = "baseline"
        elif expansion_options and expansion_options.allow_story_scoped is False:
            mode = "strong_only"
        else:
            mode = "strong_story"
        self.calls.append({"mode": mode, "document_id": document_id})
        if mode == "baseline":
            variants = [_variant(0, "original", query)]
        elif mode == "strong_only":
            kind = "story_scoped_single" if self.story_variant_in_strong_only else "strong_single"
            variants = [_variant(0, "original", query), _variant(1, kind, "Strong variant")]
        else:
            variants = [_variant(0, "original", query), _variant(1, "story_scoped_single", "Story variant")]
        return _trace(query, document_id, variants)


class FakeAnswerGenerationService:
    def __init__(self, fail_modes=None):
        self.calls = []
        self.fail_modes = set(fail_modes or ())

    def generation_config(self):
        return {"model": "test-model", "temperature": 0.0}

    def prompt_template_sha256(self):
        return "template-sha"

    def generate(self, question, contexts):
        self.calls.append({"question": question, "contexts": contexts})
        chunk_ids = {context.chunk_uid for context in contexts}
        inferred_mode = "strong_story" if "alias" in chunk_ids else "baseline"
        if inferred_mode in self.fail_modes:
            raise RuntimeError("Invalid model response")
        return GeneratedAnswer(
            answer_text="Same answer.",
            evidence_sufficient=True,
            citations=(Citation(chunk_uid=contexts[0].chunk_uid, reason="Evidence."),),
            confidence=0.9,
            model_name="test-model",
            provider="groq",
            prompt_template_sha256="template-sha",
            rendered_prompt_sha256="rendered-sha",
            context_snapshot_sha256="context-sha-" + "-".join(context.chunk_uid for context in contexts),
            prompt_context_snapshot=tuple({"rank": c.rank, "chunk_uid": c.chunk_uid, "section_title": c.section_title, "cosine_similarity": c.cosine_similarity, "chunk_text": c.chunk_text} for c in contexts),
            context_records=tuple(),
            input_token_count=10,
            output_token_count=5,
            generation_duration_ms=12.0,
            attempt_count=1,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            generation_config=self.generation_config(),
        )


class FakeRepo:
    def __init__(self):
        self.session_id = uuid4()
        self.mode_ids = {}
        self.mode_rows = {}
        self.finalized = {}
        self.schema_ready = True

    def experiment_schema_ready(self):
        return self.schema_ready

    def create_session(self, **kwargs):
        self.session = kwargs
        return self.session_id

    def create_mode_run(self, *, session_id, mode, retrieval_executed=True, retrieval_source_mode=None, retrieval_source_mode_run_id=None):
        mode_id = uuid4()
        self.mode_ids[mode] = mode_id
        self.mode_rows[mode] = {
            "id": mode_id,
            "session_id": session_id,
            "mode": mode,
            "status": "pending",
            "retrieval_executed": retrieval_executed,
            "retrieval_source_mode": retrieval_source_mode,
            "retrieval_source_mode_run_id": retrieval_source_mode_run_id,
            "context_records": [],
            "context_chunk_uids": [],
            "retrieval_summary": {},
        }
        return mode_id

    def mark_mode_running(self, mode_run_id):
        self._row(mode_run_id)["status"] = "running"

    def save_mode_retrieval_completed(self, *, mode_run_id, **kwargs):
        row = self._row(mode_run_id)
        row.update(kwargs)
        row["status"] = "retrieval_completed"
        row["retrieval_executed"] = kwargs["retrieval_summary"]["retrieval_executed"]

    def save_mode_completed(self, *, mode_run_id, **kwargs):
        row = self._row(mode_run_id)
        row.update(kwargs)
        row["status"] = "completed"

    def save_mode_failed(self, *, mode_run_id, error_code, error_message):
        row = self._row(mode_run_id)
        row["status"] = "failed"
        row["error_code"] = error_code
        row["error_message"] = error_message

    def finalize_session(self, **kwargs):
        self.finalized = kwargs

    def get_mode_run(self, mode_run_id):
        return self._row(mode_run_id)

    def _row(self, mode_run_id):
        return next(row for row in self.mode_rows.values() if row["id"] == mode_run_id)


def service_for(*, story_variant_in_strong_only=False, config=None, answer_fail_modes=None):
    registry = type("Registry", (), {"snapshot": type("Snapshot", (), {"sha256": "alias-sha"})()})()
    retrieval = FakeRetrievalService(story_variant_in_strong_only=story_variant_in_strong_only)
    answer = FakeAnswerGenerationService(fail_modes=answer_fail_modes)
    repo = FakeRepo()
    service = ExperimentalAnswerService(
        alias_registry=registry,
        expanded_retrieval_service=retrieval,
        answer_generation_service=answer,
        experiment_repository=repo,
        config=config or ExperimentalAnswerConfig(),
    )
    return service, retrieval, answer, repo


def _variant(idx, kind, text):
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


def _hit(chunk_id, rank):
    return VariantRetrievalHit(
        chunk_id=chunk_id,
        document_id="doc",
        section_title="Section",
        section_order=1,
        chunk_order=rank,
        chunk_text=f"Text {chunk_id}",
        rank=rank,
        raw_similarity=0.5,
        raw_distance=0.5,
    )


def _variant_result(variant, hits):
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


def _fused(chunk_id, rank, alias_only=False):
    return FusedChunkResult(
        chunk_id=chunk_id,
        document_id="doc",
        section_title="Section",
        section_order=1,
        chunk_order=rank,
        chunk_text=f"Text {chunk_id}",
        final_rank=rank,
        fusion_score=1.0 / rank,
        contributing_variant_count=1,
        contributions=(),
        appeared_in_original_query=not alias_only,
        original_query_rank=None if alias_only else rank,
        best_individual_rank=rank,
        best_variant_id="v1" if alias_only else "original",
        best_variant_rank=rank,
        alias_only_candidate=alias_only,
    )


def _trace(query, document_id, variants):
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
        expansion_applied=len(variants) > 1,
        expansion_reason="aliases_expanded" if len(variants) > 1 else "expansion_disabled",
    )
    baseline_hits = (_hit("base", 1),)
    variant_results = tuple(_variant_result(v, baseline_hits if v.variant_index == 0 else [_hit("alias", 1)]) for v in variants)
    fused = (_fused("base", 1), _fused("alias", 2, alias_only=True)) if len(variants) > 1 else (_fused("base", 1),)
    return ExpandedRetrievalTrace(
        original_query=query,
        document_id=document_id,
        alias_dataset_sha256="alias-sha",
        expansion_config_snapshot=QueryExpansionConfig(),
        retrieval_config_snapshot=ExpandedRetrievalConfig(),
        expansion_trace=expansion,
        variant_retrievals=variant_results,
        baseline_results=baseline_hits,
        fused_results=fused,
        total_variant_count=len(variants),
        successful_variant_count=len(variants),
        failed_variant_count=0,
        skipped_variant_count=0,
        backend_raw_hit_count=len(variants),
        normalized_hit_count=len(variants),
        intra_variant_duplicate_count=0,
        unique_candidate_chunk_count=len(variants),
        cross_variant_duplicate_occurrence_count=0,
        duplicate_chunk_occurrence_count=0,
        final_result_count=len(fused),
        embedding_input_count=len(variants),
        embedding_call_count=None,
        vector_search_call_count=len(variants),
        metadata_conflict_count=0,
        validation_warnings=(),
        expansion_duration_ms=1.0,
        retrieval_duration_ms=2.0,
        fusion_duration_ms=1.0,
        total_duration_ms=4.0,
        alias_retrieval_applied=len(variants) > 1,
        retrieval_reason="alias_expanded_retrieval" if len(variants) > 1 else "baseline_only_expansion_disabled",
    )
