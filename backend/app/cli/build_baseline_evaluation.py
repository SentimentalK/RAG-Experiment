import argparse
import json
import logging
import sys
import hashlib
import shutil
from pathlib import Path
from app.core.config import settings
from app.evaluation.judgment_validator import JudgmentValidator, ValidationResult
from app.evaluation.evaluation_builder import EvaluationBuilder

logger = logging.getLogger("build_baseline_evaluation")

def calculate_sha256(path: Path) -> str:
    """
    Computes the SHA-256 hash of a file.
    """
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Validate baseline judgments and compile frontend evaluation package.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "questions.json",
        help="Path to questions.json"
    )
    parser.add_argument(
        "--retrieval-results",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "retrieval_results.json",
        help="Path to retrieval_results.json"
    )
    parser.add_argument(
        "--judgments",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "judgments",
        help="Directory containing q001.json ... q008.json"
    )
    parser.add_argument(
        "--document",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "document.json",
        help="Path to document.json"
    )
    parser.add_argument(
        "--sections",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "sections.jsonl",
        help="Path to sections.jsonl"
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "chunks.jsonl",
        help="Path to chunks.jsonl"
    )
    parser.add_argument(
        "--validation-output",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "generated" / "validation_report.json",
        help="Path to validation_report.json"
    )
    parser.add_argument(
        "--evaluation-output",
        type=Path,
        default=settings.DATA_DIR.parent / "experiments" / "baseline_v1" / "generated" / "baseline_evaluation.json",
        help="Path to baseline_evaluation.json"
    )
    parser.add_argument(
        "--embedding-report",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "embedding_report.json",
        help="Path to embedding_report.json"
    )
    parser.add_argument(
        "--content-ingestion-report",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "content_ingestion_report.json",
        help="Path to content_ingestion_report.json"
    )
    parser.add_argument(
        "--embedding-ingestion-report",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "embedding_ingestion_report.json",
        help="Path to embedding_ingestion_report.json"
    )

    args = parser.parse_args()

    # 1. Verify that all required files and directories exist
    required_paths = [
        ("questions", args.questions),
        ("retrieval-results", args.retrieval_results),
        ("judgments dir", args.judgments),
        ("document", args.document),
        ("sections", args.sections),
        ("chunks", args.chunks)
    ]
    for name, path in required_paths:
        if not path.exists():
            print(f"Error: Required {name} path does not exist at '{path}'.", file=sys.stderr)
            sys.exit(1)

    print("Loading baseline experiment:")
    print(f"  Experiment: minilm-exact-baseline-v1")
    print(f"  Questions: 8")
    
    # Calculate sections & chunks count for printing
    sections_count = 0
    with args.sections.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sections_count += 1
    print(f"  Stories: {sections_count}")

    chunks_count = 0
    with args.chunks.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks_count += 1
    print(f"  Chunks: {chunks_count}")

    # Load canonical configurations
    with args.questions.open("r", encoding="utf-8") as f:
        questions_config = json.load(f)

    with args.retrieval_results.open("r", encoding="utf-8") as f:
        retrieval_results = json.load(f)

    generation_id = retrieval_results.get("generation_id")
    if not generation_id:
        print("Error: retrieval_results.json has missing generation_id.", file=sys.stderr)
        sys.exit(1)

    print(f"  Retrieval results: {len(retrieval_results.get('results', [])) * 10}")

    # Load sections for validator
    sections_list = EvaluationBuilder.load_jsonl(args.sections)
    sections_by_order = {s["section_order"]: s for s in sections_list}

    # 2. Scanning Judgments directory
    print("\nValidating judgments:")
    judgment_files = sorted(list(args.judgments.glob("q00*.json")))
    expected_qids = [f"q00{i}" for i in range(1, 9)]
    actual_filenames = [f.stem for f in judgment_files]

    # Check that judgments folder has exactly q001.json ... q008.json
    if set(actual_filenames) != set(expected_qids) or len(judgment_files) != 8:
        print(
            f"Error: Judgments directory must contain exactly q001.json to q008.json.\n"
            f"Found files: {[f.name for f in judgment_files]}",
            file=sys.stderr
        )
        sys.exit(1)

    validator = JudgmentValidator(questions_config, retrieval_results, sections_by_order)
    
    all_errors = []
    all_warnings = []
    all_corrections = []
    judgments_map = {}

    for idx, judgment_file in enumerate(judgment_files, start=1):
        filename_qid = judgment_file.stem
        try:
            with judgment_file.open("r", encoding="utf-8") as f:
                judgment_data = json.load(f)
        except Exception as e:
            print(f"  {filename_qid}: failed to parse JSON: {e}", file=sys.stderr)
            all_errors.append(f"JSON Parse Error in {judgment_file.name}: {e}")
            continue

        single_result, corrections = validator.validate_single(judgment_data, filename_qid)

        # Print quote style corrections if any
        for corr in corrections:
            print(f"  {filename_qid}: corrected judgment question quote style")
            print(f"    Before: {corr['original_value']}")
            print(f"    After:  {corr['corrected_value']}")

            all_corrections.append({
                "question_id": filename_qid,
                "source_file": f"judgments/{judgment_file.name}",
                "field": corr["field"],
                "type": corr["type"],
                "original_value": corr["original_value"],
                "corrected_value": corr["corrected_value"]
            })

            # Safe write corrected judgment data back to judgment file path
            tmp_judgment_path = judgment_file.with_suffix(".json.tmp")
            try:
                with tmp_judgment_path.open("w", encoding="utf-8") as tmp_f:
                    json.dump(judgment_data, tmp_f, indent=4, ensure_ascii=False)
                # Verify parse
                with tmp_judgment_path.open("r", encoding="utf-8") as tmp_f:
                    json.load(tmp_f)
                # Overwrite original
                tmp_judgment_path.replace(judgment_file)
            except Exception as write_err:
                print(f"  Error safe-writing corrected {judgment_file.name}: {write_err}", file=sys.stderr)
                all_errors.append(f"Safe-write error in {judgment_file.name}: {write_err}")
            finally:
                if tmp_judgment_path.exists():
                    tmp_judgment_path.unlink()

        if single_result.is_valid:
            print(f"  {filename_qid}: valid")
        else:
            print(f"  {filename_qid}: failed validation", file=sys.stderr)
            for err in single_result.errors:
                print(f"    Error: {err.message}", file=sys.stderr)
                all_errors.append(f"{filename_qid} error: {err.message}")

        for warn in single_result.warnings:
            all_warnings.append(f"{filename_qid} warning: {warn.message}")

        judgments_map[filename_qid] = judgment_data

    # Exit if any validation errors occurred
    if all_errors:
        print(f"\nValidation failed:", file=sys.stderr)
        for err_msg in all_errors:
            print(f"  {err_msg}", file=sys.stderr)
        print("\nNo output files were replaced.\nStatus: failed", file=sys.stderr)
        sys.exit(1)

    print("\nCalculating metrics:")
    print(f"  Questions processed: 8")
    print(f"  Retrieved chunks evaluated: 80")

    # 3. Create Staging Directory
    staging_dir = args.evaluation_output.parent / ".staging" / generation_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    try:
        # Calculate provenance hashes of all input files
        q_sha = calculate_sha256(args.questions)
        r_sha = calculate_sha256(args.retrieval_results)
        d_sha = calculate_sha256(args.document)
        s_sha = calculate_sha256(args.sections)
        c_sha = calculate_sha256(args.chunks)
        
        judgments_sha = {}
        for j_file in judgment_files:
            judgments_sha[j_file.stem] = calculate_sha256(j_file)

        source_provenance = {
            "questions_sha256": q_sha,
            "retrieval_results_sha256": r_sha,
            "document_sha256": d_sha,
            "sections_sha256": s_sha,
            "chunks_sha256": c_sha,
            "judgments_sha256": judgments_sha
        }

        # Build baseline evaluation payload
        evaluation_payload = EvaluationBuilder.build_evaluation(
            document_path=args.document,
            sections_path=args.sections,
            chunks_path=args.chunks,
            questions_config=questions_config,
            retrieval_results=retrieval_results,
            judgments=judgments_map,
            content_ingestion_report_path=args.content_ingestion_report,
            embedding_ingestion_report_path=args.embedding_ingestion_report,
            embedding_report_path=args.embedding_report
        )
        
        # Add source provenance to final baseline evaluation
        evaluation_payload["source_provenance"] = source_provenance

        # Save to staging/baseline_evaluation.json
        staging_eval_path = staging_dir / "baseline_evaluation.json"
        with staging_eval_path.open("w", encoding="utf-8") as f:
            json.dump(evaluation_payload, f, indent=2, ensure_ascii=False)

        # Build validation report structure
        validation_report = {
            "schema_version": "1.0",
            "status": "success",
            "experiment_id": "minilm-exact-baseline-v1",
            "generation_id": generation_id,
            "validated_question_count": 8,
            "validated_judgment_count": 8,
            "validated_retrieved_chunk_count": 80,
            "errors": [],
            "warnings": all_warnings,
            "corrections": all_corrections,
            "source_files": source_provenance
        }

        # Save to staging/validation_report.json
        staging_val_path = staging_dir / "validation_report.json"
        with staging_val_path.open("w", encoding="utf-8") as f:
            json.dump(validation_report, f, indent=2, ensure_ascii=False)

        # Verify staging files can be successfully read and parsed
        with staging_eval_path.open("r", encoding="utf-8") as f:
            json.load(f)
        with staging_val_path.open("r", encoding="utf-8") as f:
            json.load(f)

        # 4. Protected publication step
        args.evaluation_output.parent.mkdir(parents=True, exist_ok=True)
        args.validation_output.parent.mkdir(parents=True, exist_ok=True)

        if args.evaluation_output.exists():
            args.evaluation_output.unlink()
        shutil.move(str(staging_eval_path), str(args.evaluation_output))

        if args.validation_output.exists():
            args.validation_output.unlink()
        shutil.move(str(staging_val_path), str(args.validation_output))

        print("\nGenerated:")
        print(f"  {args.validation_output}")
        print(f"  {args.evaluation_output}")
        print("\nStatus: success")

    except Exception as build_err:
        print(f"\nExecution failed during output building: {build_err}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Clean up staging directory
        if staging_dir.exists():
            shutil.rmtree(staging_dir)

if __name__ == "__main__":
    main()
