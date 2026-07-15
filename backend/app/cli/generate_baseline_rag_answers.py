import sys
import json
import hashlib
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone

from app.core.config import settings
from app.clients.groq_gpt_oss_client import GroqGptOssClient, GroqApiError
from app.services.rag_answer_service import RagAnswerService, InvalidRagResponseError
from app.schemas.rag_answers_file import RagAnswersFile, RagAnswerItem, RagAnswersContext, RagAnswersGeneration
from app.schemas.rag_answer import Citation, TokenUsage

def calculate_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def load_jsonl(file_path: Path) -> list[dict]:
    records = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def main():
    # 1. Define paths
    base_eval_dir = settings.DATA_DIR.parent / "experiments" / "baseline_v1"
    questions_path = base_eval_dir / "questions.json"
    retrieval_path = base_eval_dir / "retrieval_results.json"
    chunks_path = settings.PROCESSED_DATA_DIR / "chunks.jsonl"
    output_path = base_eval_dir / "rag_answers.json"

    print("Loading baseline retrieval results...")
    
    # Check paths exist
    for label, path in [
        ("questions.json", questions_path),
        ("retrieval_results.json", retrieval_path),
        ("chunks.jsonl", chunks_path)
    ]:
        if not path.exists():
            print(f"Error: {label} not found at {path}", file=sys.stderr)
            sys.exit(1)

    # Calculate SHA256 of retrieval_results.json
    retrieval_sha256 = calculate_sha256(retrieval_path)

    # 2. Load files
    try:
        with questions_path.open("r", encoding="utf-8") as f:
            questions_config = json.load(f)
        with retrieval_path.open("r", encoding="utf-8") as f:
            retrieval_results = json.load(f)
        raw_chunks = load_jsonl(chunks_path)
    except Exception as e:
        print(f"Error loading inputs: {e}", file=sys.stderr)
        sys.exit(1)

    # Map chunks by chunk_id
    chunks_by_id = {c["chunk_id"]: c for c in raw_chunks}

    # 3. Perform strict validation on retrieval inputs
    questions_list = questions_config.get("questions", [])
    if len(questions_list) != 8:
        print(f"Error: questions.json must contain exactly 8 questions, got {len(questions_list)}.", file=sys.stderr)
        sys.exit(1)

    retrieval_records = retrieval_results.get("results", [])
    if len(retrieval_records) != 8:
        print(f"Error: retrieval_results.json must contain exactly 8 results, got {len(retrieval_records)}.", file=sys.stderr)
        sys.exit(1)

    # Sort and verify sequences
    sorted_q_config = sorted(questions_list, key=lambda x: x["question_id"])
    sorted_retrieval = sorted(retrieval_records, key=lambda x: x["question_id"])

    for idx in range(8):
        q_conf = sorted_q_config[idx]
        q_ret = sorted_retrieval[idx]
        qid = f"q{idx+1:03d}"

        # Sequence match q001-q008
        if q_conf["question_id"] != qid or q_ret["question_id"] != qid:
            print(f"Error: Mismatched or missing sequence ID at index {idx}. Expected {qid}.", file=sys.stderr)
            sys.exit(1)

        # Question text match
        if q_conf["question"] != q_ret["question"]:
            print(f"Error: Question text mismatch for {qid}.\nConfig: {q_conf['question']}\nRetrieval: {q_ret['question']}", file=sys.stderr)
            sys.exit(1)

        retrieved_chunks = q_ret.get("retrieved_chunks", [])
        if len(retrieved_chunks) != 10:
            print(f"Error: Question {qid} must contain exactly 10 retrieved chunks, got {len(retrieved_chunks)}.", file=sys.stderr)
            sys.exit(1)

        # Check rank continuity and chunk duplicates
        ranks = [rc["rank"] for rc in retrieved_chunks]
        if ranks != list(range(1, 11)):
            print(f"Error: Chunk ranks for {qid} must be contiguous 1 to 10, got {ranks}.", file=sys.stderr)
            sys.exit(1)

        chunk_uids = [rc["chunk_uid"] for rc in retrieved_chunks]
        if len(chunk_uids) != len(set(chunk_uids)):
            print(f"Error: Duplicate chunk UIDs found in {qid}.", file=sys.stderr)
            sys.exit(1)

        # Cross check against chunks.jsonl
        for rc in retrieved_chunks:
            uid = rc["chunk_uid"]
            if uid not in chunks_by_id:
                print(f"Error: Chunk '{uid}' in retrieval results for {qid} not found in chunks.jsonl.", file=sys.stderr)
                sys.exit(1)
            
            canonical_chunk = chunks_by_id[uid]
            if (rc["section_order"] != canonical_chunk["section_order"] or
                rc["section_title"] != canonical_chunk["section_title"] or
                rc["chunk_order"] != canonical_chunk["chunk_order"] or
                rc["token_count"] != canonical_chunk["token_count"] or
                rc["chunk_text"].strip() != canonical_chunk["text"].strip()):
                print(f"Error: Chunk '{uid}' details in retrieval results do not match chunks.jsonl.", file=sys.stderr)
                sys.exit(1)

    print("Validated 8 questions and 80 retrieved chunks.")

    # 4. Initialize RAG Services
    try:
        # We pass a None mock search service since generate_answer_from_context does not use it
        groq_client = GroqGptOssClient(settings)
        rag_service = RagAnswerService(search_service=None, groq_client=groq_client)
    except Exception as e:
        print(f"Error during initialization: {e}", file=sys.stderr)
        sys.exit(1)

    generation_id = str(uuid.uuid4()).replace("-", "")
    generated_answers = []

    # 5. Run sequential generation
    for idx, q_ret in enumerate(sorted_retrieval, start=1):
        if idx > 1:
            print("Rate limit mitigation: sleeping for 25 seconds...")
            import time
            time.sleep(25)
        qid = q_ret["question_id"]
        question_text = q_ret["question"]
        ret_chunks = q_ret["retrieved_chunks"]

        print(f"\n[{idx}/8] {qid}")

        # Setup retrieval metadata payload
        retrieval_meta = {
            "model_name": retrieval_results["model_name"],
            "top_k": 10,
            "embedding_duration_ms": q_ret["embedding_duration_ms"],
            "database_duration_ms": q_ret["database_duration_ms"]
        }

        try:
            # Generate RAG answer from context
            rag_response = rag_service.generate_answer_from_context(
                question=question_text,
                retrieved_chunks=ret_chunks,
                document_id="gutenberg-1661",
                retrieval_meta=retrieval_meta
            )
        except (GroqApiError, InvalidRagResponseError) as e:
            print(f"\n{qid} failed:\n{e}\n\nNo output was published.", file=sys.stderr)
            groq_client.close()
            sys.exit(1)
        except Exception as e:
            print(f"\n{qid} failed with unexpected error:\n{e}\n\nNo output was published.", file=sys.stderr)
            groq_client.close()
            sys.exit(1)

        gen = rag_response.generation
        print(f"  Model: {gen.model_name}")
        print(f"  Evidence sufficient: {'yes' if gen.evidence_sufficient else 'no'}")
        print(f"  Citations: {len(gen.citations)}")
        print(f"  Duration: {gen.generation_duration_ms:.1f} ms")
        print(f"  Attempts: {gen.attempt_count}")

        # Map to Pydantic items
        citations_mapped = [
            Citation(chunk_uid=c.chunk_uid, reason=c.reason)
            for c in gen.citations
        ]
        
        usage_mapped = TokenUsage(
            prompt_tokens=gen.usage.prompt_tokens,
            completion_tokens=gen.usage.completion_tokens,
            total_tokens=gen.usage.total_tokens
        )

        gen_mapped = RagAnswersGeneration(
            model_name=gen.model_name,
            answer=gen.answer,
            evidence_sufficient=gen.evidence_sufficient,
            citations=citations_mapped,
            confidence=gen.confidence,
            generation_duration_ms=gen.generation_duration_ms,
            attempt_count=gen.attempt_count,
            usage=usage_mapped
        )

        context_mapped = RagAnswersContext(
            top_k=10,
            chunk_uids=[rc["chunk_uid"] for rc in ret_chunks]
        )

        answer_item = RagAnswerItem(
            question_id=qid,
            question=question_text,
            context=context_mapped,
            generation=gen_mapped
        )
        generated_answers.append(answer_item)

    groq_client.close()

    # 6. Assemble output file structure
    answers_file_payload = RagAnswersFile(
        schema_version="1.0",
        experiment_id="minilm-exact-baseline-v1",
        generation_id=generation_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        generation_model=settings.GROQ_MODEL,
        prompt_version="rag-grounded-v1",
        retrieval_results_sha256=retrieval_sha256,
        question_count=8,
        answers=generated_answers
    )

    # 7. Safe Staging and Atomic Replacement
    staging_dir = base_eval_dir / ".staging" / generation_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    staging_path = staging_dir / "rag_answers.json"
    
    try:
        # Write staging file
        with staging_path.open("w", encoding="utf-8") as f:
            json.dump(answers_file_payload.model_dump(), f, indent=2, ensure_ascii=False)

        # Read back and parse
        with staging_path.open("r", encoding="utf-8") as f:
            json.load(f)

        # Atomic replace
        output_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path.replace(output_path)
    except Exception as io_err:
        print(f"Error publishing file: {io_err}", file=sys.stderr)
        sys.exit(1)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)

    print(f"\nPublished:\n{output_path}\n")

if __name__ == "__main__":
    main()
