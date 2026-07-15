import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, Any

@dataclass
class ValidationMessage:
    question_id: str
    message: str
    field: Optional[str] = None

@dataclass
class ValidationResult:
    errors: list[ValidationMessage] = field(default_factory=list)
    warnings: list[ValidationMessage] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

def normalize_quote_characters(value: str) -> str:
    """
    Normalizes quote characters to standardized straight double/single quotes.
    Uses Unicode NFKC normalization first.
    """
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value)
    return (
        value
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )

def normalize_evidence_text(value: str) -> str:
    """
    Normalizes evidence text for search matching by folding quote variations
    and compressing multiple spaces/whitespace to a single space.
    """
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value)
    value = (
        value
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )
    return re.sub(r"\s+", " ", value).strip()

class JudgmentValidator:
    """
    Performs structural, type, consistency, mapping, and monotonicity
    validations on RAG retrieval evaluation judgment JSON files.
    """
    def __init__(self, questions_config: dict, retrieval_results: dict, sections_by_order: dict):
        self.questions_by_id = {q["question_id"]: q for q in questions_config.get("questions", [])}
        self.retrieval_by_qid = {res["question_id"]: res for res in retrieval_results.get("results", [])}
        self.sections_by_order = sections_by_order

    def validate_single(self, judgment: dict, filename_qid: str) -> tuple[ValidationResult, list[dict]]:
        """
        Validates a single judgment dictionary.
        Returns:
            ValidationResult containing errors and warnings lists.
            list of correction dicts describing quote corrections performed.
        """
        result = ValidationResult()
        corrections = []

        # 1. Schema keys check
        required_keys = [
            "schema_version", "question_id", "question", "question_interpretation",
            "reference_answer", "candidate_story_judgments", "retrieved_chunk_judgments",
            "top_k_sufficiency", "first_direct_evidence_rank", "missing_evidence_within_candidate_stories",
            "overall_assessment", "confidence"
        ]
        
        missing_keys = [k for k in required_keys if k not in judgment]
        if missing_keys:
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"Missing required top-level schema keys: {missing_keys}"
            ))
            return result, corrections

        schema_version = judgment["schema_version"]
        question_id = judgment["question_id"]
        question_text = judgment["question"]
        interpretation = judgment["question_interpretation"]
        ref_answer = judgment["reference_answer"]
        confidence = judgment["confidence"]
        overall_assessment = judgment["overall_assessment"]

        # Validate types
        if schema_version != "1.0":
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"Expected schema_version '1.0', got '{schema_version}'.",
                field="schema_version"
            ))

        for k, v in [("question_id", question_id), ("question", question_text),
                     ("question_interpretation", interpretation), ("reference_answer", ref_answer)]:
            if not isinstance(v, str) or not v.strip():
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Field '{k}' must be a non-empty string.",
                    field=k
                ))

        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"Field 'confidence' must be a float between 0.0 and 1.0, got {confidence}.",
                field="confidence"
            ))

        if not isinstance(overall_assessment, dict):
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message="Field 'overall_assessment' must be a JSON object.",
                field="overall_assessment"
            ))
        else:
            quality = overall_assessment.get("retrieval_quality")
            score = overall_assessment.get("score_0_to_100")
            summary = overall_assessment.get("summary")

            valid_qualities = {"excellent", "good", "mixed", "poor", "failed"}
            if quality not in valid_qualities:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"overall_assessment.retrieval_quality must be one of {valid_qualities}, got '{quality}'.",
                    field="overall_assessment.retrieval_quality"
                ))
            if not isinstance(score, (int, float)) or not (0 <= score <= 100):
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"overall_assessment.score_0_to_100 must be between 0 and 100, got {score}.",
                    field="overall_assessment.score_0_to_100"
                ))
            if not isinstance(summary, str) or not summary.strip():
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message="overall_assessment.summary must be a non-empty string.",
                    field="overall_assessment.summary"
                ))

        # 2. Filename vs question_id consistency check
        if question_id != filename_qid:
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"Filename Question ID '{filename_qid}' does not match JSON field question_id '{question_id}'.",
                field="question_id"
            ))

        # 3. Canonical question matching
        if question_id not in self.questions_by_id:
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"Question ID '{question_id}' not found in canonical questions list.",
                field="question_id"
            ))
            return result, corrections

        canonical_question = self.questions_by_id[question_id]["question"]
        if question_text != canonical_question:
            # Check with normalized quote swapping
            norm_canonical = normalize_quote_characters(canonical_question)
            norm_judgment = normalize_quote_characters(question_text)
            
            eq_with_quotes = norm_canonical.replace("'", '"') == norm_judgment.replace("'", '"')
            if eq_with_quotes:
                # Correction allowed
                judgment["question"] = canonical_question
                corrections.append({
                    "question_id": question_id,
                    "field": "question",
                    "type": "quote_style_correction",
                    "original_value": question_text,
                    "corrected_value": canonical_question
                })
                result.warnings.append(ValidationMessage(
                    question_id=filename_qid,
                    message=(
                        f"Quote style mismatch corrected for question '{question_id}'. "
                        f"Changed to standard double quote version: '{canonical_question}'."
                    ),
                    field="question"
                ))
            else:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Judgment question text does not match the canonical question text.\nCanonical: {canonical_question!r}\nActual   : {question_text!r}",
                    field="question"
                ))

        # 4. Retrieval Results alignment
        if question_id not in self.retrieval_by_qid:
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"Question ID '{question_id}' not found in retrieval results report.",
                field="question_id"
            ))
            return result, corrections

        retrieval_record = self.retrieval_by_qid[question_id]
        retrieved_chunks = retrieval_record.get("retrieved_chunks", [])
        retrieved_chunk_judgments = judgment.get("retrieved_chunk_judgments", [])

        if len(retrieved_chunk_judgments) != 10:
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"retrieved_chunk_judgments must contain exactly 10 records, got {len(retrieved_chunk_judgments)}.",
                field="retrieved_chunk_judgments"
            ))
        
        # Verify retrieved chunks by Rank mapping rather than raw position
        judgments_by_rank = {}
        for idx, item in enumerate(retrieved_chunk_judgments):
            if not isinstance(item, dict):
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"retrieved_chunk_judgments index {idx} is not a JSON object."
                ))
                continue
            r = item.get("rank")
            uid = item.get("chunk_uid")
            
            if r is None or not isinstance(r, int):
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"retrieved_chunk_judgments index {idx} has missing or non-integer rank."
                ))
                continue
            if r < 1 or r > 10:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"retrieved_chunk_judgments rank {r} out of bounds (1-10)."
                ))
                continue
            if r in judgments_by_rank:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Duplicate rank {r} found in retrieved_chunk_judgments."
                ))
            judgments_by_rank[r] = item

        # Verify physical ordering of chunks
        actual_ranks = [item.get("rank") for item in retrieved_chunk_judgments if isinstance(item, dict) and "rank" in item]
        if actual_ranks != list(range(1, 11)):
            result.warnings.append(ValidationMessage(
                question_id=filename_qid,
                message="retrieved_chunk_judgments array is not sorted by rank 1-10 in ascending order.",
                field="retrieved_chunk_judgments"
            ))

        # Check alignment rank-by-rank
        for rank in range(1, 11):
            if rank not in judgments_by_rank:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Missing rank {rank} in retrieved_chunk_judgments."
                ))
                continue
            
            j_chunk = judgments_by_rank[rank]
            expected_chunk = retrieved_chunks[rank - 1]
            
            if j_chunk.get("chunk_uid") != expected_chunk["chunk_uid"]:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Chunk UID mismatch at Rank {rank}: expected '{expected_chunk['chunk_uid']}', got '{j_chunk.get('chunk_uid')}'."
                ))

        # 5. Candidate Stories alignment checks
        candidate_story_orders = retrieval_record.get("candidate_story_orders", [])
        candidate_story_judgments = judgment.get("candidate_story_judgments", [])

        if not isinstance(candidate_story_judgments, list):
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message="candidate_story_judgments must be a JSON array.",
                field="candidate_story_judgments"
            ))
            return result, corrections

        actual_orders = []
        for idx, item in enumerate(candidate_story_judgments):
            if not isinstance(item, dict):
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"candidate_story_judgments index {idx} is not a JSON object."
                ))
                continue
            order = item.get("section_order")
            title = item.get("section_title")
            label = item.get("label")
            reason = item.get("reason")

            if order is None or not isinstance(order, int):
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"candidate_story_judgments index {idx} has missing or non-integer section_order."
                ))
                continue
            actual_orders.append(order)

            # Label verify
            valid_story_labels = {"directly_relevant", "partially_relevant", "topically_related", "irrelevant"}
            if label not in valid_story_labels:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Story label for section {order} must be one of {valid_story_labels}, got '{label}'."
                ))

            # Reason verify
            if not isinstance(reason, str) or not reason.strip():
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Story reason for section {order} must be a non-empty string."
                ))

            # Alignment with sections.jsonl title
            if order in self.sections_by_order:
                canonical_title = self.sections_by_order[order]["title"]
                if title != canonical_title:
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"Candidate story title mismatch for section {order}: expected {canonical_title!r}, got {title!r}."
                    ))

        # Check candidate stories set match
        if set(actual_orders) != set(candidate_story_orders):
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"Candidate stories mismatch: expected section_orders {candidate_story_orders}, got {actual_orders}.",
                field="candidate_story_judgments"
            ))

        # Verify duplicate section_order checks
        if len(actual_orders) != len(set(actual_orders)):
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"Duplicate section_orders found in candidate_story_judgments: {actual_orders}."
            ))

        # Verify physical ordering of stories
        if actual_orders != sorted(actual_orders):
            result.warnings.append(ValidationMessage(
                question_id=filename_qid,
                message="candidate_story_judgments array is not sorted by section_order in ascending order.",
                field="candidate_story_judgments"
            ))

        # 6. Retrieved Chunk Label and supports_answer checks
        direct_ranks = []
        for rank, item in judgments_by_rank.items():
            lbl = item.get("label")
            sup = item.get("supports_answer")
            resn = item.get("reason")

            valid_chunk_labels = {"direct_evidence", "supporting_context", "topically_related", "irrelevant", "contradictory"}
            if lbl not in valid_chunk_labels:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Chunk label at Rank {rank} must be one of {valid_chunk_labels}, got '{lbl}'."
                ))
            
            if not isinstance(resn, str) or not resn.strip():
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message=f"Reason at Rank {rank} must be a non-empty string."
                ))

            # supports_answer check
            if lbl in {"direct_evidence", "supporting_context"}:
                if sup is not True:
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"supports_answer must be true for chunk at Rank {rank} with label '{lbl}'."
                    ))
            elif lbl in {"topically_related", "irrelevant", "contradictory"}:
                if sup is not False:
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"supports_answer must be false for chunk at Rank {rank} with label '{lbl}'."
                    ))

            if lbl == "direct_evidence":
                direct_ranks.append(rank)

        # 7. first_direct_evidence_rank verification
        expected_first_rank = min(direct_ranks) if direct_ranks else None
        declared_first_rank = judgment["first_direct_evidence_rank"]

        if declared_first_rank != expected_first_rank:
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message=f"first_direct_evidence_rank mismatch: declared {declared_first_rank}, computed {expected_first_rank} based on labels.",
                field="first_direct_evidence_rank"
            ))

        # 8. Top-K Sufficiency validation
        sufficiency = judgment.get("top_k_sufficiency")
        if not isinstance(sufficiency, dict) or not all(k in sufficiency for k in ["top_1", "top_3", "top_5", "top_10"]):
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message="top_k_sufficiency must be a JSON object containing keys: top_1, top_3, top_5, top_10.",
                field="top_k_sufficiency"
            ))
        else:
            t1 = sufficiency["top_1"]
            t3 = sufficiency["top_3"]
            t5 = sufficiency["top_5"]
            t10 = sufficiency["top_10"]

            if not all(isinstance(v, bool) for v in [t1, t3, t5, t10]):
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message="top_k_sufficiency values must be booleans.",
                    field="top_k_sufficiency"
                ))
            
            # Monotonicity check
            if t1 and not (t3 and t5 and t10):
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message="top_k_sufficiency monotonicity violated: top_1 is true but top_3, top_5, or top_10 is false.",
                    field="top_k_sufficiency"
                ))
            if t3 and not (t5 and t10):
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message="top_k_sufficiency monotonicity violated: top_3 is true but top_5 or top_10 is false.",
                    field="top_k_sufficiency"
                ))
            if t5 and not t10:
                result.errors.append(ValidationMessage(
                    question_id=filename_qid,
                    message="top_k_sufficiency monotonicity violated: top_5 is true but top_10 is false.",
                    field="top_k_sufficiency"
                ))

        # 9. Missing evidence quotes verification
        missing_evidence = judgment.get("missing_evidence_within_candidate_stories", [])
        if not isinstance(missing_evidence, list):
            result.errors.append(ValidationMessage(
                question_id=filename_qid,
                message="missing_evidence_within_candidate_stories must be a JSON array.",
                field="missing_evidence_within_candidate_stories"
            ))
        else:
            missing_orders = []
            for idx, item in enumerate(missing_evidence):
                if not isinstance(item, dict):
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"missing_evidence_within_candidate_stories index {idx} is not a JSON object."
                    ))
                    continue
                m_order = item.get("section_order")
                m_title = item.get("section_title")
                m_quote = item.get("evidence_quote")
                m_reason = item.get("reason")

                if m_order is None or not isinstance(m_order, int):
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"missing_evidence_within_candidate_stories index {idx} has missing or non-integer section_order."
                    ))
                    continue
                
                missing_orders.append(m_order)

                if not isinstance(m_quote, str) or not m_quote.strip():
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"missing_evidence index {idx} has empty evidence_quote."
                    ))
                    continue
                if not isinstance(m_reason, str) or not m_reason.strip():
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"missing_evidence index {idx} has empty reason."
                    ))

                # section_order must belong to current Candidate Stories
                if m_order not in candidate_story_orders:
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"missing_evidence section_order {m_order} is not in candidate stories {candidate_story_orders}."
                    ))
                    continue

                # Title verify
                canonical_title = self.sections_by_order[m_order]["title"]
                if m_title != canonical_title:
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"missing_evidence section_title mismatch for section {m_order}: expected {canonical_title!r}, got {m_title!r}."
                    ))

                # Standardized search in story text (handles ellipses in quotes)
                raw_quote_parts = [p.strip() for p in m_quote.split("...") if p.strip()]
                if not raw_quote_parts:
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"evidence_quote for section {m_order} is empty or invalid."
                    ))
                    continue

                story_text = self.sections_by_order[m_order]["text"]
                norm_story = normalize_evidence_text(story_text)

                current_idx = 0
                match_failed = False
                for part in raw_quote_parts:
                    norm_part = normalize_evidence_text(part)
                    idx = norm_story.find(norm_part, current_idx)
                    if idx == -1:
                        match_failed = True
                        break
                    current_idx = idx + len(norm_part)

                if match_failed:
                    result.errors.append(ValidationMessage(
                        question_id=filename_qid,
                        message=f"evidence_quote for section {m_order} not found in story source text.\nNormalized Quote: {normalize_evidence_text(m_quote)!r}"
                    ))

            # Verify physical ordering of missing evidence
            if missing_orders != sorted(missing_orders):
                result.warnings.append(ValidationMessage(
                    question_id=filename_qid,
                    message="missing_evidence_within_candidate_stories array is not sorted by section_order in ascending order.",
                    field="missing_evidence_within_candidate_stories"
                ))

        return result, corrections
