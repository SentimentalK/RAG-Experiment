import subprocess
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.evaluation.alias_retrieval.artifacts import (
    AtomicRunPublisher,
    file_sha256,
    validate_run_artifacts,
    write_csv,
    write_json,
    write_jsonl,
)
from app.evaluation.alias_retrieval.corpus import compute_corpus_content_sha256, load_chunks_jsonl
from app.evaluation.alias_retrieval.dataset import (
    AliasEvaluationQuestion,
    load_dataset_manifest,
    load_evaluation_dataset,
    validate_dataset,
)
from app.evaluation.alias_retrieval.metrics import (
    ModeComparison,
    RetrievalGoldMetrics,
    chunk_ids_from_results,
    compare_modes,
    compute_retrieval_metrics,
)
from app.providers.minilm_provider import MiniLMProvider
from app.services.alias_registry import AliasRegistry
from app.services.expanded_retrieval_service import ExpandedRetrievalConfig, ExpandedRetrievalService, ExpandedRetrievalTrace
from app.services.query_expansion_service import QueryExpansionConfig, QueryExpansionRequestOptions, QueryExpansionService
from app.services.vector_search_service import VectorSearchService


EvaluationMode = Literal["baseline", "strong_only", "strong_story"]


class ModeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: EvaluationMode
    metrics: RetrievalGoldMetrics
    comparison_to_baseline: ModeComparison | None = None
    trace_path: str | None = None
    trace_sha256: str | None = None
    trace_schema_version: str | None = None
    retrieval_reason: str
    alias_retrieval_applied: bool
    vector_search_call_count: int
    generated_variant_kinds: tuple[str, ...]


class QuestionEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str
    split: str
    category: str
    mode_results: tuple[ModeResult, ...]
    expected_mention_detected: bool | None
    missing_expected_mentions: tuple[str, ...]
    unexpected_detected_mentions: tuple[str, ...]
    expected_alias_groups_activated: tuple[str, ...]
    warnings: tuple[str, ...]


class AliasEvaluationRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    run_status: str
    run_dir: str
    question_count: int
    retrieval_execution_count: int
    logical_mode_count: int
    failure_count: int


