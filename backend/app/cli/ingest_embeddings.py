import argparse
import json
import logging
import sys
import hashlib
from pathlib import Path
import numpy as np

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.services.embedding_ingestion_service import EmbeddingIngestionService

logger = logging.getLogger("ingest_embeddings_cli")

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

def main():
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="Ingest precalculated embedding vectors into database.")
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "minilm_embeddings.npy",
        help="Path to the minilm_embeddings.npy file."
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "minilm_embedding_index.jsonl",
        help="Path to the minilm_embedding_index.jsonl file."
    )
    parser.add_argument(
        "--source-report",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "embedding_report.json",
        help="Path to the embedding_report.json source metadata."
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "chunks.jsonl",
        help="Path to the chunks.jsonl file."
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "embedding_ingestion_report.json",
        help="Path to save the output embedding ingestion report JSON."
    )
    parser.add_argument(
        "--document-id",
        type=str,
        default="gutenberg-1661",
        help="Target document ID mapping in database."
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Force replace embedding vectors for the document without deleting sections/chunks."
    )

    args = parser.parse_args()

    # 1. Verify file existence
    input_files = [
        ("embeddings", args.embeddings),
        ("index", args.index),
        ("source-report", args.source_report),
        ("chunks", args.chunks)
    ]
    for name, path in input_files:
        if not path.exists():
            logger.error(f"Input file for {name} not found at: {path}")
            sys.exit(1)

    try:
        # 2. Compute SHA-256 hashes of input files
        emb_sha = calculate_sha256(args.embeddings)
        idx_sha = calculate_sha256(args.index)
        chk_sha = calculate_sha256(args.chunks)

        # 3. Read source report and run metadata validation
        with args.source_report.open("r", encoding="utf-8") as f:
            source_report = json.load(f)

        # Compare hashes with source report
        if emb_sha != source_report.get("embeddings_file_sha256"):
            raise ValueError(
                f"Embedding file hash mismatch. Current={emb_sha}, "
                f"Expected={source_report.get('embeddings_file_sha256')}"
            )
        if idx_sha != source_report.get("index_file_sha256"):
            raise ValueError(
                f"Index file hash mismatch. Current={idx_sha}, "
                f"Expected={source_report.get('index_file_sha256')}"
            )
        if chk_sha != source_report.get("input_chunks_sha256"):
            raise ValueError(
                f"Chunks file hash mismatch. Current={chk_sha}, "
                f"Expected={source_report.get('input_chunks_sha256')}"
            )

        # Verify model descriptors
        if source_report.get("model_name") != "sentence-transformers/all-MiniLM-L6-v2":
            raise ValueError(f"Unsupported model in report: {source_report.get('model_name')}")
        if source_report.get("dimensions") != 384:
            raise ValueError(f"Unsupported embedding dimensions in report: {source_report.get('dimensions')}")
        if source_report.get("normalized") is not True:
            raise ValueError("Embeddings in source report are not marked as normalized.")

        # 4. Load numpy matrix and mapping index records
        embeddings = np.load(args.embeddings, allow_pickle=False)
        index_records = load_jsonl(args.index)
        chunks_data = load_jsonl(args.chunks)

        # Verify matrix shapes match report
        if list(embeddings.shape) != source_report.get("matrix_shape"):
            raise ValueError(f"Matrix shape mismatch: loaded={embeddings.shape}, report={source_report.get('matrix_shape')}")
        if len(index_records) != source_report.get("chunk_count"):
            raise ValueError(f"Index records count mismatch: loaded={len(index_records)}, report={source_report.get('chunk_count')}")

        # 5. Build text fingerprint expectations for dual DB verification
        expected_chunks = {
            chunk["chunk_id"]: {
                "section_order": chunk["section_order"],
                "section_title": chunk["section_title"],
                "chunk_order": chunk["chunk_order"],
                "token_count": chunk["token_count"],
                "text_sha256": hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest()
            }
            for chunk in chunks_data
        }

        # 6. Check replace flag
        if args.replace:
            print("\nWARNING: --replace deletes existing embeddings for document. Original text is preserved.")

        # 7. Execute Ingestion Transaction
        service = EmbeddingIngestionService()
        
        # Enforce expected counts of 909 for the default Gutenberg Sherlock RAG dataset
        is_default_run = (
            args.embeddings == settings.DATA_DIR / "artifacts" / "minilm_embeddings.npy" and
            args.index == settings.DATA_DIR / "artifacts" / "minilm_embedding_index.jsonl" and
            args.chunks == settings.PROCESSED_DATA_DIR / "chunks.jsonl"
        )
        expected_count = 909 if is_default_run else None

        stats = service.ingest(
            document_id=args.document_id,
            embeddings=embeddings,
            index_records=index_records,
            expected_chunks=expected_chunks,
            model_name=source_report["model_name"],
            replace=args.replace,
            expected_count=expected_count
        )

        print("\nDatabase verification:")
        print(f"  Inserted embeddings: {stats['inserted_embedding_count']}")
        print(f"  Minimum norm: {stats['minimum_vector_norm']:.6f}")
        print(f"  Maximum norm: {stats['maximum_vector_norm']:.6f}")
        print("  Status: success")

        # 8. Safe Ingestion report generation (atomic write)
        report_data = {
            "status": "success",
            "document_id": args.document_id,
            "model_name": source_report["model_name"],
            "dimensions": 384,
            "normalized": True,
            "matrix_shape": list(embeddings.shape),
            "index_count": len(index_records),
            "database_chunk_count": len(chunks_data),
            "inserted_embedding_count": stats["inserted_embedding_count"],
            "replace_mode": args.replace,
            "embeddings_file_sha256": emb_sha,
            "index_file_sha256": idx_sha,
            "chunks_file_sha256": chk_sha,
            "minimum_vector_norm": round(stats["minimum_vector_norm"], 7),
            "maximum_vector_norm": round(stats["maximum_vector_norm"], 7)
        }

        args.report.parent.mkdir(parents=True, exist_ok=True)
        temp_report_path = args.report.with_suffix(args.report.suffix + ".tmp")
        
        try:
            with temp_report_path.open("w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            temp_report_path.replace(args.report)
            print(f"\nReport written to {args.report}\n")
        finally:
            temp_report_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Failed to execute embedding ingestion command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
