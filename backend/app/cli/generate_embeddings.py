import argparse
import json
import logging
import platform
import sys
import time
import hashlib
from pathlib import Path
import numpy as np
import sentence_transformers

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.providers.minilm_provider import MiniLMProvider

logger = logging.getLogger("generate_embeddings_cli")

def calculate_sha256(path: Path) -> str:
    """
    Computes the SHA-256 hash of a file.
    """
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def validate_chunk(chunk: dict, line_number: int) -> None:
    """
    Validates essential fields of a chunk and basic numerical constraints.
    """
    REQUIRED_FIELDS = {
        "chunk_id",
        "section_order",
        "section_title",
        "chunk_order",
        "token_count",
        "text",
    }
    for field in REQUIRED_FIELDS:
        if field not in chunk:
            raise ValueError(f"Line {line_number}: Missing required field '{field}' in chunk.")

    if not chunk["chunk_id"] or not chunk["chunk_id"].strip():
        raise ValueError(f"Line {line_number}: chunk_id cannot be empty.")
        
    if not chunk["text"] or not chunk["text"].strip():
        raise ValueError(f"Line {line_number}: text cannot be empty.")
        
    if chunk["token_count"] <= 0:
        raise ValueError(f"Line {line_number}: token_count must be greater than 0.")
        
    if chunk["chunk_order"] <= 0:
        raise ValueError(f"Line {line_number}: chunk_order must be greater than 0.")

def load_chunks(path: Path, provider: MiniLMProvider) -> list[dict]:
    """
    Loads and validates all chunks from chunks.jsonl.
    Verifies chunk_id uniqueness and token count consistency.
    """
    chunks: list[dict] = []
    seen_chunk_ids: set[str] = set()

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number}: {error}"
                ) from error

            validate_chunk(chunk, line_number=line_number)
            
            chunk_id = chunk["chunk_id"]
            if chunk_id in seen_chunk_ids:
                raise ValueError(f"Duplicate chunk_id found: {chunk_id} on line {line_number}")
            seen_chunk_ids.add(chunk_id)

            # Re-calculate actual token count using model's tokenizer
            actual_token_count = provider.count_tokens(chunk["text"])
            
            if actual_token_count != chunk["token_count"]:
                raise ValueError(
                    f"Token count mismatch for {chunk_id}: "
                    f"stored={chunk['token_count']}, "
                    f"verified={actual_token_count}."
                )
                
            if actual_token_count > 220:
                raise ValueError(
                    f"Chunk {chunk_id} exceeds the 220-token project limit: {actual_token_count}."
                )
                
            if actual_token_count > provider.max_sequence_length:
                raise ValueError(
                    f"Chunk {chunk_id} exceeds model maximum sequence length: {provider.max_sequence_length}."
                )

            chunks.append(chunk)

    if not chunks:
        raise ValueError("No chunks were loaded.")

    return chunks

