import logging
import hashlib
import numpy as np
from app.db.connection import get_connection

logger = logging.getLogger("embedding_ingestion_service")

class EmbeddingIngestionService:
    """
    Service responsible for validating and importing MiniLM embedding vectors
    into the database within a single SQL transaction.
    """

    def validate_inputs(self, embeddings: np.ndarray, index_records: list[dict]) -> None:
        """
        Validates the format, dimensions, normalization of the matrix,
        and the structural integrity of the line mapping index records.
        """
        # 1. Matrix validations
        if embeddings.ndim != 2:
            raise ValueError("Embedding data must be a 2D matrix.")

        if embeddings.shape[1] != 384:
            raise ValueError(f"Expected 384 dimensions, got {embeddings.shape[1]}.")

        if embeddings.dtype != np.float32:
            raise ValueError(f"Expected float32, got {embeddings.dtype}.")

        if not np.isfinite(embeddings).all():
            raise ValueError("Embedding matrix contains invalid values.")

        norms = np.linalg.norm(embeddings, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-5):
            raise ValueError("One or more embeddings are not normalized.")

        # 2. Index validations
        if len(index_records) != embeddings.shape[0]:
            raise ValueError(
                f"Embedding index records count ({len(index_records)}) "
                f"does not match matrix row count ({embeddings.shape[0]})."
            )

        REQUIRED_INDEX_FIELDS = {
            "row_index",
            "chunk_id",
            "section_order",
            "section_title",
            "chunk_order",
            "token_count",
        }

        seen_row_indices = set()
        seen_chunk_ids = set()

        for idx, record in enumerate(index_records, start=1):
            # Check fields exist
            for field in REQUIRED_INDEX_FIELDS:
                if record.get(field) is None:
                    raise ValueError(f"Index record index {idx} is missing required field '{field}'.")

            # Check uniqueness
            row_idx = record["row_index"]
            chunk_id = record["chunk_id"]

            if row_idx in seen_row_indices:
                raise ValueError(f"Duplicate row_index found in index: {row_idx}")
            seen_row_indices.add(row_idx)

            if chunk_id in seen_chunk_ids:
                raise ValueError(f"Duplicate chunk_id found in index: {chunk_id}")
            seen_chunk_ids.add(chunk_id)

            # Check index doesn't contain text or embedding
            if "text" in record:
                raise ValueError("Embedding index record contains forbidden field 'text'.")
            if "embedding" in record:
                raise ValueError("Embedding index record contains forbidden field 'embedding'.")

        # Check contiguous row_index range from 0 to N-1
        sorted_rows = sorted(list(seen_row_indices))
        expected_rows = list(range(len(index_records)))
        if sorted_rows != expected_rows:
            raise ValueError(f"Row indices must be contiguous from 0 to {len(index_records) - 1}.")

    def _build_insert_rows(
        self,
        embeddings: np.ndarray,
        ordered_records: list[dict],
        database_chunk_ids: dict[str, int],
        model_name: str,
    ) -> list[dict]:
        """
        Helper method to construct list of parameter dictionaries for cursor.executemany().
        """
        rows = []
        for record in ordered_records:
            row_idx = record["row_index"]
            chunk_uid = record["chunk_id"]
            
            # Retrieve generated database bigint ID using JSON string chunk_id (chunk_uid)
            db_chunk_id = database_chunk_ids[chunk_uid]
            
            rows.append({
                "chunk_id": db_chunk_id,
                "model_name": model_name,
                "dimensions": 384,
                "normalized": True,
                "embedding": embeddings[row_idx],
            })
        return rows

    def ingest(
        self,
        document_id: str,
        embeddings: np.ndarray,
        index_records: list[dict],
        expected_chunks: dict[str, dict],
        model_name: str,
        replace: bool = False,
        expected_count: int | None = None,
    ) -> dict:
        """
        Executes embedding validation, conflict handling, metadata fingerprint matching,
        and database insertion in a single transaction.
        """
        # 1. Run basic validations
        self.validate_inputs(embeddings, index_records)

        # 2. Sort index records by row_index to map values correctly
        ordered_records = sorted(index_records, key=lambda record: record["row_index"])

        if expected_count is not None and len(ordered_records) != expected_count:
            raise ValueError(f"Expected {expected_count} embeddings, got {len(ordered_records)}.")

        with get_connection() as conn:
            with conn.transaction():
                # 3. Check existing embeddings
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1
                        FROM minilm_embeddings e
                        JOIN chunks c ON c.chunk_id = e.chunk_id
                        JOIN sections s ON s.section_id = c.section_id
                        WHERE s.document_id = %s
                        LIMIT 1;
                        """,
                        (document_id,)
                    )
                    exists = cur.fetchone() is not None

                if exists:
                    if not replace:
                        raise ValueError(
                            f"Embeddings for document {document_id} already exist. "
                            f"Use --replace to replace existing embeddings."
                        )
                    else:
                        logger.warning(
                            f"WARNING: --replace deletes existing embeddings for document '{document_id}'."
                        )
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                DELETE FROM minilm_embeddings e
                                USING chunks c, sections s
                                WHERE e.chunk_id = c.chunk_id
                                  AND c.section_id = s.section_id
                                  AND s.document_id = %s;
                                """,
                                (document_id,)
                            )

                # 4. Fetch DB chunks & perform text fingerprint and metadata verification
                database_chunk_ids = {}
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            c.chunk_id,
                            c.chunk_uid,
                            c.chunk_order,
                            c.token_count,
                            c.chunk_text,
                            s.section_order,
                            s.title AS section_title
                        FROM chunks c
                        JOIN sections s ON s.section_id = c.section_id
                        WHERE s.document_id = %s;
                        """,
                        (document_id,)
                    )
                    db_rows = cur.fetchall()

                for db_row in db_rows:
                    db_id, db_uid, db_order, db_tokens, db_text, db_sec_order, db_sec_title = db_row
                    
                    if db_uid not in expected_chunks:
                        raise ValueError(f"Database chunk '{db_uid}' is missing from input chunks file.")
                        
                    exp = expected_chunks[db_uid]
                    
                    # Verify metadata fields
                    if db_sec_order != exp["section_order"]:
                        raise ValueError(f"Section order mismatch for chunk {db_uid}: DB={db_sec_order}, Expected={exp['section_order']}")
                    if db_sec_title != exp["section_title"]:
                        raise ValueError(f"Section title mismatch for chunk {db_uid}: DB='{db_sec_title}', Expected='{exp['section_title']}'")
                    if db_order != exp["chunk_order"]:
                        raise ValueError(f"Chunk order mismatch for chunk {db_uid}: DB={db_order}, Expected={exp['chunk_order']}")
                    if db_tokens != exp["token_count"]:
                        raise ValueError(f"Token count mismatch for chunk {db_uid}: DB={db_tokens}, Expected={exp['token_count']}")
                        
                    # Verify text sha256 finger-print
                    db_text_sha = hashlib.sha256(db_text.encode("utf-8")).hexdigest()
                    if db_text_sha != exp["text_sha256"]:
                        raise ValueError(
                            f"Content mismatch for chunk '{db_uid}'. "
                            f"Database text does not match the text used to generate embeddings."
                        )
                        
                    database_chunk_ids[db_uid] = db_id

                # 5. Dual-alignment set verification
                index_chunk_uids = {record["chunk_id"] for record in ordered_records}
                db_chunk_uids = set(database_chunk_ids.keys())
                
                missing_in_db = index_chunk_uids - db_chunk_uids
                missing_in_index = db_chunk_uids - index_chunk_uids
                
                if missing_in_db:
                    raise ValueError(f"Index chunks missing in database: {list(missing_in_db)[:5]}")
                if missing_in_index:
                    raise ValueError(f"Database chunks missing in index: {list(missing_in_index)[:5]}")

                # 6. Build insertion rows
                rows = self._build_insert_rows(embeddings, ordered_records, database_chunk_ids, model_name)

                # 7. Execute batch insertion
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO minilm_embeddings (chunk_id, model_name, dimensions, normalized, embedding)
                        VALUES (%(chunk_id)s, %(model_name)s, %(dimensions)s, %(normalized)s, %(embedding)s);
                        """,
                        rows
                    )

                # 8. Post-Ingestion database verification
                with conn.cursor() as cur:
                    # Embedded vectors count
                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM minilm_embeddings e
                        JOIN chunks c ON c.chunk_id = e.chunk_id
                        JOIN sections s ON s.section_id = c.section_id
                        WHERE s.document_id = %s;
                        """,
                        (document_id,)
                    )
                    actual_embeddings_count = cur.fetchone()[0]
                    if actual_embeddings_count != len(ordered_records):
                        raise ValueError(
                            f"Post-ingestion check failed. Embedding count for '{document_id}' is "
                            f"{actual_embeddings_count}, expected {len(ordered_records)}."
                        )

                    # Correct dimension count
                    cur.execute(
                        """
                        SELECT COUNT(*) FILTER (WHERE vector_dims(e.embedding) = 384) AS correct_dims, COUNT(*) AS total
                        FROM minilm_embeddings e
                        JOIN chunks c ON c.chunk_id = e.chunk_id
                        JOIN sections s ON s.section_id = c.section_id
                        WHERE s.document_id = %s;
                        """,
                        (document_id,)
                    )
                    correct_dims, total = cur.fetchone()
                    if correct_dims != len(ordered_records) or total != len(ordered_records):
                        raise ValueError(
                            f"Post-ingestion check failed. Expected {len(ordered_records)} vector(384) records, "
                            f"database has correct_dimensions={correct_dims}, total={total}."
                        )

                    # Check vector norm range
                    cur.execute(
                        """
                        SELECT MIN(vector_norm(e.embedding)), MAX(vector_norm(e.embedding))
                        FROM minilm_embeddings e
                        JOIN chunks c ON c.chunk_id = e.chunk_id
                        JOIN sections s ON s.section_id = c.section_id
                        WHERE s.document_id = %s;
                        """,
                        (document_id,)
                    )
                    min_norm, max_norm = cur.fetchone()
                    if min_norm is None or max_norm is None or not np.isclose(min_norm, 1.0, atol=1e-5) or not np.isclose(max_norm, 1.0, atol=1e-5):
                        raise ValueError(
                            f"Post-ingestion check failed. Embedding norms must be close to 1.0. "
                            f"Got min_norm={min_norm}, max_norm={max_norm}."
                        )

        # Successful transaction
        return {
            "document_id": document_id,
            "inserted_embedding_count": len(ordered_records),
            "replace_mode": replace,
            "minimum_vector_norm": float(min_norm),
            "maximum_vector_norm": float(max_norm),
            "status": "success"
        }
