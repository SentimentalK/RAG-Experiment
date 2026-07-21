import logging
import math
from collections import defaultdict
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.alias_registry import AliasRegistry
from app.services.query_expansion_service import (
    QueryExpansionConfig,
    QueryExpansionRequestOptions,
    QueryExpansionService,
    QueryExpansionTrace,
    QueryVariant,
)
from app.services.vector_search_service import VectorSearchService


logger = logging.getLogger("app.services.expanded_retrieval")
KNOWN_VARIANT_KINDS = {"original", "strong_single", "strong_multi", "story_scoped_single", "mixed"}


class ExpandedRetrievalError(RuntimeError):
    """Raised when expanded retrieval cannot produce a valid trace."""


class ExpandedRetrievalConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    original_top_k: int = 10
    variant_top_k: int = 5
    final_top_k: int = 10
    rrf_k: int = 60
    original_weight: float = 1.0
    strong_single_weight: float = 0.9
    strong_multi_weight: float = 0.85
    story_scoped_single_weight: float = 0.75
    mixed_weight: float = 0.7
    max_variants: int = 8
    strict_variant_failures: bool = True

    @classmethod
    def from_settings(cls, settings: Any) -> "ExpandedRetrievalConfig":
        return cls(
            enabled=settings.ALIAS_RETRIEVAL_ENABLED,
            original_top_k=settings.ALIAS_RETRIEVAL_ORIGINAL_TOP_K,
            variant_top_k=settings.ALIAS_RETRIEVAL_VARIANT_TOP_K,
            final_top_k=settings.ALIAS_RETRIEVAL_FINAL_TOP_K,
            rrf_k=settings.ALIAS_RETRIEVAL_RRF_K,
            original_weight=settings.ALIAS_RETRIEVAL_ORIGINAL_WEIGHT,
            strong_single_weight=settings.ALIAS_RETRIEVAL_STRONG_SINGLE_WEIGHT,
            strong_multi_weight=settings.ALIAS_RETRIEVAL_STRONG_MULTI_WEIGHT,
            story_scoped_single_weight=settings.ALIAS_RETRIEVAL_STORY_SCOPED_SINGLE_WEIGHT,
            mixed_weight=settings.ALIAS_RETRIEVAL_MIXED_WEIGHT,
            max_variants=settings.ALIAS_RETRIEVAL_MAX_VARIANTS,
            strict_variant_failures=settings.ALIAS_RETRIEVAL_STRICT_VARIANT_FAILURES,
        )

    @field_validator("original_top_k", "variant_top_k", "final_top_k", "max_variants")
    @classmethod
    def positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be positive")
        return value

    @field_validator("rrf_k")
    @classmethod
    def non_negative_rrf_k(cls, value: int) -> int:
        if value < 0:
            raise ValueError("rrf_k must be non-negative")
        return value

    @model_validator(mode="after")
    def finite_positive_weights(self) -> "ExpandedRetrievalConfig":
        for value in self.variant_weights().values():
            if not math.isfinite(value) or value <= 0:
                raise ValueError("variant weights must be finite positive numbers")
        return self

    def variant_weights(self) -> dict[str, float]:
        return {
            "original": self.original_weight,
            "strong_single": self.strong_single_weight,
            "strong_multi": self.strong_multi_weight,
            "story_scoped_single": self.story_scoped_single_weight,
            "mixed": self.mixed_weight,
        }


class VariantRetrievalHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str | None = None
    story_id: str | None = None
    section_id: str | None = None
    section_title: str | None = None
    section_order: int | None = None
    chunk_order: int | None = None
    chunk_text: str
    rank: int
    raw_similarity: float | None = None
    raw_distance: float | None = None


class VariantRetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    variant_index: int
    variant_kind: str
    query_text: str
    variant_weight: float
    requested_top_k: int
    backend_raw_hit_count: int = 0
    intra_variant_duplicate_count: int = 0
    hits: tuple[VariantRetrievalHit, ...] = ()
    embedding_duration_ms: float | None = None
    search_duration_ms: float
    total_duration_ms: float
    success: bool
    error_code: str | None = None
    error_message: str | None = None


class ChunkContribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    variant_index: int
    variant_kind: str
    query_text: str
    variant_weight: float
    rank: int
    rrf_contribution: float
    raw_similarity: float | None = None
    raw_distance: float | None = None


class FusedChunkResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_id: str | None = None
    story_id: str | None = None
    section_id: str | None = None
    section_title: str | None = None
    section_order: int | None = None
    chunk_order: int | None = None
    chunk_text: str
    final_rank: int
    fusion_score: float
    contributing_variant_count: int
    contributions: tuple[ChunkContribution, ...]
    appeared_in_original_query: bool
    original_query_rank: int | None
    best_individual_rank: int
    best_variant_id: str
    best_variant_rank: int
    alias_only_candidate: bool


class ExpandedRetrievalTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    original_query: str
    document_id: str
    alias_dataset_sha256: str
    expansion_config_snapshot: QueryExpansionConfig
    retrieval_config_snapshot: ExpandedRetrievalConfig
    expansion_trace: QueryExpansionTrace
    variant_retrievals: tuple[VariantRetrievalResult, ...]
    baseline_results: tuple[VariantRetrievalHit, ...]
    fused_results: tuple[FusedChunkResult, ...]
    total_variant_count: int
    successful_variant_count: int
    failed_variant_count: int
    skipped_variant_count: int
    backend_raw_hit_count: int
    normalized_hit_count: int
    intra_variant_duplicate_count: int
    unique_candidate_chunk_count: int
    cross_variant_duplicate_occurrence_count: int
    duplicate_chunk_occurrence_count: int
    final_result_count: int
    embedding_input_count: int
    embedding_call_count: int | None
    vector_search_call_count: int
    metadata_conflict_count: int
    validation_warnings: tuple[str, ...]
    expansion_duration_ms: float
    retrieval_duration_ms: float
    fusion_duration_ms: float
    total_duration_ms: float
    alias_retrieval_applied: bool
    retrieval_reason: str


