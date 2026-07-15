import pytest
from app.evaluation.metric_calculator import MetricCalculator

def test_single_question_metrics():
    # Rank 1 is supporting_context, Rank 3 is direct_evidence, other 8 are irrelevant
    judgments = [
        {"rank": 1, "label": "supporting_context"},
        {"rank": 2, "label": "irrelevant"},
        {"rank": 3, "label": "direct_evidence"},
        {"rank": 4, "label": "irrelevant"},
        {"rank": 5, "label": "irrelevant"},
        {"rank": 6, "label": "irrelevant"},
        {"rank": 7, "label": "irrelevant"},
        {"rank": 8, "label": "irrelevant"},
        {"rank": 9, "label": "irrelevant"},
        {"rank": 10, "label": "irrelevant"}
    ]
    sufficiency = {"top_1": False, "top_3": True, "top_5": True, "top_10": True}
    first_direct_evidence_rank = 3

    metrics = MetricCalculator.compute_question_metrics(judgments, sufficiency, first_direct_evidence_rank)

    # 1. Direct Hit@K
    assert metrics["direct_hit_at_1"] == 0
    assert metrics["direct_hit_at_3"] == 1
    assert metrics["direct_hit_at_5"] == 1
    assert metrics["direct_hit_at_10"] == 1

    # 2. Reciprocal Rank
    assert pytest.approx(metrics["reciprocal_rank"]) == 1.0 / 3.0

    # 3. Direct Precision@K
    assert metrics["direct_precision_at_1"] == 0.0
    assert pytest.approx(metrics["direct_precision_at_3"]) == 1.0 / 3.0
    assert pytest.approx(metrics["direct_precision_at_5"]) == 1.0 / 5.0
    assert pytest.approx(metrics["direct_precision_at_10"]) == 1.0 / 10.0

    # 4. Useful Precision@K (includes direct_evidence and supporting_context)
    assert metrics["useful_precision_at_1"] == 1.0  # Rank 1 is supporting_context
    assert pytest.approx(metrics["useful_precision_at_3"]) == 2.0 / 3.0  # Rank 1 + 3
    assert pytest.approx(metrics["useful_precision_at_5"]) == 2.0 / 5.0
    assert pytest.approx(metrics["useful_precision_at_10"]) == 2.0 / 10.0

    # 5. Answer Sufficiency@K
    assert metrics["answer_sufficiency_at_1"] == 0
    assert metrics["answer_sufficiency_at_3"] == 1
    assert metrics["answer_sufficiency_at_5"] == 1
    assert metrics["answer_sufficiency_at_10"] == 1

    # 6. Noise rate
    # noise labels: irrelevant (8 counts)
    assert pytest.approx(metrics["noise_rate_at_10"]) == 0.8
    assert metrics["label_counts"]["direct_evidence"] == 1
    assert metrics["label_counts"]["supporting_context"] == 1
    assert metrics["label_counts"]["irrelevant"] == 8

def test_aggregate_metrics():
    # Metric question 1: MRR = 0.5, direct_hit_at_1 = 0, dp_10 = 0.2, suff_3 = 1
    q1 = {
        "first_direct_evidence_rank": 2,
        "reciprocal_rank": 0.5,
        "direct_hit_at_1": 0,
        "direct_hit_at_3": 1,
        "direct_hit_at_5": 1,
        "direct_hit_at_10": 1,
        "direct_precision_at_1": 0.0,
        "direct_precision_at_3": 0.33,
        "direct_precision_at_5": 0.2,
        "direct_precision_at_10": 0.2,
        "useful_precision_at_1": 1.0,
        "useful_precision_at_3": 0.67,
        "useful_precision_at_5": 0.4,
        "useful_precision_at_10": 0.3,
        "answer_sufficiency_at_1": 0,
        "answer_sufficiency_at_3": 1,
        "answer_sufficiency_at_5": 1,
        "answer_sufficiency_at_10": 1,
        "label_counts": {
            "direct_evidence": 2,
            "supporting_context": 1,
            "topically_related": 1,
            "irrelevant": 6,
            "contradictory": 0
        },
        "noise_rate_at_10": 0.7
    }

    # Metric question 2: MRR = 1.0, direct_hit_at_1 = 1, dp_10 = 0.1, suff_3 = 0
    q2 = {
        "first_direct_evidence_rank": 1,
        "reciprocal_rank": 1.0,
        "direct_hit_at_1": 1,
        "direct_hit_at_3": 1,
        "direct_hit_at_5": 1,
        "direct_hit_at_10": 1,
        "direct_precision_at_1": 1.0,
        "direct_precision_at_3": 0.33,
        "direct_precision_at_5": 0.2,
        "direct_precision_at_10": 0.1,
        "useful_precision_at_1": 1.0,
        "useful_precision_at_3": 0.33,
        "useful_precision_at_5": 0.2,
        "useful_precision_at_10": 0.1,
        "answer_sufficiency_at_1": 0,
        "answer_sufficiency_at_3": 0,
        "answer_sufficiency_at_5": 1,
        "answer_sufficiency_at_10": 1,
        "label_counts": {
            "direct_evidence": 1,
            "supporting_context": 0,
            "topically_related": 2,
            "irrelevant": 7,
            "contradictory": 0
        },
        "noise_rate_at_10": 0.9
    }

    agg = MetricCalculator.compute_aggregate_metrics([q1, q2])

    assert agg["question_count"] == 2
    assert pytest.approx(agg["mrr"]) == 0.75  # (0.5 + 1.0) / 2
    assert pytest.approx(agg["direct_hit_rate_at_1"]) == 0.5  # (0 + 1) / 2
    assert pytest.approx(agg["direct_hit_rate_at_3"]) == 1.0
    assert pytest.approx(agg["answer_sufficiency_rate_at_3"]) == 0.5 # (1 + 0) / 2
    assert pytest.approx(agg["mean_noise_rate_at_10"]) == 0.8 # (0.7 + 0.9) / 2

    # Verify label_totals sums
    assert agg["label_totals"]["direct_evidence"] == 3
    assert agg["label_totals"]["supporting_context"] == 1
    assert agg["label_totals"]["topically_related"] == 3
    assert agg["label_totals"]["irrelevant"] == 13