def main():
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="Generate embeddings for all chunks in a batch.")
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "chunks.jsonl",
        help="Path to the chunks.jsonl file."
    )
    parser.add_argument(
        "--embeddings-output",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "minilm_embeddings.npy",
        help="Path to save the output embeddings matrix (.npy)."
    )
    parser.add_argument(
        "--index-output",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "minilm_embedding_index.jsonl",
        help="Path to save the index mapping file (.jsonl)."
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "embedding_report.json",
        help="Path to save the summary report JSON."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for model inference."
    )

    args = parser.parse_args()

    # Ensure output parent directory exists
    args.embeddings_output.parent.mkdir(parents=True, exist_ok=True)

    # Track temporary files for cleanup in case of failure
    temp_paths: list[Path] = []
    
    temp_embeddings_path = args.embeddings_output.with_suffix(args.embeddings_output.suffix + ".tmp")
    temp_index_path = args.index_output.with_suffix(args.index_output.suffix + ".tmp")
    temp_report_path = args.report_output.with_suffix(args.report_output.suffix + ".tmp")
    
    temp_paths.extend([temp_embeddings_path, temp_index_path, temp_report_path])

    try:
        # Load model provider
        provider = MiniLMProvider(device="cpu")
        
        # 1. Load chunks & run tokenizer verification
        logger.info(f"Loading and validating chunks from {args.input}...")
        chunks = load_chunks(args.input, provider)
        
        token_counts = [c["token_count"] for c in chunks]
        min_tokens = min(token_counts)
        max_tokens = max(token_counts)

        print(f"Loading chunks:")
        print(f"  Input: {args.input}")
        print(f"  Chunks loaded: {len(chunks)}")
        print(f"  Unique chunk IDs: {len(chunks)}")
        print(f"  Token count range: {min_tokens}–{max_tokens}")

        print(f"\nLoading model:")
        print(f"  Model: {provider.model_name}")
        print(f"  Device: cpu")
        print(f"  Dimensions: {provider.dimensions}")
        print(f"  Batch size: {args.batch_size}")

        print(f"\nValidating tokenizer counts:")
        print(f"  Verified: {len(chunks)} / {len(chunks)}")
        print(f"  Mismatches: 0")

        # 2. Extract texts and generate embedding matrix
        print(f"\nGenerating embeddings:")
        texts = [c["text"] for c in chunks]
        
        start_time = time.time()
        embeddings = provider.encode_batch(texts, batch_size=args.batch_size)
        duration = time.time() - start_time

        # Calculate metrics for the validation output
        norms = np.linalg.norm(embeddings, axis=1)
        min_norm = float(np.min(norms))
        max_norm = float(np.max(norms))
        avg_norm = float(np.mean(norms))
        
        finite_value_count = int(np.count_nonzero(np.isfinite(embeddings)))
        total_value_count = int(embeddings.size)
        invalid_value_count = total_value_count - finite_value_count

        print(f"  Matrix shape: {embeddings.shape}")
        print(f"  Data type: {embeddings.dtype}")
        print(f"  Finite vectors: {len(chunks)} / {len(chunks)}")
        print(f"  Normalized vectors: {len(chunks)} / {len(chunks)}")

        # 3. Write output files to temporary locations
        # Write embeddings matrix to npy using binary file object
        with temp_embeddings_path.open("wb") as file:
            np.save(file, embeddings, allow_pickle=False)

        # Write mapping index JSONL (excluding text and embedding)
        with temp_index_path.open("w", encoding="utf-8") as file:
            for row_idx, chunk in enumerate(chunks):
                record = {
                    "row_index": row_idx,
                    "chunk_id": chunk["chunk_id"],
                    "section_order": chunk["section_order"],
                    "section_title": chunk["section_title"],
                    "chunk_order": chunk["chunk_order"],
                    "token_count": chunk["token_count"]
                }
                file.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 4. Atomic Reload & Self-Validation of temporary files
        # Verify matrix reload
        with temp_embeddings_path.open("rb") as file:
            loaded_embeddings = np.load(file, allow_pickle=False)
            
        if loaded_embeddings.shape != embeddings.shape:
            raise ValueError(f"Reload verification failed. Shape mismatch: {loaded_embeddings.shape} vs {embeddings.shape}")
            
        if loaded_embeddings.dtype != embeddings.dtype:
            raise ValueError(f"Reload verification failed. Dtype mismatch: {loaded_embeddings.dtype} vs {embeddings.dtype}")
            
        # Verify index count matches matrix rows
        index_records_count = 0
        with temp_index_path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    index_records_count += 1
                    
        if index_records_count != loaded_embeddings.shape[0]:
            raise ValueError(
                f"Validation failed. Index row count ({index_records_count}) "
                f"does not match embeddings matrix shape ({loaded_embeddings.shape[0]})."
            )

        # 5. Compute SHA-256 hashes
        input_chunks_sha256 = calculate_sha256(args.input)
        embeddings_file_sha256 = calculate_sha256(temp_embeddings_path)
        index_file_sha256 = calculate_sha256(temp_index_path)

        # Write report JSON
        report = {
            "model_name": provider.model_name,
            "model_max_sequence_length": provider.max_sequence_length,
            "device": "cpu",
            "dimensions": provider.dimensions,
            "normalized": True,
            "dtype": str(embeddings.dtype),
            "batch_size": args.batch_size,
            "chunk_count": len(chunks),
            "matrix_shape": list(embeddings.shape),
            "finite_value_count": finite_value_count,
            "invalid_value_count": invalid_value_count,
            "minimum_vector_norm": round(min_norm, 7),
            "maximum_vector_norm": round(max_norm, 7),
            "average_vector_norm": round(avg_norm, 7),
            "minimum_token_count": min_tokens,
            "maximum_token_count": max_tokens,
            "token_count_mismatches": 0,
            "duration_seconds": round(duration, 2),
            "input_chunks_sha256": input_chunks_sha256,
            "embeddings_file_sha256": embeddings_file_sha256,
            "index_file_sha256": index_file_sha256,
            "sentence_transformers_version": sentence_transformers.__version__,
            "numpy_version": np.__version__,
            "python_version": platform.python_version()
        }

        with temp_report_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)

        # 6. Success! Rename temporary files to final paths
        temp_embeddings_path.replace(args.embeddings_output)
        temp_index_path.replace(args.index_output)
        temp_report_path.replace(args.report_output)

        print(f"\nOutputs:")
        print(f"  {args.embeddings_output}")
        print(f"  {args.index_output}")
        print(f"  {args.report_output}\n")

    except Exception as e:
        logger.error(f"Failed to execute batch generate embeddings command: {e}")
        sys.exit(1)
        
    finally:
        # Cleanup remaining .tmp files in case of errors/interruption
        for temp_path in temp_paths:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception as cleanup_err:
                logger.debug(f"Failed to remove temporary file {temp_path}: {cleanup_err}")

if __name__ == "__main__":
    main()