class ExpandedRetrievalService:
    def __init__(
        self,
        *,
        alias_registry: AliasRegistry,
        query_expansion_service: QueryExpansionService,
        vector_search_service: VectorSearchService,
        config: ExpandedRetrievalConfig,
    ) -> None:
        self._alias_registry = alias_registry
        self._query_expansion_service = query_expansion_service
        self._vector_search_service = vector_search_service
        self._config = config

    def retrieve(
        self,
        query: str,
        *,
        document_id: str = "gutenberg-1661",
        expansion_options: QueryExpansionRequestOptions | None = None,
    ) -> ExpandedRetrievalTrace:
        total_start = perf_counter()
        expansion_start = perf_counter()
        expansion_trace = self._query_expansion_service.expand(query, config_override=expansion_options)
        expansion_duration_ms = _elapsed_ms(expansion_start)
        _validate_expansion_trace(expansion_trace, self._config)

        variants = tuple(sorted(expansion_trace.generated_variants, key=lambda variant: variant.variant_index))
        original_variant = variants[0]
        skipped_variant_count = 0
        retrieval_reason = "alias_expanded_retrieval"
        if expansion_trace.expansion_reason == "expansion_disabled":
            retrieval_reason = "baseline_only_expansion_disabled"
        elif len(variants) == 1:
            retrieval_reason = "baseline_only_no_variants"
        elif not self._config.enabled:
            retrieval_reason = "baseline_only_retrieval_disabled"
            skipped_variant_count = len(variants) - 1

        retrieval_start = perf_counter()
        variant_retrievals: list[VariantRetrievalResult] = []
        original_result = self._search_variant(original_variant, document_id, self._config.original_top_k)
        variant_retrievals.append(original_result)
        if not original_result.success:
            raise ExpandedRetrievalError("Original query retrieval failed.")

        if self._config.enabled:
            for variant in variants[1:]:
                result = self._search_variant(variant, document_id, self._config.variant_top_k)
                if not result.success and self._config.strict_variant_failures:
                    raise ExpandedRetrievalError(f"Alias variant retrieval failed: {result.error_code}")
                variant_retrievals.append(result)
        retrieval_duration_ms = _elapsed_ms(retrieval_start)

        fusion_start = perf_counter()
        baseline_results = original_result.hits
        successful_results = tuple(result for result in variant_retrievals if result.success)
        validation_warnings: list[str] = []
        metadata_conflict_count = 0
        if retrieval_reason.startswith("baseline_only"):
            fused_results = _baseline_fused_results(original_result, self._config)
        else:
            fused_results, metadata_conflict_count, validation_warnings = _fuse_results(
                successful_results,
                self._config,
            )
        fusion_duration_ms = _elapsed_ms(fusion_start)

        backend_raw_hit_count = sum(result.backend_raw_hit_count for result in variant_retrievals)
        normalized_hit_count = sum(len(result.hits) for result in variant_retrievals)
        intra_variant_duplicate_count = sum(result.intra_variant_duplicate_count for result in variant_retrievals)
        unique_candidate_chunk_count = len({hit.chunk_id for result in variant_retrievals for hit in result.hits})
        cross_variant_duplicate_occurrence_count = normalized_hit_count - unique_candidate_chunk_count
        duplicate_chunk_occurrence_count = intra_variant_duplicate_count + cross_variant_duplicate_occurrence_count
        vector_search_call_count = len(variant_retrievals)
        alias_retrieval_applied = any(result.variant_index != 0 and result.success for result in variant_retrievals)
        trace = ExpandedRetrievalTrace(
            original_query=query,
            document_id=document_id,
            alias_dataset_sha256=self._alias_registry.snapshot.sha256,
            expansion_config_snapshot=expansion_trace.config_snapshot,
            retrieval_config_snapshot=self._config,
            expansion_trace=expansion_trace,
            variant_retrievals=tuple(variant_retrievals),
            baseline_results=baseline_results,
            fused_results=fused_results,
            total_variant_count=len(variants),
            successful_variant_count=sum(1 for result in variant_retrievals if result.success),
            failed_variant_count=sum(1 for result in variant_retrievals if not result.success),
            skipped_variant_count=skipped_variant_count,
            backend_raw_hit_count=backend_raw_hit_count,
            normalized_hit_count=normalized_hit_count,
            intra_variant_duplicate_count=intra_variant_duplicate_count,
            unique_candidate_chunk_count=unique_candidate_chunk_count,
            cross_variant_duplicate_occurrence_count=cross_variant_duplicate_occurrence_count,
            duplicate_chunk_occurrence_count=duplicate_chunk_occurrence_count,
            final_result_count=len(fused_results),
            embedding_input_count=vector_search_call_count,
            embedding_call_count=None,
            vector_search_call_count=vector_search_call_count,
            metadata_conflict_count=metadata_conflict_count,
            validation_warnings=tuple(validation_warnings),
            expansion_duration_ms=expansion_duration_ms,
            retrieval_duration_ms=retrieval_duration_ms,
            fusion_duration_ms=fusion_duration_ms,
            total_duration_ms=_elapsed_ms(total_start),
            alias_retrieval_applied=alias_retrieval_applied,
            retrieval_reason=retrieval_reason,
        )
        logger.info(
            "Expanded retrieval completed query_length=%s variant_count=%s successful_variants=%s "
            "raw_hits=%s unique_chunks=%s final_chunks=%s search_calls=%s total_duration_ms=%.2f",
            len(query),
            trace.total_variant_count,
            trace.successful_variant_count,
            trace.backend_raw_hit_count,
            trace.unique_candidate_chunk_count,
            trace.final_result_count,
            trace.vector_search_call_count,
            trace.total_duration_ms,
        )
        return trace

    def _search_variant(
        self,
        variant: QueryVariant,
        document_id: str,
        top_k: int,
    ) -> VariantRetrievalResult:
        weight = _variant_weight(variant.variant_kind, self._config)
        start = perf_counter()
        try:
            search_result = self._vector_search_service.search(
                variant.query_text,
                document_id=document_id,
                top_k=top_k,
            )
            raw_hits = search_result.get("results", [])
            hits, duplicate_count = _dedupe_variant_hits(raw_hits, document_id)
            total_ms = _elapsed_ms(start)
            return VariantRetrievalResult(
                variant_id=variant.variant_id,
                variant_index=variant.variant_index,
                variant_kind=variant.variant_kind,
                query_text=variant.query_text,
                variant_weight=weight,
                requested_top_k=top_k,
                backend_raw_hit_count=len(raw_hits),
                intra_variant_duplicate_count=duplicate_count,
                hits=hits,
                embedding_duration_ms=search_result.get("embedding_duration_ms"),
                search_duration_ms=search_result.get("database_duration_ms", total_ms),
                total_duration_ms=total_ms,
                success=True,
            )
        except Exception as exc:
            logger.exception("Variant retrieval failed variant_id=%s variant_index=%s", variant.variant_id, variant.variant_index)
            if variant.variant_index == 0 or self._config.strict_variant_failures:
                raise ExpandedRetrievalError("Variant retrieval failed: vector_search_failed") from exc
            total_ms = _elapsed_ms(start)
            return VariantRetrievalResult(
                variant_id=variant.variant_id,
                variant_index=variant.variant_index,
                variant_kind=variant.variant_kind,
                query_text=variant.query_text,
                variant_weight=weight,
                requested_top_k=top_k,
                hits=(),
                search_duration_ms=total_ms,
                total_duration_ms=total_ms,
                success=False,
                error_code="vector_search_failed",
                error_message="Vector search failed for this query variant.",
            )


