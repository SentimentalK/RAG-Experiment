from typing import Optional, Any

class MetricCalculator:
    """
    Computes semantic retrieval metrics for individual questions and aggregates
    them across all questions in an evaluation batch.
    """
    @staticmethod
    def compute_question_metrics(
        retrieved_chunk_judgments: list[dict],
        sufficiency: dict,
        first_direct_evidence_rank: Optional[int]
    ) -> dict:
        """
        Computes metric dict for a single question based on rank-judgments and sufficiency values.
        """
        # Map rank to labels (assumes rank is validated as 1-10)
        labels_by_rank = {}
        for item in retrieved_chunk_judgments:
            labels_by_rank[item["rank"]] = item["label"]

        # Helper to compute metric at K
        def has_direct_evidence(k: int) -> int:
            for rank in range(1, k + 1):
                if labels_by_rank.get(rank) == "direct_evidence":
                    return 1
            return 0

        def get_precision(k: int, target_labels: set[str]) -> float:
            matches = 0
            for rank in range(1, k + 1):
                if labels_by_rank.get(rank) in target_labels:
                    matches += 1
            return matches / k

        # 1. Direct Hit@K
        direct_hit_at_1 = has_direct_evidence(1)
        direct_hit_at_3 = has_direct_evidence(3)
        direct_hit_at_5 = has_direct_evidence(5)
        direct_hit_at_10 = has_direct_evidence(10)

        # 2. Reciprocal Rank
        reciprocal_rank = 1.0 / first_direct_evidence_rank if first_direct_evidence_rank else 0.0

        # 3. Direct Precision@K
        direct_precision_at_1 = get_precision(1, {"direct_evidence"})
        direct_precision_at_3 = get_precision(3, {"direct_evidence"})
        direct_precision_at_5 = get_precision(5, {"direct_evidence"})
        direct_precision_at_10 = get_precision(10, {"direct_evidence"})

        # 4. Useful Precision@K
        useful_precision_at_1 = get_precision(1, {"direct_evidence", "supporting_context"})
        useful_precision_at_3 = get_precision(3, {"direct_evidence", "supporting_context"})
        useful_precision_at_5 = get_precision(5, {"direct_evidence", "supporting_context"})
        useful_precision_at_10 = get_precision(10, {"direct_evidence", "supporting_context"})

        # 5. Answer Sufficiency@K (1 or 0)
        answer_sufficiency_at_1 = 1 if sufficiency.get("top_1") else 0
        answer_sufficiency_at_3 = 1 if sufficiency.get("top_3") else 0
        answer_sufficiency_at_5 = 1 if sufficiency.get("top_5") else 0
        answer_sufficiency_at_10 = 1 if sufficiency.get("top_10") else 0

        # 6. Label counts
        label_counts = {
            "direct_evidence": 0,
            "supporting_context": 0,
            "topically_related": 0,
            "irrelevant": 0,
            "contradictory": 0
        }
        for label in labels_by_rank.values():
            if label in label_counts:
                label_counts[label] += 1

        # 7. Noise rate at 10
        noise_labels = {"topically_related", "irrelevant", "contradictory"}
        noise_count = sum(1 for label in labels_by_rank.values() if label in noise_labels)
        noise_rate_at_10 = noise_count / 10.0

        return {
            "first_direct_evidence_rank": first_direct_evidence_rank,
            "reciprocal_rank": reciprocal_rank,
            "direct_hit_at_1": direct_hit_at_1,
            "direct_hit_at_3": direct_hit_at_3,
            "direct_hit_at_5": direct_hit_at_5,
            "direct_hit_at_10": direct_hit_at_10,
            "direct_precision_at_1": direct_precision_at_1,
            "direct_precision_at_3": direct_precision_at_3,
            "direct_precision_at_5": direct_precision_at_5,
            "direct_precision_at_10": direct_precision_at_10,
            "useful_precision_at_1": useful_precision_at_1,
            "useful_precision_at_3": useful_precision_at_3,
            "useful_precision_at_5": useful_precision_at_5,
            "useful_precision_at_10": useful_precision_at_10,
            "answer_sufficiency_at_1": answer_sufficiency_at_1,
            "answer_sufficiency_at_3": answer_sufficiency_at_3,
            "answer_sufficiency_at_5": answer_sufficiency_at_5,
            "answer_sufficiency_at_10": answer_sufficiency_at_10,
            "label_counts": label_counts,
            "noise_rate_at_10": noise_rate_at_10
        }

    @staticmethod
    def compute_aggregate_metrics(questions_metrics: list[dict]) -> dict:
        """
        Computes aggregate Rate and Mean metrics across all questions.
        """
        q_count = len(questions_metrics)
        if q_count == 0:
            return {
                "question_count": 0,
                "direct_hit_rate_at_1": 0.0,
                "direct_hit_rate_at_3": 0.0,
                "direct_hit_rate_at_5": 0.0,
                "direct_hit_rate_at_10": 0.0,
                "mrr": 0.0,
                "mean_direct_precision_at_1": 0.0,
                "mean_direct_precision_at_3": 0.0,
                "mean_direct_precision_at_5": 0.0,
                "mean_direct_precision_at_10": 0.0,
                "mean_useful_precision_at_1": 0.0,
                "mean_useful_precision_at_3": 0.0,
                "mean_useful_precision_at_5": 0.0,
                "mean_useful_precision_at_10": 0.0,
                "answer_sufficiency_rate_at_1": 0.0,
                "answer_sufficiency_rate_at_3": 0.0,
                "answer_sufficiency_rate_at_5": 0.0,
                "answer_sufficiency_rate_at_10": 0.0,
                "mean_noise_rate_at_10": 0.0,
                "label_totals": {
                    "direct_evidence": 0,
                    "supporting_context": 0,
                    "topically_related": 0,
                    "irrelevant": 0,
                    "contradictory": 0
                }
            }

        label_totals = {
            "direct_evidence": 0,
            "supporting_context": 0,
            "topically_related": 0,
            "irrelevant": 0,
            "contradictory": 0
        }

        # Sum values
        direct_hit_1 = sum(m["direct_hit_at_1"] for m in questions_metrics)
        direct_hit_3 = sum(m["direct_hit_at_3"] for m in questions_metrics)
        direct_hit_5 = sum(m["direct_hit_at_5"] for m in questions_metrics)
        direct_hit_10 = sum(m["direct_hit_at_10"] for m in questions_metrics)

        mrr_sum = sum(m["reciprocal_rank"] for m in questions_metrics)

        dp_1 = sum(m["direct_precision_at_1"] for m in questions_metrics)
        dp_3 = sum(m["direct_precision_at_3"] for m in questions_metrics)
        dp_5 = sum(m["direct_precision_at_5"] for m in questions_metrics)
        dp_10 = sum(m["direct_precision_at_10"] for m in questions_metrics)

        up_1 = sum(m["useful_precision_at_1"] for m in questions_metrics)
        up_3 = sum(m["useful_precision_at_3"] for m in questions_metrics)
        up_5 = sum(m["useful_precision_at_5"] for m in questions_metrics)
        up_10 = sum(m["useful_precision_at_10"] for m in questions_metrics)

        suff_1 = sum(m["answer_sufficiency_at_1"] for m in questions_metrics)
        suff_3 = sum(m["answer_sufficiency_at_3"] for m in questions_metrics)
        suff_5 = sum(m["answer_sufficiency_at_5"] for m in questions_metrics)
        suff_10 = sum(m["answer_sufficiency_at_10"] for m in questions_metrics)

        noise_rate_10_sum = sum(m["noise_rate_at_10"] for m in questions_metrics)

        for m in questions_metrics:
            counts = m["label_counts"]
            for label in label_totals:
                label_totals[label] += counts.get(label, 0)

        return {
            "question_count": q_count,
            "direct_hit_rate_at_1": direct_hit_1 / q_count,
            "direct_hit_rate_at_3": direct_hit_3 / q_count,
            "direct_hit_rate_at_5": direct_hit_5 / q_count,
            "direct_hit_rate_at_10": direct_hit_10 / q_count,
            "mrr": mrr_sum / q_count,
            "mean_direct_precision_at_1": dp_1 / q_count,
            "mean_direct_precision_at_3": dp_3 / q_count,
            "mean_direct_precision_at_5": dp_5 / q_count,
            "mean_direct_precision_at_10": dp_10 / q_count,
            "mean_useful_precision_at_1": up_1 / q_count,
            "mean_useful_precision_at_3": up_3 / q_count,
            "mean_useful_precision_at_5": up_5 / q_count,
            "mean_useful_precision_at_10": up_10 / q_count,
            "answer_sufficiency_rate_at_1": suff_1 / q_count,
            "answer_sufficiency_rate_at_3": suff_3 / q_count,
            "answer_sufficiency_rate_at_5": suff_5 / q_count,
            "answer_sufficiency_rate_at_10": suff_10 / q_count,
            "mean_noise_rate_at_10": noise_rate_10_sum / q_count,
            "label_totals": label_totals
        }
