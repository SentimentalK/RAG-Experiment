import argparse
import json
import logging
import sys
import uuid
import hashlib
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.providers.minilm_provider import MiniLMProvider
from app.services.vector_search_service import VectorSearchService

logger = logging.getLogger("prepare_baseline_packets")

def calculate_sha256(path: Path) -> str:
    """
    Computes the SHA-256 hash of a file.
    """
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def load_jsonl(path: Path) -> list[dict]:
    """
    Loads JSONL records into a list of dicts.
    """
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def prepare_baseline_packets(
    questions_path: Path,
    sections_path: Path,
    results_output: Path,
    prompt_path: Path,
    packets_output: Path,
    search_service: VectorSearchService,
) -> dict:
    """
    Core function to validate inputs, run queries, generate packets in staging,
    verify everything, publish results, and clean up staging.
    """
    generation_id = uuid.uuid4().hex
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Calculate file hashes for reproducibility
    questions_sha = calculate_sha256(questions_path)
    sections_sha = calculate_sha256(sections_path)
    prompt_sha = calculate_sha256(prompt_path)

    # 2. Load questions
    with questions_path.open("r", encoding="utf-8") as f:
        questions_config = json.load(f)

    # Validate questions config structure
    experiment_id = questions_config.get("experiment_id")
    document_id = questions_config.get("document_id")
    top_k = questions_config.get("top_k")
    questions = questions_config.get("questions", [])

    if not experiment_id or not str(experiment_id).strip():
        raise ValueError("questions.json 'experiment_id' cannot be empty.")
    if not document_id or not str(document_id).strip():
        raise ValueError("questions.json 'document_id' cannot be empty.")
    if top_k != 10:
        raise ValueError(f"questions.json 'top_k' must be 10, got {top_k}.")
    if len(questions) != 8:
        raise ValueError(f"questions.json 'questions' must have exactly 8 questions, got {len(questions)}.")

    seen_qids = set()
    for idx, q in enumerate(questions, start=1):
        qid = q.get("question_id")
        cat = q.get("category")
        text = q.get("question")
        if not qid or not str(qid).strip():
            raise ValueError(f"Question index {idx} has empty 'question_id'.")
        if qid in seen_qids:
            raise ValueError(f"Duplicate 'question_id' found: {qid}.")
        seen_qids.add(qid)
        if not cat or not str(cat).strip():
            raise ValueError(f"Question '{qid}' category cannot be empty.")
        if not text or not str(text).strip():
            raise ValueError(f"Question '{qid}' query text cannot be empty.")

    # 3. Load sections
    sections_list = load_jsonl(sections_path)
    sections_by_order = {s["section_order"]: s for s in sections_list}

    # 4. Initialize Staging Directory
    staging_dir = results_output.parent / ".staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    
    staging_packets_dir = staging_dir / "packets"
    staging_packets_dir.mkdir(parents=True)

    try:
        # Load Judge Prompt
        with prompt_path.open("r", encoding="utf-8") as f:
            judge_prompt_content = f.read()

        results_list = []
        print("\nRunning searches:")

        for q in questions:
            qid = q["question_id"]
            question_text = q["question"]
            category = q["category"]

            # Execute vector search
            res = search_service.search(question_text, document_id, top_k=10)

            retrieved = res["results"]
            if len(retrieved) != 10:
                raise ValueError(f"Query '{qid}' returned {len(retrieved)} results, expected exactly 10.")

            # Validate retrieved chunks integrity and sorting
            seen_chunk_uids = set()
            distances = []
            for rank_idx, item in enumerate(retrieved, start=1):
                if item["rank"] != rank_idx:
                    raise ValueError(f"Query '{qid}' rank sequence broken: got rank {item['rank']} at index {rank_idx}.")
                
                uid = item["chunk_uid"]
                if uid in seen_chunk_uids:
                    raise ValueError(f"Query '{qid}' returned duplicate chunk_uid: '{uid}'.")
                seen_chunk_uids.add(uid)

                # Float validation for distance-similarity relation
                dist = item["cosine_distance"]
                sim = item["cosine_similarity"]
                if not math.isclose(sim, 1.0 - dist, abs_tol=1e-6):
                    raise ValueError(f"Similarity mismatch for chunk {uid} in query '{qid}': similarity={sim}, 1 - distance={1.0 - dist}.")

                # Section order check
                sec_order = item["section_order"]
                if sec_order not in sections_by_order:
                    raise ValueError(f"Chunk {uid} references non-existent section_order: {sec_order}.")

                # Title alignment check
                source_section = sections_by_order[sec_order]
                if item["section_title"] != source_section["title"]:
                    raise ValueError(
                        f"Section title mismatch for {uid} in query '{qid}': "
                        f"retrieval={item['section_title']!r}, source={source_section['title']!r}."
                    )

                distances.append(dist)

            # Check that results are sorted non-decreasingly by distance
            for i in range(len(distances) - 1):
                if distances[i] > distances[i + 1] + 1e-9:
                    raise ValueError(f"Query '{qid}' search results are not sorted non-decreasingly by distance: {distances}.")

            # Generate candidate story orders list
            candidate_story_orders = sorted(list({item["section_order"] for item in retrieved}))

            results_list.append({
                "question_id": qid,
                "category": category,
                "question": question_text,
                "query_token_count": res["query_token_count"],
                "embedding_duration_ms": res["embedding_duration_ms"],
                "database_duration_ms": res["database_duration_ms"],
                "candidate_story_orders": candidate_story_orders,
                "retrieved_chunks": retrieved
            })

            print(f"  {qid}: 10 results, {len(candidate_story_orders)} candidate stories")

            # 5. Build Markdown Packet Content
            packet_lines = [
                "# Semantic Retrieval Evaluation Packet\n",
                "## Experiment\n",
                f"- Generation ID: {generation_id}",
                f"- Experiment ID: {experiment_id}",
                f"- Document: The Adventures of Sherlock Holmes",
                f"- Embedding model: {search_service._provider.model_name}",
                f"- Retrieval method: PostgreSQL exact cosine search",
                f"- Top K: 10\n",
                "## Question\n",
                f"- Question ID: {qid}",
                f"- Category: {category}\n",
                f"{question_text}\n",
                "## Retrieved Top 10\n"
            ]

            for item in retrieved:
                packet_lines.extend([
                    f"### Rank {item['rank']}\n",
                    f"- Chunk ID: {item['chunk_uid']}",
                    f"- Story: {item['section_title']}",
                    f"- Story order: {item['section_order']}",
                    f"- Chunk order: {item['chunk_order']}",
                    f"- Token count: {item['token_count']}",
                    f"- Cosine distance: {item['cosine_distance']:.6f}",
                    f"- Cosine similarity: {item['cosine_similarity']:.6f}\n",
                    f'<retrieved_chunk rank="{item["rank"]}" chunk_uid="{item["chunk_uid"]}" section_order="{item["section_order"]}" section_title="{item["section_title"]}">\n',
                    f"{item['chunk_text']}\n",
                    "</retrieved_chunk>\n",
                    "---"
                ])
            
            # Remove trailing '---' divider
            if packet_lines and packet_lines[-1] == "---":
                packet_lines.pop()

            packet_lines.extend(["", "## Complete Candidate Stories\n"])

            # Append complete stories text sorted by section_order
            for order in candidate_story_orders:
                sec = sections_by_order[order]
                packet_lines.extend([
                    f"### Story {order}: {sec['title']}\n",
                    f'<candidate_story section_order="{order}" section_title="{sec["title"]}">\n',
                    f"{sec['text']}\n",
                    "</candidate_story>\n",
                    "---"
                ])

            if packet_lines and packet_lines[-1] == "---":
                packet_lines.pop()

            packet_lines.extend([
                "",
                "## Evaluation Instructions\n",
                judge_prompt_content
            ])

            # Save temporary Markdown packet
            staging_pkt_path = staging_packets_dir / f"{qid}.md"
            with staging_pkt_path.open("w", encoding="utf-8") as f:
                f.write("\n".join(packet_lines))

        # 6. Save temporary retrieval results report
        results_report = {
            "generation_id": generation_id,
            "experiment_id": experiment_id,
            "document_id": document_id,
            "model_name": search_service._provider.model_name,
            "retrieval_method": "exact_cosine",
            "top_k": 10,
            "question_count": len(questions),
            "generated_at_utc": generated_at,
            "question_file_sha256": questions_sha,
            "sections_file_sha256": sections_sha,
            "judge_prompt_sha256": prompt_sha,
            "results": results_list
        }

        staging_results_path = staging_dir / "retrieval_results.json"
        with staging_results_path.open("w", encoding="utf-8") as f:
            json.dump(results_report, f, indent=2, ensure_ascii=False)

        # 7. Perform Staging Verification Checks
        if not staging_results_path.exists():
            raise FileNotFoundError("Staging verification failed: retrieval_results.json not found in staging.")
        
        # Verify 8 MD packet files
        for q in questions:
            qid = q["question_id"]
            md_file = staging_packets_dir / f"{qid}.md"
            if not md_file.exists():
                raise FileNotFoundError(f"Staging verification failed: packet file '{qid}.md' not found in staging.")

        # 8. Publish Stage: Success! Move staging files to official experiments dir
        if packets_output.exists():
            shutil.rmtree(packets_output)
        packets_output.mkdir(parents=True, exist_ok=True)

        for p_file in staging_packets_dir.glob("*.md"):
            shutil.move(str(p_file), str(packets_output / p_file.name))

        results_output.parent.mkdir(parents=True, exist_ok=True)
        # Safe move JSON
        if results_output.exists():
            results_output.unlink()
        shutil.move(str(staging_results_path), str(results_output))

        return {
            "generation_id": generation_id,
            "question_count": len(questions),
            "output_json": results_output,
            "output_packets_dir": packets_output
        }

    except Exception as e:
        logger.error(f"Error during packet generation: {e}")
        raise e
    finally:
        # Recursively remove staging directory
        if staging_dir.exists():
            shutil.rmtree(staging_dir)