def _validate_expansion_trace(trace: QueryExpansionTrace, config: ExpandedRetrievalConfig) -> None:
    variants = trace.generated_variants
    if len(variants) > config.max_variants:
        raise ExpandedRetrievalError("Expansion produced more variants than retrieval max_variants.")
    originals = [variant for variant in variants if variant.variant_kind == "original"]
    if len(originals) != 1:
        raise ExpandedRetrievalError("Expansion trace must contain exactly one original variant.")
    original = originals[0]
    if original.variant_index != 0 or original.variant_id != "original":
        raise ExpandedRetrievalError("Original variant must have index 0 and id 'original'.")
    if len({variant.variant_id for variant in variants}) != len(variants):
        raise ExpandedRetrievalError("Expansion trace contains duplicate variant_id values.")
    if len({variant.variant_index for variant in variants}) != len(variants):
        raise ExpandedRetrievalError("Expansion trace contains duplicate variant_index values.")
    if any(variant.variant_kind not in KNOWN_VARIANT_KINDS for variant in variants):
        raise ExpandedRetrievalError("Expansion trace contains unknown variant_kind.")


def _variant_weight(variant_kind: str, config: ExpandedRetrievalConfig) -> float:
    weights = config.variant_weights()
    if variant_kind not in weights:
        raise ExpandedRetrievalError(f"Unknown variant_kind: {variant_kind}")
    return weights[variant_kind]


def _dedupe_variant_hits(raw_hits: list[dict], document_id: str) -> tuple[tuple[VariantRetrievalHit, ...], int]:
    by_chunk: dict[str, VariantRetrievalHit] = {}
    for item in raw_hits:
        chunk_id = item["chunk_uid"]
        hit = VariantRetrievalHit(
            chunk_id=chunk_id,
            document_id=item.get("document_id", document_id),
            story_id=item.get("story_id"),
            section_id=item.get("section_id"),
            section_title=item.get("section_title"),
            section_order=item.get("section_order"),
            chunk_order=item.get("chunk_order"),
            chunk_text=item["chunk_text"],
            rank=item["rank"],
            raw_similarity=item.get("cosine_similarity"),
            raw_distance=item.get("cosine_distance"),
        )
        existing = by_chunk.get(chunk_id)
        if existing is None or hit.rank < existing.rank:
            by_chunk[chunk_id] = hit
    hits = tuple(sorted(by_chunk.values(), key=lambda hit: (hit.rank, hit.chunk_id)))
    return hits, max(0, len(raw_hits) - len(hits))


def _baseline_fused_results(
    original_result: VariantRetrievalResult,
    config: ExpandedRetrievalConfig,
) -> tuple[FusedChunkResult, ...]:
    fused: list[FusedChunkResult] = []
    for final_rank, hit in enumerate(original_result.hits[: config.final_top_k], start=1):
        contribution = _contribution(original_result, hit, config)
        fused.append(
            FusedChunkResult(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                story_id=hit.story_id,
                section_id=hit.section_id,
                section_title=hit.section_title,
                section_order=hit.section_order,
                chunk_order=hit.chunk_order,
                chunk_text=hit.chunk_text,
                final_rank=final_rank,
                fusion_score=contribution.rrf_contribution,
                contributing_variant_count=1,
                contributions=(contribution,),
                appeared_in_original_query=True,
                original_query_rank=hit.rank,
                best_individual_rank=hit.rank,
                best_variant_id=original_result.variant_id,
                best_variant_rank=hit.rank,
                alias_only_candidate=False,
            )
        )
    return tuple(fused)


