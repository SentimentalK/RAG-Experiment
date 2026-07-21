import logging
import os
import re
import subprocess
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.evaluation.alias_retrieval.corpus import compute_corpus_content_sha256, load_chunks_jsonl
from app.repositories.experiment_repository import ExperimentPersistenceError, ExperimentRepository
from app.schemas.experiments import (
    ExperimentCompareResponse,
    ExperimentContextRecord,
    ExperimentModeResult,
    ExperimentRetrievalSummary,
    ExperimentSessionDetail,
    ExperimentSessionSummary,
    ExperimentTiming,
    ExperimentalAnswerResponse,
    ModeComparisonSummary,
    RetrievalMode,
)
from app.services.alias_registry import AliasRegistry
from app.services.answer_generation_service import AnswerContext, AnswerGenerationService, GeneratedAnswer, normalized_answer_text
from app.services.expanded_retrieval_service import ExpandedRetrievalTrace, FusedChunkResult, VariantRetrievalHit
from app.services.query_expansion_service import QueryExpansionRequestOptions


logger = logging.getLogger("app.services.experimental_answer")


class ExperimentalAnswerError(RuntimeError):
    def __init__(self, error_code: str, message: str, *, session_id: UUID | None = None, failed_mode: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.session_id = session_id
        self.failed_mode = failed_mode


class ExperimentalAnswerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    persistence_enabled: bool = True
    persistence_required: bool = False
    persistence_strict: bool = True
    persist_full_trace: bool = True

    @classmethod
    def from_settings(cls, app_settings: Any) -> "ExperimentalAnswerConfig":
        return cls(
            persistence_enabled=app_settings.EXPERIMENT_PERSISTENCE_ENABLED,
            persistence_required=app_settings.EXPERIMENT_PERSISTENCE_REQUIRED,
            persistence_strict=app_settings.EXPERIMENT_PERSISTENCE_STRICT,
            persist_full_trace=app_settings.EXPERIMENT_PERSIST_FULL_TRACE,
        )


@dataclass(frozen=True)
class ExecutionPlan:
    requested_modes: tuple[RetrievalMode, ...]
    retrieval_modes: tuple[RetrievalMode, ...]
    baseline_source_mode: RetrievalMode | None
    persist_baseline_run: bool


@dataclass
class WorkItem:
    mode: RetrievalMode
    mode_run_id: UUID | None
    trace: ExpandedRetrievalTrace | None = None
    contexts: tuple[AnswerContext, ...] = ()
    context_records: tuple[ExperimentContextRecord, ...] = ()
    answer: GeneratedAnswer | None = None
    retrieval_executed: bool = True
    retrieval_source_mode: RetrievalMode | None = None
    retrieval_source_mode_run_id: UUID | None = None
    retrieval_duration_ms: float | None = None
    total_duration_ms: float | None = None
    status: str = "pending"
    error_code: str | None = None
    error_message: str | None = None


class ExperimentalAnswerService:
    def __init__(
        self,
        *,
        alias_registry: AliasRegistry,
        expanded_retrieval_service: Any,
        answer_generation_service: AnswerGenerationService,
        experiment_repository: ExperimentRepository,
        config: ExperimentalAnswerConfig,
    ) -> None:
        self._alias_registry = alias_registry
        self._expanded_retrieval_service = expanded_retrieval_service
        self._answer_generation_service = answer_generation_service
        self._repository = experiment_repository
        self._config = config

    def answer(
        self,
        *,
        query: str,
        mode: RetrievalMode,
        document_id: str = "gutenberg-1661",
        expansion_options: QueryExpansionRequestOptions | None = None,
        persist: bool = True,
        include_trace: bool = False,
    ) -> ExperimentalAnswerResponse:
        comparison = self.compare(
            query=query,
            modes=(mode,),
            document_id=document_id,
            expansion_options=expansion_options,
            persist=persist,
            include_trace=include_trace,
        )
        result = comparison.results[mode]
        return ExperimentalAnswerResponse(
            session_id=comparison.session_id,
            mode_run_id=result.mode_run_id,
            persisted=comparison.persisted,
            query=query,
            mode=mode,
            result=result,
            warnings=comparison.warnings,
        )

    def compare(
        self,
        *,
        query: str,
        modes: tuple[RetrievalMode, ...],
        document_id: str = "gutenberg-1661",
        expansion_options: QueryExpansionRequestOptions | None = None,
        persist: bool = True,
        include_trace: bool = False,
    ) -> ExperimentCompareResponse:
        plan = build_execution_plan(modes)
        persist_effective = self._resolve_persistence(persist)
        session_id: UUID | None = None
        warnings: list[str] = []
        started = perf_counter()
        work: dict[RetrievalMode, WorkItem] = {mode: WorkItem(mode=mode, mode_run_id=None) for mode in plan.requested_modes}

        try:
            if persist_effective:
                try:
                    session_id = self._create_session(query, plan.requested_modes, document_id)
                    for mode in plan.requested_modes:
                        work[mode].mode_run_id = self._repository.create_mode_run(session_id=session_id, mode=mode)
                except ExperimentalAnswerError:
                    if self._config.persistence_strict:
                        raise
                    logger.warning("Persistence initialization failed; continuing without persistence", exc_info=True)
                    warnings.append("Experiment persistence failed; result was not persisted.")
                    persist_effective = False
                    session_id = None

            traces: dict[RetrievalMode, ExpandedRetrievalTrace] = {}
            retrieval_execution_count = 0
            vector_search_call_count = 0
            for mode in plan.retrieval_modes:
                try:
                    trace = self._execute_retrieval(query, mode, document_id, expansion_options)
                except ExperimentalAnswerError as exc:
                    if mode in work:
                        work[mode].status = "failed"
                        work[mode].error_code = exc.error_code
                        work[mode].error_message = str(exc)
                        if persist_effective and work[mode].mode_run_id is not None:
                            self._repository.save_mode_failed(
                                mode_run_id=work[mode].mode_run_id,
                                error_code=exc.error_code,
                                error_message=str(exc),
                            )
                    raise
                traces[mode] = trace
                retrieval_execution_count += 1
                vector_search_call_count += trace.vector_search_call_count
                if mode in work:
                    self._populate_retrieved_work_item(work[mode], trace, mode, persist_effective)

            if "strong_story" in traces and "strong_only" in traces:
                _validate_baseline_parity(traces["strong_story"], traces["strong_only"])

            if "baseline" in work and "baseline" not in traces:
                source_mode = plan.baseline_source_mode
                if source_mode is None or source_mode not in traces:
                    raise ExperimentalAnswerError("retrieval_source_failed", "Baseline source retrieval failed.", session_id=session_id, failed_mode="baseline")
                baseline_item = work["baseline"]
                source_item = work[source_mode]
                baseline_item.retrieval_executed = False
                baseline_item.retrieval_source_mode = source_mode
                baseline_item.retrieval_source_mode_run_id = source_item.mode_run_id
                self._populate_baseline_from_trace(baseline_item, traces[source_mode], persist_effective)
            elif "baseline" in traces and "baseline" in work:
                self._populate_retrieved_work_item(work["baseline"], traces["baseline"], "baseline", persist_effective)

            answer_generation_count = 0
            for mode in plan.requested_modes:
                item = work[mode]
                if item.status == "failed":
                    continue
                self._generate_answer_for_item(query, item, persist_effective)
                answer_generation_count += 1

            completed = [item for item in work.values() if item.status == "completed"]
            failed = [item for item in work.values() if item.status == "failed"]
            status = _session_status(completed_count=len(completed), failed_count=len(failed), requested_count=len(work))
            if status != "completed":
                first_failed = failed[0] if failed else None
                raise ExperimentalAnswerError(
                    first_failed.error_code or "experiment_failed" if first_failed else "experiment_failed",
                    first_failed.error_message or "Experiment failed." if first_failed else "Experiment failed.",
                    session_id=session_id,
                    failed_mode=first_failed.mode if first_failed else None,
                )

            if persist_effective and session_id is not None:
                self._finalize_session(
                    session_id,
                    status=status,
                    retrieval_execution_count=retrieval_execution_count,
                    answer_generation_count=answer_generation_count,
                    vector_search_call_count=vector_search_call_count,
                )

            results = {mode: _mode_result(item, include_trace=include_trace) for mode, item in work.items()}
            comparisons = _comparisons(results)
            logger.info(
                "Experimental answer completed session_id=%s modes=%s query_length=%s retrievals=%s answers=%s persisted=%s total_ms=%.2f",
                session_id,
                ",".join(plan.requested_modes),
                len(query),
                retrieval_execution_count,
                answer_generation_count,
                persist_effective,
                (perf_counter() - started) * 1000,
            )
            return ExperimentCompareResponse(
                session_id=session_id,
                persisted=persist_effective,
                query=query,
                status=status,
                results=results,
                comparisons=comparisons,
                requested_mode_count=len(plan.requested_modes),
                retrieval_execution_count=retrieval_execution_count,
                answer_generation_count=answer_generation_count,
                total_vector_search_call_count=vector_search_call_count,
                warnings=tuple(warnings),
            )
        except ExperimentalAnswerError as exc:
            if persist_effective and session_id is not None:
                self._safe_finalize_failed_session(session_id, work, exc.error_code, str(exc))
            raise
        except Exception as exc:
            logger.exception("Experimental answer failed")
            if persist_effective and session_id is not None:
                self._safe_finalize_failed_session(session_id, work, "experiment_failed", "Experimental answer failed.")
            raise ExperimentalAnswerError("experiment_failed", "Experimental answer failed.", session_id=session_id) from exc

    def list_sessions(self, **kwargs) -> list[ExperimentSessionSummary]:
        return [_session_summary(row) for row in self._repository.list_sessions(**kwargs)]

    def get_session_detail(self, session_id: UUID) -> ExperimentSessionDetail | None:
        session = self._repository.get_session(session_id)
        if session is None:
            return None
        modes = tuple(_mode_result_from_row(row, include_trace=False, include_context_text=False) for row in self._repository.list_mode_runs_for_session(session_id))
        return ExperimentSessionDetail(
            session=_session_summary(session),
            modes=modes,
            alias_dataset_sha256=session["alias_dataset_sha256"],
            corpus_content_sha256=session.get("corpus_content_sha256"),
            git_commit=session.get("git_commit"),
            query_expansion_config=session["query_expansion_config"],
            retrieval_config=session["retrieval_config"],
            generation_config=session["generation_config"],
        )

    def get_mode_run_detail(self, mode_run_id: UUID, *, include_trace: bool = False, include_context_text: bool = False) -> ExperimentModeResult | None:
        row = self._repository.get_mode_run(mode_run_id)
        if row is None:
            return None
        return _mode_result_from_row(row, include_trace=include_trace, include_context_text=include_context_text)

    def _resolve_persistence(self, persist_requested: bool) -> bool:
        if not self._config.persistence_enabled:
            return False
        if self._config.persistence_required and not persist_requested:
            raise ExperimentalAnswerError("persistence_required", "Experiment persistence is required by server configuration.")
        return persist_requested

    def _create_session(self, query: str, modes: tuple[RetrievalMode, ...], document_id: str) -> UUID:
        try:
            return self._repository.create_session(
                query_text=query,
                requested_modes=modes,
                alias_dataset_sha256=self._alias_registry.snapshot.sha256,
                corpus_content_sha256=_corpus_hash(document_id),
                git_commit=_git_commit(),
                metadata_warnings=[],
                embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                vector_metric="exact_cosine",
                answer_model=self._answer_generation_service.generation_config()["model"],
                answer_provider="groq",
                query_expansion_config=self._expanded_retrieval_service._query_expansion_service._config.model_dump(mode="json"),
                retrieval_config=self._expanded_retrieval_service._config.model_dump(mode="json"),
                generation_config=self._answer_generation_service.generation_config(),
                prompt_template_sha256=self._answer_generation_service.prompt_template_sha256(),
            )
        except Exception as exc:
            raise ExperimentalAnswerError("experiment_persistence_failed", "Experiment persistence failed.") from exc

    def _execute_retrieval(
        self,
        query: str,
        mode: RetrievalMode,
        document_id: str,
        expansion_options: QueryExpansionRequestOptions | None,
    ) -> ExpandedRetrievalTrace:
        try:
            if mode == "baseline":
                options = QueryExpansionRequestOptions(enabled=False)
            elif mode == "strong_only":
                options = _merge_expansion_options(expansion_options, allow_story_scoped=False)
            else:
                options = expansion_options
            trace = self._expanded_retrieval_service.retrieve(query, document_id=document_id, expansion_options=options)
            if mode == "strong_only":
                _validate_strong_only_trace(trace)
            return trace
        except ExperimentalAnswerError:
            raise
        except Exception as exc:
            raise ExperimentalAnswerError("retrieval_failed", "Experimental retrieval failed.", failed_mode=mode) from exc

    def _populate_retrieved_work_item(
        self,
        item: WorkItem,
        trace: ExpandedRetrievalTrace,
        mode: RetrievalMode,
        persist_effective: bool,
    ) -> None:
        item.trace = trace
        item.retrieval_executed = True
        item.retrieval_duration_ms = trace.retrieval_duration_ms
        if mode == "baseline":
            item.contexts, item.context_records = _contexts_from_baseline(trace.baseline_results)
        else:
            item.contexts, item.context_records = _contexts_from_fused(trace.fused_results)
        item.status = "retrieval_completed"
        if persist_effective and item.mode_run_id is not None:
            self._repository.mark_mode_running(item.mode_run_id)
            self._persist_retrieval(item, trace)

    def _populate_baseline_from_trace(
        self,
        item: WorkItem,
        trace: ExpandedRetrievalTrace,
        persist_effective: bool,
    ) -> None:
        item.trace = trace
        item.contexts, item.context_records = _contexts_from_baseline(trace.baseline_results)
        item.retrieval_duration_ms = 0.0
        item.status = "retrieval_completed"
        if persist_effective and item.mode_run_id is not None:
            self._repository.mark_mode_running(item.mode_run_id)
            self._persist_retrieval(item, trace, derived=True)

    def _persist_retrieval(self, item: WorkItem, trace: ExpandedRetrievalTrace, derived: bool = False) -> None:
        prompt_snapshot = tuple(_prompt_snapshot_from_context(context) for context in item.contexts)
        context_hash = item.answer.context_snapshot_sha256 if item.answer else _json_hash(prompt_snapshot)
        retrieval_summary = _retrieval_summary(trace, item, derived=derived)
        retrieval_trace = None
        expansion_trace = None
        if self._config.persist_full_trace and not derived:
            retrieval_trace = trace.model_dump(mode="json")
            expansion_trace = trace.expansion_trace.model_dump(mode="json")
        elif derived:
            retrieval_trace = {
                "trace_type": "derived_baseline",
                "source_mode_run_id": str(item.retrieval_source_mode_run_id) if item.retrieval_source_mode_run_id else None,
                "retrieval_summary": retrieval_summary,
            }
        self._repository.save_mode_retrieval_completed(
            mode_run_id=item.mode_run_id,
            retrieval_reason=trace.retrieval_reason,
            generated_variant_count=0 if derived else trace.total_variant_count,
            vector_search_call_count=0 if derived else trace.vector_search_call_count,
            final_context_count=len(item.contexts),
            retrieval_duration_ms=item.retrieval_duration_ms,
            context_chunk_uids=tuple(context.chunk_uid for context in item.contexts),
            context_records=tuple(record.model_dump(mode="json") for record in item.context_records),
            prompt_context_snapshot=prompt_snapshot,
            context_snapshot_sha256=context_hash,
            expansion_trace=expansion_trace,
            retrieval_trace=retrieval_trace,
            retrieval_summary=retrieval_summary,
        )

    def _generate_answer_for_item(self, query: str, item: WorkItem, persist_effective: bool) -> None:
        start = perf_counter()
        try:
            answer = self._answer_generation_service.generate(query, item.contexts)
            item.answer = answer
            item.status = "completed"
            item.total_duration_ms = (perf_counter() - start) * 1000 + (item.retrieval_duration_ms or 0.0)
            if persist_effective and item.mode_run_id is not None:
                self._repository.save_mode_completed(
                    mode_run_id=item.mode_run_id,
                    answer_text=answer.answer_text,
                    answer_payload=answer.model_dump(mode="json"),
                    generation_duration_ms=answer.generation_duration_ms,
                    total_duration_ms=item.total_duration_ms,
                    prompt_template_sha256=answer.prompt_template_sha256,
                    rendered_prompt_sha256=answer.rendered_prompt_sha256,
                    input_token_count=answer.input_token_count,
                    output_token_count=answer.output_token_count,
                )
        except Exception as exc:
            item.status = "failed"
            item.error_code = "answer_generation_failed"
            item.error_message = "Answer generation failed."
            if persist_effective and item.mode_run_id is not None:
                self._repository.save_mode_failed(
                    mode_run_id=item.mode_run_id,
                    error_code=item.error_code,
                    error_message=item.error_message,
                )
            raise ExperimentalAnswerError(item.error_code, item.error_message, failed_mode=item.mode) from exc

    def _finalize_session(
        self,
        session_id: UUID,
        *,
        status: str,
        retrieval_execution_count: int,
        answer_generation_count: int,
        vector_search_call_count: int,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self._repository.finalize_session(
            session_id=session_id,
            status=status,
            retrieval_execution_count=retrieval_execution_count,
            answer_generation_count=answer_generation_count,
            total_vector_search_call_count=vector_search_call_count,
            error_code=error_code,
            error_message=error_message,
        )

    def _safe_finalize_failed_session(self, session_id: UUID, work: dict[RetrievalMode, WorkItem], error_code: str, error_message: str) -> None:
        try:
            completed_count = sum(1 for item in work.values() if item.status == "completed")
            failed_count = sum(1 for item in work.values() if item.status == "failed")
            status = _session_status(completed_count=completed_count, failed_count=failed_count or 1, requested_count=len(work))
            self._finalize_session(
                session_id,
                status=status,
                retrieval_execution_count=sum(1 for item in work.values() if item.retrieval_executed and item.trace is not None),
                answer_generation_count=completed_count,
                vector_search_call_count=sum((item.trace.vector_search_call_count if item.retrieval_executed and item.trace else 0) for item in work.values()),
                error_code=error_code,
                error_message=error_message,
            )
        except Exception:
            logger.exception("Failed to finalize failed experiment session safely")


def build_execution_plan(modes: tuple[RetrievalMode, ...]) -> ExecutionPlan:
    requested = tuple(dict.fromkeys(modes))
    if not requested:
        raise ExperimentalAnswerError("invalid_retrieval_mode", "At least one retrieval mode is required.")
    if set(requested) == {"baseline"}:
        return ExecutionPlan(requested, ("baseline",), "baseline", True)
    retrieval_modes: list[RetrievalMode] = []
    if "strong_story" in requested:
        retrieval_modes.append("strong_story")
    if "strong_only" in requested:
        retrieval_modes.append("strong_only")
    baseline_source = "strong_story" if "strong_story" in retrieval_modes else "strong_only"
    return ExecutionPlan(requested, tuple(retrieval_modes), baseline_source, "baseline" in requested)


def _merge_expansion_options(
    options: QueryExpansionRequestOptions | None,
    *,
    allow_story_scoped: bool,
) -> QueryExpansionRequestOptions:
    data = options.model_dump(exclude_unset=True) if options else {}
    data["allow_story_scoped"] = allow_story_scoped
    return QueryExpansionRequestOptions(**data)


def _validate_strong_only_trace(trace: ExpandedRetrievalTrace) -> None:
    forbidden = {"story_scoped_single", "mixed"}
    kinds = {variant.variant_kind for variant in trace.expansion_trace.generated_variants}
    if kinds & forbidden:
        raise ExperimentalAnswerError("invalid_retrieval_trace", "Strong-only trace contains story-scoped variants.")


def _validate_baseline_parity(left: ExpandedRetrievalTrace, right: ExpandedRetrievalTrace) -> None:
    left_rows = [(hit.chunk_id, hit.rank, hit.document_id) for hit in left.baseline_results]
    right_rows = [(hit.chunk_id, hit.rank, hit.document_id) for hit in right.baseline_results]
    if left_rows != right_rows:
        raise ExperimentalAnswerError("baseline_parity_failed", "Baseline parity mismatch between expanded modes.")


def _contexts_from_baseline(hits: tuple[VariantRetrievalHit, ...]) -> tuple[tuple[AnswerContext, ...], tuple[ExperimentContextRecord, ...]]:
    contexts: list[AnswerContext] = []
    records: list[ExperimentContextRecord] = []
    for rank, hit in enumerate(hits[:10], start=1):
        contexts.append(
            AnswerContext(
                chunk_uid=hit.chunk_id,
                rank=rank,
                chunk_text=hit.chunk_text,
                section_title=hit.section_title or "",
                cosine_similarity=hit.raw_similarity or 0.0,
                cosine_distance=hit.raw_distance,
                document_id=hit.document_id,
                section_id=hit.section_id,
                section_order=hit.section_order,
                chunk_index=hit.chunk_order,
                chunk_order=hit.chunk_order,
            )
        )
        records.append(_record_from_answer_context(contexts[-1], alias_only_candidate=False))
    return tuple(contexts), tuple(records)


def _contexts_from_fused(results: tuple[FusedChunkResult, ...]) -> tuple[tuple[AnswerContext, ...], tuple[ExperimentContextRecord, ...]]:
    contexts: list[AnswerContext] = []
    records: list[ExperimentContextRecord] = []
    for rank, item in enumerate(sorted(results, key=lambda result: result.final_rank)[:10], start=1):
        best_contrib = item.contributions[0] if item.contributions else None
        contexts.append(
            AnswerContext(
                chunk_uid=item.chunk_id,
                rank=rank,
                chunk_text=item.chunk_text,
                section_title=item.section_title or "",
                cosine_similarity=(best_contrib.raw_similarity if best_contrib else 0.0) or 0.0,
                cosine_distance=best_contrib.raw_distance if best_contrib else None,
                document_id=item.document_id,
                section_id=item.section_id,
                section_order=item.section_order,
                chunk_index=item.chunk_order,
                chunk_order=item.chunk_order,
            )
        )
        records.append(_record_from_answer_context(contexts[-1], alias_only_candidate=item.alias_only_candidate))
    return tuple(contexts), tuple(records)


def _record_from_answer_context(context: AnswerContext, *, alias_only_candidate: bool) -> ExperimentContextRecord:
    return ExperimentContextRecord(
        rank=context.rank,
        chunk_uid=context.chunk_uid,
        section_title=context.section_title,
        chunk_text=context.chunk_text,
        raw_similarity=context.cosine_similarity,
        raw_distance=context.cosine_distance,
        document_id=context.document_id,
        section_id=context.section_id,
        section_order=context.section_order,
        chunk_index=context.chunk_index,
        chunk_order=context.chunk_order,
        token_count=context.token_count,
        alias_only_candidate=alias_only_candidate,
    )


def _prompt_snapshot_from_context(context: AnswerContext) -> dict[str, Any]:
    return {
        "rank": context.rank,
        "chunk_uid": context.chunk_uid,
        "section_title": context.section_title,
        "cosine_similarity": context.cosine_similarity,
        "chunk_text": context.chunk_text,
    }


def _mode_result(item: WorkItem, *, include_trace: bool) -> ExperimentModeResult:
    answer = item.answer
    contexts = item.context_records
    trace_payload = None
    if include_trace and item.trace is not None and item.retrieval_executed:
        trace_payload = item.trace.model_dump(mode="json")
    return ExperimentModeResult(
        mode=item.mode,
        mode_run_id=item.mode_run_id,
        status=item.status,  # type: ignore[arg-type]
        answer=answer.answer_text if answer else None,
        evidence_sufficient=answer.evidence_sufficient if answer else None,
        confidence=answer.confidence if answer else None,
        contexts=contexts,
        context_chunk_uids=tuple(context.chunk_uid for context in item.contexts),
        context_snapshot_sha256=answer.context_snapshot_sha256 if answer else (_json_hash(tuple(_prompt_snapshot_from_context(c) for c in item.contexts)) if item.contexts else None),
        prompt_template_sha256=answer.prompt_template_sha256 if answer else None,
        rendered_prompt_sha256=answer.rendered_prompt_sha256 if answer else None,
        retrieval_summary=ExperimentRetrievalSummary(
            retrieval_reason=item.trace.retrieval_reason if item.trace else None,
            generated_variant_count=0 if not item.retrieval_executed else (item.trace.total_variant_count if item.trace else 0),
            vector_search_call_count=0 if not item.retrieval_executed else (item.trace.vector_search_call_count if item.trace else 0),
            final_context_count=len(item.contexts),
            retrieval_executed=item.retrieval_executed,
            retrieval_source_mode=item.retrieval_source_mode,
        ),
        timing=ExperimentTiming(
            retrieval_duration_ms=item.retrieval_duration_ms,
            generation_duration_ms=answer.generation_duration_ms if answer else None,
            total_duration_ms=item.total_duration_ms,
        ),
        trace=trace_payload,
        error_code=item.error_code,
        error_message=item.error_message,
    )


def _mode_result_from_row(row: dict[str, Any], *, include_trace: bool, include_context_text: bool) -> ExperimentModeResult:
    answer_payload = row.get("answer_payload") or {}
    contexts = []
    for record in row.get("context_records") or []:
        payload = dict(record)
        if not include_context_text:
            payload["chunk_text"] = None
        contexts.append(ExperimentContextRecord.model_validate(payload))
    trace_payload = row.get("retrieval_trace") if include_trace else None
    return ExperimentModeResult(
        mode=row["mode"],
        mode_run_id=row["id"],
        status=row["status"],
        answer=row.get("answer_text"),
        evidence_sufficient=answer_payload.get("evidence_sufficient"),
        confidence=answer_payload.get("confidence"),
        contexts=tuple(contexts),
        context_chunk_uids=tuple(row.get("context_chunk_uids") or []),
        context_snapshot_sha256=row.get("context_snapshot_sha256"),
        prompt_template_sha256=row.get("prompt_template_sha256"),
        rendered_prompt_sha256=row.get("rendered_prompt_sha256"),
        retrieval_summary=ExperimentRetrievalSummary(
            retrieval_reason=row.get("retrieval_reason"),
            generated_variant_count=row.get("generated_variant_count") or 0,
            vector_search_call_count=row.get("vector_search_call_count") or 0,
            final_context_count=row.get("final_context_count") or 0,
            retrieval_executed=row.get("retrieval_executed"),
            retrieval_source_mode=row.get("retrieval_source_mode"),
        ),
        timing=ExperimentTiming(
            retrieval_duration_ms=row.get("retrieval_duration_ms"),
            generation_duration_ms=row.get("generation_duration_ms"),
            total_duration_ms=row.get("total_duration_ms"),
        ),
        trace=trace_payload,
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
    )


def _session_summary(row: dict[str, Any]) -> ExperimentSessionSummary:
    return ExperimentSessionSummary(
        session_id=row["id"],
        query=row["query_text"],
        requested_modes=tuple(row["requested_modes"]),
        status=row["status"],
        started_at=row["started_at"],
        completed_at=row.get("completed_at"),
        requested_mode_count=row.get("requested_mode_count") or len(row["requested_modes"]),
        retrieval_execution_count=row.get("retrieval_execution_count") or 0,
        answer_generation_count=row.get("answer_generation_count") or 0,
        total_vector_search_call_count=row.get("total_vector_search_call_count") or 0,
    )


def _comparisons(results: dict[RetrievalMode, ExperimentModeResult]) -> tuple[ModeComparisonSummary, ...]:
    if "baseline" not in results:
        return ()
    baseline = results["baseline"]
    comparisons = []
    for mode, result in results.items():
        if mode == "baseline":
            continue
        comparisons.append(_compare_contexts(baseline, result))
    return tuple(comparisons)


def _compare_contexts(baseline: ExperimentModeResult, compared: ExperimentModeResult) -> ModeComparisonSummary:
    baseline_set = set(baseline.context_chunk_uids)
    compared_set = set(compared.context_chunk_uids)
    shared = baseline_set & compared_set
    new = compared_set - baseline_set
    displaced = baseline_set - compared_set
    union = baseline_set | compared_set
    jaccard = 1.0 if not union else len(shared) / len(union)
    alias_only = sum(1 for context in compared.contexts if context.alias_only_candidate)
    warnings = []
    if alias_only != len(new):
        warnings.append("alias_only_context_count differs from set-based new_context_count")
    return ModeComparisonSummary(
        baseline_mode="baseline",
        compared_mode=compared.mode,
        shared_context_count=len(shared),
        new_context_count=len(new),
        displaced_context_count=len(displaced),
        context_jaccard_at_10=jaccard,
        new_chunk_uids=tuple(sorted(new)),
        displaced_chunk_uids=tuple(sorted(displaced)),
        alias_only_context_count=alias_only,
        answer_text_equal=(baseline.answer or "") == (compared.answer or ""),
        answer_text_normalized_equal=normalized_answer_text(baseline.answer or "") == normalized_answer_text(compared.answer or ""),
        validation_warnings=tuple(warnings),
    )


def _retrieval_summary(trace: ExpandedRetrievalTrace, item: WorkItem, *, derived: bool) -> dict[str, Any]:
    return {
        "trace_type": "derived_baseline" if derived else "expanded_retrieval",
        "retrieval_reason": trace.retrieval_reason,
        "generated_variant_count": 0 if derived else trace.total_variant_count,
        "vector_search_call_count": 0 if derived else trace.vector_search_call_count,
        "final_context_count": len(item.contexts),
        "retrieval_executed": item.retrieval_executed,
        "retrieval_source_mode": item.retrieval_source_mode,
        "retrieval_source_mode_run_id": str(item.retrieval_source_mode_run_id) if item.retrieval_source_mode_run_id else None,
    }


def _session_status(*, completed_count: int, failed_count: int, requested_count: int) -> str:
    if completed_count == requested_count and failed_count == 0:
        return "completed"
    if completed_count > 0 and failed_count > 0:
        return "partial"
    if completed_count == 0 and failed_count > 0:
        return "failed"
    return "running"


def _json_hash(value: Any) -> str:
    import hashlib
    import json

    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _corpus_hash(document_id: str) -> str | None:
    try:
        chunks = load_chunks_jsonl(settings.PROCESSED_DATA_DIR / "chunks.jsonl")
        return compute_corpus_content_sha256(chunks, document_id)
    except Exception:
        logger.warning("Unable to compute corpus content hash", exc_info=True)
        return None


def _git_commit() -> str | None:
    if os.environ.get("GIT_COMMIT_SHA"):
        return os.environ["GIT_COMMIT_SHA"]
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None