def main():
    parser = argparse.ArgumentParser(description="Generate evaluation baseline packets for RAG experiments.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "questions.json",
        help="Path to questions.json"
    )
    parser.add_argument(
        "--sections",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "sections.jsonl",
        help="Path to sections.jsonl"
    )
    parser.add_argument(
        "--results-output",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "retrieval_results.json",
        help="Path to retrieval_results.json output"
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "judge_prompt.md",
        help="Path to judge_prompt.md"
    )
    parser.add_argument(
        "--packets-output",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "packets",
        help="Directory to save MD packets"
    )

    args = parser.parse_args()

    # 1. Verify existence of raw inputs
    for name, path in [("questions", args.questions), ("sections", args.sections), ("prompt", args.prompt)]:
        if not path.exists():
            print(f"Error: {name} file does not exist at {path}", file=sys.stderr)
            sys.exit(1)

    print("Loading experiment:")
    print(f"  Experiment: minilm-exact-baseline-v1")
    print(f"  Questions: 8")
    print(f"  Document: gutenberg-1661")
    print(f"  Top K: 10")

    print("\nLoading stories:")
    # Counts lines to print loading info
    sections_count = 0
    with args.sections.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sections_count += 1
    print(f"  Sections loaded: {sections_count}")

    try:
        # Load single instances of MiniLM model & search service
        provider = MiniLMProvider(device="cpu")
        search_service = VectorSearchService(provider)

        stats = prepare_baseline_packets(
            questions_path=args.questions,
            sections_path=args.sections,
            results_output=args.results_output,
            prompt_path=args.prompt,
            packets_output=args.packets_output,
            search_service=search_service
        )

        print("\nOutputs:")
        print(f"  {stats['output_json']}")
        for q_idx in range(1, 9):
            print(f"  {stats['output_packets_dir']}/q00{q_idx}.md")
        
        print("\nStatus: success")

    except Exception as e:
        print(f"\nExecution failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
