import sys
import json
import hashlib
import logging
from pathlib import Path
import numpy as np
import psycopg

# Add backend directory to sys.path to run cleanly as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.db.connection import get_connection
from app.services.content_ingestion_service import ContentIngestionService
from app.services.embedding_ingestion_service import EmbeddingIngestionService

logger = logging.getLogger("bootstrap_database")

def calculate_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def verify_schema_exists() -> None:
    REQUIRED_TABLES = ["documents", "sections", "chunks", "minilm_embeddings"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check table existence
            for table in REQUIRED_TABLES:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = %s
                    );
                """, (table,))
                if not cur.fetchone()[0]:
                    print(f"Error: Database schema is not initialized. Table '{table}' is missing.")
                    print("Apply database migrations before running bootstrap_database.")
                    sys.exit(1)
            
            # Check pgvector extension
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector');")
            if not cur.fetchone()[0]:
                print("Error: Database schema is not initialized. pgvector extension is missing.")
                print("Apply database migrations before running bootstrap_database.")
                sys.exit(1)

def run_bootstrap() -> None:
    # 1. Resolve source paths
    doc_path = settings.PROCESSED_DATA_DIR / "document.json"
    sections_path = settings.PROCESSED_DATA_DIR / "sections.jsonl"
    chunks_path = settings.PROCESSED_DATA_DIR / "chunks.jsonl"
    embeddings_path = settings.DATA_DIR / "artifacts" / "minilm_embeddings.npy"
    index_path = settings.DATA_DIR / "artifacts" / "minilm_embedding_index.jsonl"
    report_path = settings.DATA_DIR / "artifacts" / "embedding_report.json"

    # Verify input files exist in image
    for name, p in [
        ("document.json", doc_path),
        ("sections.jsonl", sections_path),
        ("chunks.jsonl", chunks_path),
        ("minilm_embeddings.npy", embeddings_path),
        ("minilm_embedding_index.jsonl", index_path),
        ("embedding_report.json", report_path)
    ]:
        if not p.exists():
            print(f"Error: Required artifact '{name}' not found at: {p}")
            sys.exit(1)

    # 2. Compute expected hashes and load metadata
    doc_hash = calculate_sha256(doc_path)
    sec_hash = calculate_sha256(sections_path)
    chunk_hash = calculate_sha256(chunks_path)
    emb_hash = calculate_sha256(embeddings_path)
    idx_hash = calculate_sha256(index_path)

    with doc_path.open("r", encoding="utf-8") as f:
        doc_data = json.load(f)
    if "document_id" not in doc_data:
        doc_data["document_id"] = "gutenberg-1661"
    if "source_name" not in doc_data:
        doc_data["source_name"] = "Project Gutenberg"
    if "source_reference" not in doc_data:
        doc_data["source_reference"] = "1661"
    doc_id = doc_data["document_id"]

    sections_data = load_jsonl(sections_path)
    chunks_data = load_jsonl(chunks_path)
    embeddings = np.load(embeddings_path, allow_pickle=False)
    index_records = load_jsonl(index_path)

    with report_path.open("r", encoding="utf-8") as f:
        embedding_report = json.load(f)

    # Validate report matches files
    if emb_hash != embedding_report.get("embeddings_file_sha256"):
        raise ValueError("Embedding file hash mismatch with report.")
    if idx_hash != embedding_report.get("index_file_sha256"):
        raise ValueError("Index file hash mismatch with report.")
    if chunk_hash != embedding_report.get("input_chunks_sha256"):
        raise ValueError("Chunks file hash mismatch with report.")

    # 3. Check for conflicts in existing DB state
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Query document metadata
            cur.execute("SELECT title, author, source_name FROM documents WHERE document_id = %s;", (doc_id,))
            doc_row = cur.fetchone()
            if doc_row:
                db_title, db_author, db_source_name = doc_row
                if db_title != doc_data.get("title") or db_author != doc_data.get("author") or db_source_name != doc_data.get("source_name"):
                    print("Conflict detected: Document metadata in DB does not match image data.")
                    print(f"DB Title: '{db_title}', Image Title: '{doc_data.get('title')}'")
                    sys.exit(1)

            # Query existing chunk texts and orders
            cur.execute("""
                SELECT c.chunk_uid, c.chunk_order, c.token_count, c.chunk_text, s.section_order
                FROM chunks c
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s;
            """, (doc_id,))
            db_chunks = cur.fetchall()

            # Compare database chunks with container chunks
            expected_chunks_map = {c["chunk_id"]: c for c in chunks_data}
            for db_uid, db_order, db_tokens, db_text, db_sec_order in db_chunks:
                if db_uid not in expected_chunks_map:
                    print(f"Conflict detected: Chunk UID '{db_uid}' exists in DB but not in image data.")
                    sys.exit(1)
                exp = expected_chunks_map[db_uid]
                if db_order != exp["chunk_order"] or db_tokens != exp["token_count"] or db_text != exp["text"] or db_sec_order != exp["section_order"]:
                    print(f"Conflict detected: Content or metadata mismatch for chunk '{db_uid}'.")
                    sys.exit(1)

            # Check model name / dimensions in existing embeddings
            cur.execute("""
                SELECT DISTINCT model_name, dimensions, normalized
                FROM minilm_embeddings e
                JOIN chunks c ON c.chunk_id = e.chunk_id
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s;
            """, (doc_id,))
            db_emb_types = cur.fetchall()
            for model_name, dimensions, normalized in db_emb_types:
                if model_name != "sentence-transformers/all-MiniLM-L6-v2" or dimensions != 384 or not normalized:
                    print(f"Conflict detected: Incompatible embedding model in DB: model='{model_name}', dimensions={dimensions}")
                    sys.exit(1)

            # Query counts of Gutenberg-1661 records
            cur.execute("SELECT COUNT(*) FROM sections WHERE document_id = %s;", (doc_id,))
            db_sections_count = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s;
            """, (doc_id,))
            db_chunks_count = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM minilm_embeddings e
                JOIN chunks c ON c.chunk_id = e.chunk_id
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s;
            """, (doc_id,))
            db_embeddings_count = cur.fetchone()[0]

    # 4. Determine state and execute actions
    needs_content_ingestion = False
    needs_embedding_ingestion = False

    if db_chunks_count == 0:
        # Fully empty or missing text database
        needs_content_ingestion = True
        needs_embedding_ingestion = True
    elif db_chunks_count != 909 or db_sections_count != 12:
        # Partial content state (since no conflicts were found, it's a subset; we replace and re-ingest all)
        print(f"Partial content detected (chunks: {db_chunks_count}/909, sections: {db_sections_count}/12). Repairing...")
        needs_content_ingestion = True
        needs_embedding_ingestion = True
    elif db_embeddings_count < 909:
        # Content is completely intact, but embeddings are missing or incomplete
        print(f"Missing embeddings detected ({db_embeddings_count}/909). Repairing...")
        needs_embedding_ingestion = True
    else:
        # Fully seeded and correct
        pass

    # Execute Content Ingestion if needed
    if needs_content_ingestion:
        print("Running content ingestion...")
        content_service = ContentIngestionService()
        content_service.validate_data(
            doc_data,
            sections_data,
            chunks_data,
            expected_section_count=12,
            expected_chunk_count=909
        )
        content_service.ingest(doc_data, sections_data, chunks_data, replace=True)

    # Execute Embedding Ingestion if needed
    if needs_embedding_ingestion:
        print("Running embedding vector ingestion...")
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
        embedding_service = EmbeddingIngestionService()
        embedding_service.ingest(
            document_id=doc_id,
            embeddings=embeddings,
            index_records=index_records,
            expected_chunks=expected_chunks,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            replace=True,
            expected_count=909
        )

    # 5. Perform Deep Validation
    print("Executing final database validation...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Document Count
            cur.execute("SELECT COUNT(*) FROM documents WHERE document_id = %s;", (doc_id,))
            final_docs = cur.fetchone()[0]
            if final_docs != 1:
                raise ValueError(f"Deep validation failed: expected 1 document for '{doc_id}', got {final_docs}")

            # Story (Section) Count
            cur.execute("SELECT COUNT(*) FROM sections WHERE document_id = %s;", (doc_id,))
            final_sections = cur.fetchone()[0]
            if final_sections != 12:
                raise ValueError(f"Deep validation failed: expected 12 sections, got {final_sections}")

            # Chunk Count
            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s;
            """, (doc_id,))
            final_chunks = cur.fetchone()[0]
            if final_chunks != 909:
                raise ValueError(f"Deep validation failed: expected 909 chunks, got {final_chunks}")

            # Embedding Count
            cur.execute("""
                SELECT COUNT(*) FROM minilm_embeddings e
                JOIN chunks c ON c.chunk_id = e.chunk_id
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s;
            """, (doc_id,))
            final_embeddings = cur.fetchone()[0]
            if final_embeddings != 909:
                raise ValueError(f"Deep validation failed: expected 909 embeddings, got {final_embeddings}")

            # No duplicate chunk_uid values
            cur.execute("""
                SELECT chunk_uid, COUNT(*) FROM chunks c
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s
                GROUP BY chunk_uid HAVING COUNT(*) > 1;
            """, (doc_id,))
            duplicates = cur.fetchall()
            if duplicates:
                raise ValueError(f"Deep validation failed: duplicate chunk_uids found: {duplicates}")

            # Every embedding references an existing chunk and has correct dims/model
            cur.execute("""
                SELECT COUNT(*)
                FROM minilm_embeddings e
                JOIN chunks c ON c.chunk_id = e.chunk_id
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s
                  AND (e.model_name != 'sentence-transformers/all-MiniLM-L6-v2' 
                       OR e.dimensions != 384 
                       OR e.normalized != TRUE);
            """, (doc_id,))
            invalid_embs = cur.fetchone()[0]
            if invalid_embs > 0:
                raise ValueError(f"Deep validation failed: {invalid_embs} embeddings have incorrect metadata.")

            # No chunks without embeddings
            cur.execute("""
                SELECT COUNT(*)
                FROM chunks c
                JOIN sections s ON s.section_id = c.section_id
                LEFT JOIN minilm_embeddings e ON e.chunk_id = c.chunk_id
                WHERE s.document_id = %s AND e.chunk_id IS NULL;
            """, (doc_id,))
            chunks_without_embs = cur.fetchone()[0]
            if chunks_without_embs > 0:
                raise ValueError(f"Deep validation failed: {chunks_without_embs} chunks have no embeddings.")

    print("\nDatabase bootstrap complete.\n")
    print(f"Document: {doc_id}")
    print("Stories: 12")
    print("Chunks: 909")
    print("Embeddings: 909")
    print("Dimensions: 384")
    print("Model: sentence-transformers/all-MiniLM-L6-v2")
    print("Status: ready")

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Verify migration schema is present
    verify_schema_exists()

    # Acquire Session-level Advisory Lock
    lock_conn = psycopg.connect(settings.DATABASE_URL)
    lock_conn.autocommit = True
    try:
        with lock_conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtext('rag-bootstrap:gutenberg-1661'));")
            if not cur.fetchone()[0]:
                print("Error: Could not acquire postgres advisory lock. Another seeder is running.")
                sys.exit(1)
        
        run_bootstrap()

    except Exception as e:
        print(f"Failed to bootstrap database: {e}")
        sys.exit(1)
    finally:
        try:
            with lock_conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(hashtext('rag-bootstrap:gutenberg-1661'));")
        except Exception:
            pass
        lock_conn.close()

if __name__ == "__main__":
    main()