def _fuse_results(
    variant_results: tuple[VariantRetrievalResult, ...],
    config: ExpandedRetrievalConfig,
) -> tuple[tuple[FusedChunkResult, ...], int, list[str]]:
    hits_by_chunk: dict[str, list[tuple[VariantRetrievalResult, VariantRetrievalHit]]] = defaultdict(list)
    metadata_by_chunk: dict[str, VariantRetrievalHit] = {}
    metadata_conflict_count = 0
    warnings: list[str] = []
    for result in sorted(variant_results, key=lambda item: item.variant_index):
        for hit in result.hits:
            hits_by_chunk[hit.chunk_id].append((result, hit))
            selected = metadata_by_chunk.get(hit.chunk_id)
            if selected is None:
                metadata_by_chunk[hit.chunk_id] = hit
            elif _metadata_conflicts(selected, hit):
                metadata_conflict_count += 1
                warnings.append(f"Metadata conflict for chunk_id {hit.chunk_id}")
                if config.strict_variant_failures:
                    raise ExpandedRetrievalError(f"Chunk metadata conflict for {hit.chunk_id}")
                if result.variant_index == 0:
                    metadata_by_chunk[hit.chunk_id] = hit

    fused: list[FusedChunkResult] = []
    for chunk_id, pairs in hits_by_chunk.items():
        contributions = tuple(
            sorted(
                (_contribution(result, hit, config) for result, hit in pairs),
                key=lambda contribution: contribution.variant_index,
            )
        )
        fusion_score = sum(item.rrf_contribution for item in contributions)
        original_hits = [hit for result, hit in pairs if result.variant_index == 0]
        original_rank = min((hit.rank for hit in original_hits), default=None)
        best_pair = min(pairs, key=lambda pair: (pair[1].rank, pair[0].variant_index, pair[0].variant_id))
        metadata = metadata_by_chunk[chunk_id]
        fused.append(
            FusedChunkResult(
                chunk_id=chunk_id,
                document_id=metadata.document_id,
                story_id=metadata.story_id,
                section_id=metadata.section_id,
                section_title=metadata.section_title,
                section_order=metadata.section_order,
                chunk_order=metadata.chunk_order,
                chunk_text=metadata.chunk_text,
                final_rank=-1,
                fusion_score=fusion_score,
                contributing_variant_count=len(contributions),
                contributions=contributions,
                appeared_in_original_query=original_rank is not None,
                original_query_rank=original_rank,
                best_individual_rank=best_pair[1].rank,
                best_variant_id=best_pair[0].variant_id,
                best_variant_rank=best_pair[1].rank,
                alias_only_candidate=original_rank is None,
            )
        )
    ranked = sorted(fused, key=_fused_sort_key)[: config.final_top_k]
    return tuple(item.model_copy(update={"final_rank": idx}) for idx, item in enumerate(ranked, start=1)), metadata_conflict_count, warnings


def _metadata_conflicts(left: VariantRetrievalHit, right: VariantRetrievalHit) -> bool:
    return (
        left.document_id != right.document_id
        or left.story_id != right.story_id
        or left.section_id != right.section_id
        or left.section_title != right.section_title
        or left.section_order != right.section_order
        or left.chunk_order != right.chunk_order
        or left.chunk_text != right.chunk_text
    )


def _contribution(
    result: VariantRetrievalResult,
    hit: VariantRetrievalHit,
    config: ExpandedRetrievalConfig,
) -> ChunkContribution:
    return ChunkContribution(
        variant_id=result.variant_id,
        variant_index=result.variant_index,
        variant_kind=result.variant_kind,
        query_text=result.query_text,
        variant_weight=result.variant_weight,
        rank=hit.rank,
        rrf_contribution=result.variant_weight / (config.rrf_k + hit.rank),
        raw_similarity=hit.raw_similarity,
        raw_distance=hit.raw_distance,
    )


def _fused_sort_key(item: FusedChunkResult) -> tuple:
    return (
        -item.fusion_score,
        not item.appeared_in_original_query,
        item.original_query_rank if item.original_query_rank is not None else 10**9,
        item.best_individual_rank,
        item.chunk_id,
    )


def _elapsed_ms(start: float) -> float:
    return (perf_counter() - start) * 1000