def run_alias_retrieval_evaluation(
    *,
    questions_path: Path,
    output_root: Path,
    modes: tuple[EvaluationMode, ...],
    run_id: str | None = None,
    require_official_dataset: bool = False,
    continue_on_question_error: bool = False,
    document_id: str | None = None,
    chunks_path: Path | None = None,
    alias_registry: AliasRegistry | None = None,
    retrieval_service: ExpandedRetrievalService | None = None,
) -> AliasEvaluationRunResult:
    started = datetime.now(timezone.utc)
    run_id = run_id or f"alias_eval_{started.strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    output_root = output_root.resolve()
    questions_path = questions_path.resolve()
    manifest_path = questions_path.parent / "dataset_manifest.json"
    chunks_path = (chunks_path or (settings.PROCESSED_DATA_DIR / "chunks.jsonl")).resolve()

    dataset = load_evaluation_dataset(questions_path)
    dataset_manifest = load_dataset_manifest(manifest_path)
    if require_official_dataset and not dataset_manifest.official_evaluation_ready:
        raise ValueError("Dataset is not marked official_evaluation_ready=true.")
    if set(modes) - {"baseline", "strong_only", "strong_story"}:
        raise ValueError(f"Unsupported mode(s): {modes}")
    if not modes:
        raise ValueError("At least one mode is required.")

    chunks = load_chunks_jsonl(chunks_path)
    known_chunk_uids = {chunk.get("chunk_uid") or chunk.get("chunk_id") for chunk in chunks}
    alias_registry = alias_registry or AliasRegistry.load(
        settings.ALIAS_DATASET_PATH,
        expected_sha256=settings.ALIAS_DATASET_EXPECTED_SHA256 or None,
        strict_validation=settings.ALIAS_DATASET_STRICT_VALIDATION,
    )
    validation = validate_dataset(
        dataset,
        manifest=dataset_manifest,
        known_chunk_uids=known_chunk_uids,
        alias_registry=alias_registry,
        strict=not continue_on_question_error,
    )
    retrieval_service = retrieval_service or _build_retrieval_service(alias_registry)
    doc_id = document_id or dataset.document_id

    result_rows: list[dict] = []
    csv_rows: list[dict] = []
    failures: list[dict] = []
    trace_refs: list[dict[str, str]] = []
    question_results: list[QuestionEvaluationResult] = []
    retrieval_execution_count = 0

    with AtomicRunPublisher(output_root, run_id) as run_dir:
        try:
            for question in sorted(dataset.questions, key=lambda item: item.question_id):
                try:
                    result, executions, refs = _evaluate_question(
                        question=question,
                        modes=modes,
                        retrieval_service=retrieval_service,
                        document_id=doc_id,
                        run_dir=run_dir,
                    )
                    retrieval_execution_count += executions
                    question_results.append(result)
                    trace_refs.extend(refs)
                    row = result.model_dump(mode="json")
                    result_rows.append(row)
                    csv_rows.extend(_flatten_question_result(result))
                except Exception as exc:
                    failures.append(
                        {
                            "question_id": question.question_id,
                            "error_code": "question_evaluation_failed",
                            "error_message": str(exc),
                        }
                    )
                    if not continue_on_question_error:
                        raise

            run_status = "completed" if not failures else "incomplete"
            summary = _summarize(question_results, modes)
            write_jsonl(run_dir / "question_results.jsonl", result_rows)
            write_json(run_dir / "summary.json", summary)
            write_csv(run_dir / "summary.csv", csv_rows)
            write_jsonl(run_dir / "failures.jsonl", failures)
            validate_run_artifacts(run_dir, trace_refs)
            manifest = _manifest(
                run_id=run_id,
                run_status=run_status,
                started_at=started,
                question_count=len(dataset.questions),
                questions_path=questions_path,
                chunks=chunks,
                chunks_path=chunks_path,
                dataset_manifest=dataset_manifest.model_dump(mode="json"),
                alias_registry=alias_registry,
                retrieval_service=retrieval_service,
                modes=modes,
                retrieval_execution_count=retrieval_execution_count,
                warnings=validation.warnings,
                failures=failures,
                document_id=doc_id,
            )
            write_json(run_dir / "manifest.json", manifest)
        except Exception:
            if not (run_dir / "manifest.json").exists():
                write_json(
                    run_dir / "manifest.json",
                    {
                        "run_id": run_id,
                        "run_status": "failed",
                        "started_at": started.isoformat(),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            raise

    return AliasEvaluationRunResult(
        run_id=run_id,
        run_status=run_status,
        run_dir=str(output_root / run_id),
        question_count=len(dataset.questions),
        retrieval_execution_count=retrieval_execution_count,
        logical_mode_count=len(dataset.questions) * len(modes),
        failure_count=len(failures),
    )


def _evaluate_question(
    *,
    question: AliasEvaluationQuestion,
    modes: tuple[EvaluationMode, ...],
    retrieval_service: ExpandedRetrievalService,
    document_id: str,
    run_dir: Path,
) -> tuple[QuestionEvaluationResult, int, list[dict[str, str]]]:
    traces: dict[EvaluationMode, ExpandedRetrievalTrace] = {}
    trace_refs: list[dict[str, str]] = []
    retrieval_executions = 0

    if "strong_story" in modes:
        trace = retrieval_service.retrieve(question.question, document_id=document_id)
        traces["strong_story"] = trace
        retrieval_executions += 1
        trace_refs.append(_write_trace(run_dir, question.question_id, "strong_story", trace))

    if "strong_only" in modes:
        trace = retrieval_service.retrieve(
            question.question,
            document_id=document_id,
            expansion_options=QueryExpansionRequestOptions(allow_story_scoped=False),
        )
        _validate_strong_only_trace(trace)
        if "strong_story" in traces:
            _validate_baseline_parity(traces["strong_story"], trace)
        traces["strong_only"] = trace
        retrieval_executions += 1
        trace_refs.append(_write_trace(run_dir, question.question_id, "strong_only", trace))

    if "baseline" in modes and not traces:
        trace = retrieval_service.retrieve(
            question.question,
            document_id=document_id,
            expansion_options=QueryExpansionRequestOptions(enabled=False),
        )
        traces["baseline"] = trace
        retrieval_executions += 1
        trace_refs.append(_write_trace(run_dir, question.question_id, "baseline", trace))

    baseline_source = traces.get("strong_story") or traces.get("strong_only") or traces["baseline"]
    baseline_metrics = compute_retrieval_metrics(question, chunk_ids_from_results(baseline_source.baseline_results))
    mode_results: list[ModeResult] = []
    if "baseline" in modes:
        ref = (
            next((item for item in trace_refs if item["mode"] == "baseline"), None)
            or next((item for item in trace_refs if item["mode"] == "strong_story"), None)
            or next((item for item in trace_refs if item["mode"] == "strong_only"), None)
        )
        mode_results.append(
            ModeResult(
                mode="baseline",
                metrics=baseline_metrics,
                retrieval_reason=baseline_source.retrieval_reason,
                alias_retrieval_applied=False,
                vector_search_call_count=1,
                generated_variant_kinds=tuple(variant.variant_kind for variant in baseline_source.expansion_trace.generated_variants),
                trace_path=ref["trace_path"] if ref else None,
                trace_sha256=ref["trace_sha256"] if ref else None,
                trace_schema_version=ref["trace_schema_version"] if ref else None,
            )
        )

    for mode in ("strong_only", "strong_story"):
        if mode in modes:
            trace = traces[mode]  # type: ignore[index]
            metrics = compute_retrieval_metrics(question, chunk_ids_from_results(trace.fused_results))
            ref = next(item for item in trace_refs if item["mode"] == mode)
            mode_results.append(
                ModeResult(
                    mode=mode,  # type: ignore[arg-type]
                    metrics=metrics,
                    comparison_to_baseline=compare_modes(question, baseline_metrics, metrics),
                    trace_path=ref["trace_path"],
                    trace_sha256=ref["trace_sha256"],
                    trace_schema_version=ref["trace_schema_version"],
                    retrieval_reason=trace.retrieval_reason,
                    alias_retrieval_applied=trace.alias_retrieval_applied,
                    vector_search_call_count=trace.vector_search_call_count,
                    generated_variant_kinds=tuple(variant.variant_kind for variant in trace.expansion_trace.generated_variants),
                )
            )

    diagnostics = _mention_diagnostics(question, tuple(traces.values()))
    return (
        QuestionEvaluationResult(
            question_id=question.question_id,
            split=question.split,
            category=question.category,
            mode_results=tuple(mode_results),
            warnings=(),
            **diagnostics,
        ),
        retrieval_executions,
        trace_refs,
    )


def _write_trace(run_dir: Path, question_id: str, mode: str, trace: ExpandedRetrievalTrace) -> dict[str, str]:
    relative = f"traces/{question_id}_{mode}.json"
    path = run_dir / relative
    write_json(path, trace.model_dump(mode="json"))
    return {
        "question_id": question_id,
        "mode": mode,
        "trace_path": relative,
        "trace_sha256": file_sha256(path),
        "trace_schema_version": "1",
    }


def _validate_strong_only_trace(trace: ExpandedRetrievalTrace) -> None:
    forbidden = {"story_scoped_single", "mixed"}
    kinds = {variant.variant_kind for variant in trace.expansion_trace.generated_variants}
    if kinds & forbidden:
        raise ValueError(f"Strong-only trace contains story-scoped variants: {sorted(kinds & forbidden)}")


def _validate_baseline_parity(left: ExpandedRetrievalTrace, right: ExpandedRetrievalTrace) -> None:
    left_rows = [(hit.chunk_id, hit.rank, hit.document_id) for hit in left.baseline_results]
    right_rows = [(hit.chunk_id, hit.rank, hit.document_id) for hit in right.baseline_results]
    if left_rows != right_rows:
        raise ValueError("Baseline parity mismatch between expanded modes")
    left_top_k = left.variant_retrievals[0].requested_top_k
    right_top_k = right.variant_retrievals[0].requested_top_k
    if left_top_k != right_top_k:
        raise ValueError("Baseline requested_top_k mismatch between expanded modes")


def _mention_diagnostics(question: AliasEvaluationQuestion, traces: tuple[ExpandedRetrievalTrace, ...]) -> dict:
    detected = {
        mention.original_text
        for trace in traces
        for mention in trace.expansion_trace.detected_mentions + trace.expansion_trace.blocked_mentions
    }
    activated = {
        mention.group_id
        for trace in traces
        for mention in trace.expansion_trace.selected_mentions
        if mention.group_id
    }
    expected_mentions = set(question.expected_query_mentions)
    expected_groups = set(question.expected_alias_group_ids)
    return {
        "expected_mention_detected": (expected_mentions <= detected) if expected_mentions else None,
        "missing_expected_mentions": tuple(sorted(expected_mentions - detected)),
        "unexpected_detected_mentions": tuple(sorted(detected - expected_mentions)),
        "expected_alias_groups_activated": tuple(sorted(expected_groups & activated)),
    }


def _flatten_question_result(result: QuestionEvaluationResult) -> list[dict]:
    rows: list[dict] = []
    for mode_result in result.mode_results:
        metrics = mode_result.metrics
        rows.append(
            {
                "question_id": result.question_id,
                "mode": mode_result.mode,
                "category": result.category,
                "split": result.split,
                "evidence_group_recall_at_10": metrics.evidence_group_recall_at_10,
                "complete_evidence_at_10": metrics.complete_evidence_at_10,
                "first_evidence_rank": metrics.first_evidence_rank,
                "completion_rank": metrics.completion_rank,
                "mrr_at_10": metrics.mrr_at_10,
                "contradictory_hit_at_10": metrics.contradictory_hit_at_10,
                "comparison_category": (
                    mode_result.comparison_to_baseline.comparison_category if mode_result.comparison_to_baseline else None
                ),
                "newly_covered_evidence_group_ids": (
                    list(mode_result.comparison_to_baseline.newly_covered_evidence_group_ids)
                    if mode_result.comparison_to_baseline
                    else []
                ),
            }
        )
    return rows


def _summarize(results: list[QuestionEvaluationResult], modes: tuple[EvaluationMode, ...]) -> dict:
    by_mode: dict[str, list[RetrievalGoldMetrics]] = defaultdict(list)
    comparison_counts: Counter[str] = Counter()
    for result in results:
        for mode_result in result.mode_results:
            by_mode[mode_result.mode].append(mode_result.metrics)
            if mode_result.comparison_to_baseline:
                comparison_counts[mode_result.comparison_to_baseline.comparison_category] += 1
    mode_summary = {}
    for mode, metrics in sorted(by_mode.items()):
        count = len(metrics)
        mode_summary[mode] = {
            "question_count": count,
            "mean_evidence_group_recall_at_10": _mean(item.evidence_group_recall_at_10 for item in metrics),
            "complete_evidence_rate_at_10": _mean(1.0 if item.complete_evidence_at_10 else 0.0 for item in metrics),
            "mrr_at_10": _mean(item.mrr_at_10 for item in metrics),
            "contradictory_hit_rate_at_10": _mean(1.0 if item.contradictory_hit_at_10 else 0.0 for item in metrics),
            "mean_contradictory_chunk_count_at_10": _mean(item.contradictory_chunk_count_at_10 for item in metrics),
        }
    return {
        "schema_version": "1",
        "logical_modes": list(modes),
        "mode_summary": mode_summary,
        "comparison_counts": dict(sorted(comparison_counts.items())),
    }


def _manifest(
    *,
    run_id: str,
    run_status: str,
    started_at: datetime,
    question_count: int,
    questions_path: Path,
    chunks: list[dict],
    chunks_path: Path,
    dataset_manifest: dict,
    alias_registry: AliasRegistry,
    retrieval_service: ExpandedRetrievalService,
    modes: tuple[EvaluationMode, ...],
    retrieval_execution_count: int,
    warnings: tuple[str, ...],
    failures: list[dict],
    document_id: str,
) -> dict:
    config = retrieval_service._config
    expansion_config = retrieval_service._query_expansion_service._config
    return {
        "schema_version": "1",
        "run_id": run_id,
        "run_status": run_status,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "question_count": question_count,
        "question_dataset_path": str(questions_path),
        "question_dataset_sha256": file_sha256(questions_path),
        "alias_dataset_sha256": alias_registry.snapshot.sha256,
        "corpus_content_sha256": compute_corpus_content_sha256(chunks, document_id),
        "chunk_count": len(chunks),
        "chunks_path": str(chunks_path),
        "document_id": document_id,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_metric": "exact_cosine",
        "effective_expansion_config": expansion_config.model_dump(mode="json"),
        "effective_retrieval_config": config.model_dump(mode="json"),
        "logical_modes": list(modes),
        "logical_mode_count": question_count * len(modes),
        "retrieval_execution_count": retrieval_execution_count,
        "dataset_readiness": dataset_manifest,
        "warmup_performed": False,
        "observed_latency_note": "Latency is descriptive only and should not be interpreted causally.",
        "validation_warnings": list(warnings),
        "failure_count": len(failures),
    }


def _build_retrieval_service(alias_registry: AliasRegistry) -> ExpandedRetrievalService:
    expansion_service = QueryExpansionService(
        alias_registry=alias_registry,
        config=QueryExpansionConfig.from_settings(settings),
    )
    provider = MiniLMProvider()
    search_service = VectorSearchService(provider)
    return ExpandedRetrievalService(
        alias_registry=alias_registry,
        query_expansion_service=expansion_service,
        vector_search_service=search_service,
        config=ExpandedRetrievalConfig.from_settings(settings),
    )


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def _mean(values) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0
