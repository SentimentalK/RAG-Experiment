import math
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.evaluation.alias_retrieval.dataset import AliasEvaluationQuestion
from app.services.expanded_retrieval_service import FusedChunkResult, VariantRetrievalHit


ComparisonCategory = Literal[
    "rescued",
    "lost",
    "coverage_improved",
    "coverage_harmed",
    "coverage_mixed",
    "rank_improved",
    "rank_harmed",
    "unchanged",
]


class RetrievalGoldMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_group_recall_at_1: float
    evidence_group_recall_at_3: float
    evidence_group_recall_at_5: float
    evidence_group_recall_at_10: float
    complete_evidence_at_3: bool
    complete_evidence_at_5: bool
    complete_evidence_at_10: bool
    first_evidence_rank: int | None
    completion_rank: int | None
    evidence_rank_sum: int | None
    mrr_at_10: float
    ndcg_at_10: float | None
    contradictory_hit_at_10: bool
    contradictory_chunk_count_at_10: int
    hit_evidence_group_ids_at_10: tuple[str, ...]
    direct_evidence_chunk_uids_at_10: tuple[str, ...]


class ModeComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    comparison_category: ComparisonCategory
    new_gold_chunk_uids: tuple[str, ...]
    newly_covered_evidence_group_ids: tuple[str, ...]


def chunk_ids_from_results(results: tuple[FusedChunkResult, ...] | tuple[VariantRetrievalHit, ...]) -> list[str]:
    return [item.chunk_id for item in results]


def compute_retrieval_metrics(
    question: AliasEvaluationQuestion,
    ranked_chunk_ids: list[str],
    *,
    include_ndcg: bool = True,
) -> RetrievalGoldMetrics:
    top10 = ranked_chunk_ids[:10]
    required_groups = question.gold_evidence_groups
    group_first_ranks: dict[str, int] = {}
    direct_chunks: set[str] = set()
    for group in required_groups:
        alternatives = set(group.alternative_chunk_uids)
        direct_chunks.update(alternatives)
        for idx, chunk_id in enumerate(top10, start=1):
            if chunk_id in alternatives:
                group_first_ranks[group.evidence_group_id] = idx
                break

    def recall_at(k: int) -> float:
        if not required_groups:
            return 0.0
        hit_count = 0
        prefix = set(ranked_chunk_ids[:k])
        for group in required_groups:
            if prefix.intersection(group.alternative_chunk_uids):
                hit_count += 1
        return hit_count / len(required_groups)

    def complete_at(k: int) -> bool:
        if not required_groups:
            return False
        prefix = set(ranked_chunk_ids[:k])
        return all(prefix.intersection(group.alternative_chunk_uids) for group in required_groups)

    first_evidence_rank = min(group_first_ranks.values()) if group_first_ranks else None
    is_complete_10 = len(group_first_ranks) == len(required_groups)
    completion_rank = max(group_first_ranks.values()) if is_complete_10 and group_first_ranks else None
    evidence_rank_sum = sum(group_first_ranks.values()) if group_first_ranks else None
    contradictory_count = sum(1 for chunk_id in top10 if chunk_id in set(question.contradictory_chunk_uids))

    return RetrievalGoldMetrics(
        evidence_group_recall_at_1=recall_at(1),
        evidence_group_recall_at_3=recall_at(3),
        evidence_group_recall_at_5=recall_at(5),
        evidence_group_recall_at_10=recall_at(10),
        complete_evidence_at_3=complete_at(3),
        complete_evidence_at_5=complete_at(5),
        complete_evidence_at_10=complete_at(10),
        first_evidence_rank=first_evidence_rank,
        completion_rank=completion_rank,
        evidence_rank_sum=evidence_rank_sum,
        mrr_at_10=1.0 / first_evidence_rank if first_evidence_rank else 0.0,
        ndcg_at_10=_ndcg(top10, direct_chunks, set(question.supporting_chunk_uids)) if include_ndcg else None,
        contradictory_hit_at_10=contradictory_count > 0,
        contradictory_chunk_count_at_10=contradictory_count,
        hit_evidence_group_ids_at_10=tuple(sorted(group_first_ranks)),
        direct_evidence_chunk_uids_at_10=tuple(chunk_id for chunk_id in top10 if chunk_id in direct_chunks),
    )


def compare_modes(
    question: AliasEvaluationQuestion,
    baseline: RetrievalGoldMetrics,
    expanded: RetrievalGoldMetrics,
) -> ModeComparison:
    baseline_groups = set(baseline.hit_evidence_group_ids_at_10)
    expanded_groups = set(expanded.hit_evidence_group_ids_at_10)
    baseline_complete = baseline.complete_evidence_at_10
    expanded_complete = expanded.complete_evidence_at_10

    if not baseline_complete and expanded_complete:
        category: ComparisonCategory = "rescued"
    elif baseline_complete and not expanded_complete:
        category = "lost"
    elif len(expanded_groups) > len(baseline_groups):
        category = "coverage_improved"
    elif len(expanded_groups) < len(baseline_groups):
        category = "coverage_harmed"
    elif expanded_groups != baseline_groups:
        category = "coverage_mixed"
    else:
        category = _rank_category(baseline, expanded)

    baseline_direct = set(baseline.direct_evidence_chunk_uids_at_10)
    expanded_direct = set(expanded.direct_evidence_chunk_uids_at_10)
    return ModeComparison(
        comparison_category=category,
        new_gold_chunk_uids=tuple(sorted(expanded_direct - baseline_direct)),
        newly_covered_evidence_group_ids=tuple(sorted(expanded_groups - baseline_groups)),
    )


def _rank_category(baseline: RetrievalGoldMetrics, expanded: RetrievalGoldMetrics) -> ComparisonCategory:
    if baseline.complete_evidence_at_10 and expanded.complete_evidence_at_10:
        left = (baseline.completion_rank or 10**9, baseline.first_evidence_rank or 10**9)
        right = (expanded.completion_rank or 10**9, expanded.first_evidence_rank or 10**9)
    else:
        left = (baseline.evidence_rank_sum or 10**9, baseline.first_evidence_rank or 10**9)
        right = (expanded.evidence_rank_sum or 10**9, expanded.first_evidence_rank or 10**9)
    if right < left:
        return "rank_improved"
    if right > left:
        return "rank_harmed"
    return "unchanged"


def _ndcg(top10: list[str], direct_chunks: set[str], supporting_chunks: set[str]) -> float:
    gains = []
    for chunk_id in top10[:10]:
        if chunk_id in direct_chunks:
            gains.append(2)
        elif chunk_id in supporting_chunks:
            gains.append(1)
        else:
            gains.append(0)
    dcg = sum(gain / math.log2(idx + 2) for idx, gain in enumerate(gains))
    ideal = sorted(gains, reverse=True)
    idcg = sum(gain / math.log2(idx + 2) for idx, gain in enumerate(ideal))
    return dcg / idcg if idcg else 0.0

