import argparse
import json
import logging
import sys
import hashlib
from pathlib import Path

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.services.content_ingestion_service import ContentIngestionService

logger = logging.getLogger("ingest_content_cli")

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

    parser = argparse.ArgumentParser(description="Ingest document contents into the PostgreSQL database.")
    parser.add_argument(
        "--document",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "document.json",
        help="Path to the document.json file."
    )
    parser.add_argument(
        "--sections",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "sections.jsonl",
        help="Path to the sections.jsonl file."
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
        default=settings.DATA_DIR / "artifacts" / "content_ingestion_report.json",
        help="Path to save the output ingestion report JSON."
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Force replace document and cascade delete sections/chunks/embeddings."
    )

    args = parser.parse_args()

    # 1. Verify file existence
    for path_name, file_path in [("document", args.document), ("sections", args.sections), ("chunks", args.chunks)]:
        if not file_path.exists():
            logger.error(f"Input file for {path_name} not found at: {file_path}")
            sys.exit(1)

    try:
        # 2. Compute SHA-256 of input files
        doc_hash = calculate_sha256(args.document)
        sec_hash = calculate_sha256(args.sections)
        chunk_hash = calculate_sha256(args.chunks)

        # 3. Load files
        with args.document.open("r", encoding="utf-8") as f:
            doc_data = json.load(f)

        # Apply database fields default values if missing
        if "document_id" not in doc_data:
            doc_data["document_id"] = "gutenberg-1661"
        if "source_name" not in doc_data:
            doc_data["source_name"] = "Project Gutenberg"
        if "source_reference" not in doc_data:
            doc_data["source_reference"] = "1661"

        sections_data = load_jsonl(args.sections)
        chunks_data = load_jsonl(args.chunks)

        # 4. Perform pre-ingestion validation
        print("Validating input files:")
        print(f"  Documents: 1")
        print(f"  Sections: {len(sections_data)}")
        print(f"  Chunks: {len(chunks_data)}")
        
        service = ContentIngestionService()
        
        # We enforce expected counts of 12 and 909 for the default Gutenberg Sherlock RAG datasets
        is_default_run = (
            args.document == settings.PROCESSED_DATA_DIR / "document.json" and
            args.sections == settings.PROCESSED_DATA_DIR / "sections.jsonl" and
            args.chunks == settings.PROCESSED_DATA_DIR / "chunks.jsonl"
        )
        
        expected_sec = 12 if is_default_run else None
        expected_chk = 909 if is_default_run else None
        
        service.validate_data(
            doc_data,
            sections_data,
            chunks_data,
            expected_section_count=expected_sec,
            expected_chunk_count=expected_chk
        )
        
        token_counts = [c["token_count"] for c in chunks_data]
        min_tokens = min(token_counts) if token_counts else 0
        max_tokens = max(token_counts) if token_counts else 0
        print(f"  Unique chunk IDs: {len(chunks_data)}")
        print(f"  Token range: {min_tokens}–{max_tokens}")
        print("  Cross-reference errors: 0")

        # 5. Handle --replace mode warning
        if args.replace:
            print("\nWARNING: --replace deletes existing chunks and any associated embeddings.")

        # 6. Execute database transaction
        print("\nWriting database transaction:")
        stats = service.ingest(doc_data, sections_data, chunks_data, replace=args.replace)

        print(f"  Document inserted: {stats['document_count']}")
        print(f"  Sections inserted: {stats['section_count']}")
        print(f"  Chunks inserted: {stats['chunk_count']}")
        print(f"  Embeddings inserted: {stats['embedding_count']}")

        print("\nDatabase verification:")
        print(f"  documents: {stats['document_count']}")
        print(f"  sections: {stats['section_count']}")
        print(f"  chunks: {stats['chunk_count']}")
        print(f"  minilm_embeddings: {stats['embedding_count']}")

        print("\nStatus: success")

        # 7. Safe JSON report generation
        report_data = {
            "document_id": stats["document_id"],
            "document_count": stats["document_count"],
            "section_count": stats["section_count"],
            "chunk_count": stats["chunk_count"],
            "embedding_count": stats["embedding_count"],
            "document_file_sha256": doc_hash,
            "sections_file_sha256": sec_hash,
            "chunks_file_sha256": chunk_hash,
            "replace_mode": args.replace,
            "status": "success"
        }

        # Safe atomic replacement of output report
        args.report.parent.mkdir(parents=True, exist_ok=True)
        temp_report_path = args.report.with_suffix(args.report.suffix + ".tmp")
        
        try:
            with temp_report_path.open("w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            temp_report_path.replace(args.report)
            print(f"Report written to {args.report}\n")
        finally:
            temp_report_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Failed to execute content ingestion command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
