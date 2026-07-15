import json
from pathlib import Path
from typing import Optional
from app.evaluation.metric_calculator import MetricCalculator

class EvaluationBuilder:
    """
    Builds the consolidated frontend baseline_evaluation.json bundle by merging
    canonical content source, retrieval statistics, subjective judgments,
    and computed metric details.
    """
    @staticmethod
    def load_jsonl(path: Path) -> list[dict]:
        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    @classmethod
    def build_evaluation(
        cls,
        document_path: Path,
        sections_path: Path,
        chunks_path: Path,
        questions_config: dict,
        retrieval_results: dict,
        judgments: dict[str, dict], # question_id -> judgment_dict
        content_ingestion_report_path: Optional[Path] = None,
        embedding_ingestion_report_path: Optional[Path] = None,
        embedding_report_path: Optional[Path] = None,
    ) -> dict:
        """
        Integrates and normalizes all evaluation fields into the final frontend payload.
        """
        # 1. Load book metadata and content collections
        with document_path.open("r", encoding="utf-8") as f:
            doc_data = json.load(f)

        raw_sections = cls.load_jsonl(sections_path)
        raw_chunks = cls.load_jsonl(chunks_path)

        actual_sections_count = len(raw_sections)
        actual_chunks_count = len(raw_chunks)

        # 2. Pipeline verification checks against report JSONs
        if content_ingestion_report_path and content_ingestion_report_path.exists():
            with content_ingestion_report_path.open("r", encoding="utf-8") as f:
                cir = json.load(f)
            if cir.get("section_count") != actual_sections_count:
                raise ValueError(
                    f"Consistency mismatch: content_ingestion_report section_count={cir.get('section_count')}, "
                    f"but sections.jsonl contains {actual_sections_count} sections."
                )
            if cir.get("chunk_count") != actual_chunks_count:
                raise ValueError(
                    f"Consistency mismatch: content_ingestion_report chunk_count={cir.get('chunk_count')}, "
                    f"but chunks.jsonl contains {actual_chunks_count} chunks."
                )

        max_chunk_tokens = 0
        if raw_chunks:
            max_chunk_tokens = max(c["token_count"] for c in raw_chunks)

        emb_model = "sentence-transformers/all-MiniLM-L6-v2"
        emb_dims = 384
        emb_norm = True
        
        if embedding_report_path and embedding_report_path.exists():
            with embedding_report_path.open("r", encoding="utf-8") as f:
                er = json.load(f)
            if er.get("chunk_count") != actual_chunks_count:
                raise ValueError(
                    f"Consistency mismatch: embedding_report chunk_count={er.get('chunk_count')}, "
                    f"but chunks.jsonl contains {actual_chunks_count} chunks."
                )
            emb_model = er.get("model_name", emb_model)
            emb_dims = er.get("dimensions", emb_dims)
            emb_norm = er.get("normalized", emb_norm)

        db_embedding_count = actual_chunks_count
        if embedding_ingestion_report_path and embedding_ingestion_report_path.exists():
            with embedding_ingestion_report_path.open("r", encoding="utf-8") as f:
                eir = json.load(f)
            if eir.get("inserted_embedding_count") != actual_chunks_count:
                raise ValueError(
                    f"Consistency mismatch: embedding_ingestion_report inserted_embedding_count={eir.get('inserted_embedding_count')}, "
                    f"but chunks.jsonl contains {actual_chunks_count} chunks."
                )
            db_embedding_count = eir.get("inserted_embedding_count", db_embedding_count)

        # 3. Build lookup maps for verification
        sections_by_order = {s["section_order"]: s for s in raw_sections}
        chunks_by_id = {c["chunk_id"]: c for c in raw_chunks}

        # 4. Integrate Pipeline Metadata
        experiment_id = questions_config["experiment_id"]
        document_id = questions_config["document_id"]
        top_k = questions_config["top_k"]
        generation_id = retrieval_results.get("generation_id")

        pipeline_metadata = {
            "steps": [
                {
                    "step_id": "document_cleaning",
                    "name": "Document Cleaning",
                    "status": "completed"
                },
                {
                    "step_id": "section_splitting",
                    "name": "Story Splitting",
                    "status": "completed",
                    "section_count": actual_sections_count
                },
                {
                    "step_id": "chunking",
                    "name": "Sentence-Aware Chunking",
                    "status": "completed",
                    "chunk_count": actual_chunks_count,
                    "maximum_tokens": max_chunk_tokens
                },
                {
                    "step_id": "embedding",
                    "name": "MiniLM Embedding",
                    "status": "completed",
                    "model_name": emb_model,
                    "dimensions": emb_dims,
                    "normalized": emb_norm
                },
                {
                    "step_id": "database",
                    "name": "PostgreSQL and pgvector",
                    "status": "completed",
                    "embedding_count": db_embedding_count
                },
                {
                    "step_id": "retrieval",
                    "name": "Exact Cosine Top 10",
                    "status": "completed",
                    "question_count": len(questions_config.get("questions", []))
                },
                {
                    "step_id": "evaluation",
                    "name": "LLM-Assisted Retrieval Evaluation",
                    "status": "completed"
                }
            ]
        }

        # 5. Process each question
        retrieval_by_qid = {res["question_id"]: res for res in retrieval_results.get("results", [])}
        questions_list = []
        computed_metrics_list = []

        # Sort questions by question_id ascending
        sorted_questions_config = sorted(questions_config.get("questions", []), key=lambda x: x["question_id"])

        for q in sorted_questions_config:
            qid = q["question_id"]
            judgment_dict = judgments[qid]
            retrieved_record = retrieval_by_qid[qid]
            retrieved_chunks = retrieved_record.get("retrieved_chunks", [])

            # Merge and verify retrieved chunks against chunks.jsonl source
            merged_chunks = []
            judgments_by_rank = {item["rank"]: item for item in judgment_dict["retrieved_chunk_judgments"]}

            for retrieved_chunk in retrieved_chunks:
                rank = retrieved_chunk["rank"]
                uid = retrieved_chunk["chunk_uid"]

                # Chunk check against chunks.jsonl
                if uid not in chunks_by_id:
                    raise ValueError(f"Chunk '{uid}' in retrieval results for question '{qid}' does not exist in chunks.jsonl.")
                
                canonical_chunk = chunks_by_id[uid]
                
                if (retrieved_chunk["section_order"] != canonical_chunk["section_order"] or
                    retrieved_chunk["section_title"] != canonical_chunk["section_title"] or
                    retrieved_chunk["chunk_order"] != canonical_chunk["chunk_order"] or
                    retrieved_chunk["token_count"] != canonical_chunk["token_count"] or
                    retrieved_chunk["chunk_text"] != canonical_chunk["text"]):
                    raise ValueError(f"Chunk '{uid}' in retrieval results does not match chunks.jsonl data.")

                j_item = judgments_by_rank[rank]
                merged_chunks.append({
                    "rank": rank,
                    "chunk_uid": uid,
                    "section_order": retrieved_chunk["section_order"],
                    "section_title": retrieved_chunk["section_title"],
                    "chunk_order": retrieved_chunk["chunk_order"],
                    "token_count": retrieved_chunk["token_count"],
                    "cosine_distance": retrieved_chunk["cosine_distance"],
                    "cosine_similarity": retrieved_chunk["cosine_similarity"],
                    "chunk_text": retrieved_chunk["chunk_text"],
                    "judgment": {
                        "label": j_item["label"],
                        "supports_answer": j_item["supports_answer"],
                        "reason": j_item["reason"]
                    }
                })

            # Calculate question computed metrics
            first_direct_evidence_rank = judgment_dict["first_direct_evidence_rank"]
            sufficiency = judgment_dict["top_k_sufficiency"]
            computed = MetricCalculator.compute_question_metrics(
                retrieved_chunk_judgments=judgment_dict["retrieved_chunk_judgments"],
                sufficiency=sufficiency,
                first_direct_evidence_rank=first_direct_evidence_rank
            )
            computed_metrics_list.append(computed)

            # Sort items by section_order / rank / etc before writing
            candidate_story_judgments = sorted(
                judgment_dict["candidate_story_judgments"],
                key=lambda x: x["section_order"]
            )
            sorted_merged_chunks = sorted(merged_chunks, key=lambda x: x["rank"])
            missing_evidence = sorted(
                judgment_dict["missing_evidence_within_candidate_stories"],
                key=lambda x: x["section_order"]
            )

            questions_list.append({
                "question_id": qid,
                "category": q["category"],
                "question": q["question"],
                "question_interpretation": judgment_dict["question_interpretation"],
                "reference_answer": judgment_dict["reference_answer"],
                "retrieval": {
                    "query_token_count": retrieved_record["query_token_count"],
                    "embedding_duration_ms": retrieved_record["embedding_duration_ms"],
                    "database_duration_ms": retrieved_record["database_duration_ms"],
                    "candidate_story_orders": retrieved_record["candidate_story_orders"]
                },
                "candidate_story_judgments": candidate_story_judgments,
                "retrieved_chunks": sorted_merged_chunks,
                "missing_evidence_within_candidate_stories": missing_evidence,
                "judge_assessment": {
                    "retrieval_quality": judgment_dict["overall_assessment"]["retrieval_quality"],
                    "score_0_to_100": judgment_dict["overall_assessment"]["score_0_to_100"],
                    "summary": judgment_dict["overall_assessment"]["summary"],
                    "confidence": judgment_dict["confidence"]
                },
                "computed_metrics": computed
            })

        # 6. Aggregate metrics across all questions
        aggregate_metrics = MetricCalculator.compute_aggregate_metrics(computed_metrics_list)

        # 7. Formulate document and sorted stories sections
        document_meta = {
            "document_id": document_id,
            "title": doc_data.get("title", "The Adventures of Sherlock Holmes"),
            "author": doc_data.get("author", "Arthur Conan Doyle"),
            "source_name": doc_data.get("source_name", "Project Gutenberg"),
            "source_reference": doc_data.get("source_reference", "1661")
        }

        stories_payload = []
        sorted_sections = sorted(raw_sections, key=lambda x: x["section_order"])
        for sec in sorted_sections:
            stories_payload.append({
                "section_order": sec["section_order"],
                "section_title": sec["title"],
                "section_text": sec["text"]
            })

        experiment_metadata = {
            "experiment_id": experiment_id,
            "evaluation_type": "llm_assisted_human_reviewed",
            "question_count": len(sorted_questions_config),
            "top_k": top_k,
            "retrieval_method": "exact_cosine",
            "generated_at_utc": retrieval_results.get("generated_at_utc", ""),
            "generation_id": generation_id,
            "judgment_schema_version": "1.0"
        }

        # Formulate source provenance details
        # The hashes are set at the CLI orchestrator level or computed
        source_provenance = {}

        return {
            "schema_version": "1.0",
            "experiment": experiment_metadata,
            "pipeline": pipeline_metadata,
            "document": document_meta,
            "stories": stories_payload,
            "aggregate_metrics": aggregate_metrics,
            "questions": questions_list
        }
