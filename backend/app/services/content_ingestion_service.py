import logging
from app.db.connection import get_connection

logger = logging.getLogger("content_ingestion_service")

class ContentIngestionService:
    """
    Service responsible for validating and importing document contents (documents, sections, chunks)
    into the PostgreSQL database within a single transaction.
    """

    def validate_data(
        self,
        document: dict,
        sections: list[dict],
        chunks: list[dict],
        expected_section_count: int | None = None,
        expected_chunk_count: int | None = None,
    ) -> None:
        """
        Validates all input file records and cross-references them in memory before database ingestion.
        """
        # 1. Document validation
        if not document.get("document_id") or not str(document["document_id"]).strip():
            raise ValueError("document_id cannot be empty.")
        if not document.get("title") or not str(document["title"]).strip():
            raise ValueError("document title cannot be empty.")
        if not document.get("source_name") or not str(document["source_name"]).strip():
            raise ValueError("document source_name cannot be empty.")

        # 2. Sections validation
        if not sections:
            raise ValueError("Sections list cannot be empty.")
        if expected_section_count is not None and len(sections) != expected_section_count:
            raise ValueError(f"Expected {expected_section_count} sections, got {len(sections)}.")

        seen_section_orders = set()
        sections_by_order = {}
        for idx, section in enumerate(sections, start=1):
            order = section.get("section_order")
            if order is None:
                raise ValueError(f"Section index {idx} is missing 'section_order'.")
            if not isinstance(order, int) or order <= 0:
                raise ValueError(f"Section index {idx} 'section_order' must be a positive integer.")
            if order in seen_section_orders:
                raise ValueError(f"Duplicate 'section_order' found: {order}")
            
            # Check fields
            if not section.get("title") or not str(section["title"]).strip():
                raise ValueError(f"Section {order} title cannot be empty.")
            # Note: raw section JSON has 'text' field
            if not section.get("text") or not str(section["text"]).strip():
                raise ValueError(f"Section {order} text cannot be empty.")
                
            seen_section_orders.add(order)
            sections_by_order[order] = section

        # Check section orders are contiguous 1..N
        sorted_orders = sorted(list(seen_section_orders))
        expected_orders = list(range(1, len(sections) + 1))
        if sorted_orders != expected_orders:
            raise ValueError(f"Section orders must be contiguous from 1 to {len(sections)}. Got {sorted_orders}")

        # 3. Chunks validation
        if not chunks:
            raise ValueError("Chunks list cannot be empty.")
        if expected_chunk_count is not None and len(chunks) != expected_chunk_count:
            raise ValueError(f"Expected {expected_chunk_count} chunks, got {len(chunks)}.")

        seen_chunk_ids = set()
        chunks_by_section = {} # section_order -> list of chunks

        for idx, chunk in enumerate(chunks, start=1):
            chunk_id = chunk.get("chunk_id")
            if not chunk_id or not str(chunk_id).strip():
                raise ValueError(f"Chunk index {idx} is missing or has empty 'chunk_id'.")
            if chunk_id in seen_chunk_ids:
                raise ValueError(f"Duplicate chunk_id found: {chunk_id}")
            seen_chunk_ids.add(chunk_id)

            # Check other required fields
            for f in ["section_order", "section_title", "chunk_order", "token_count", "text"]:
                if chunk.get(f) is None:
                    raise ValueError(f"Chunk {chunk_id} is missing required field '{f}'.")

            sec_order = chunk["section_order"]
            if sec_order not in sections_by_order:
                raise ValueError(f"Chunk {chunk_id} references non-existent section_order: {sec_order}.")

            # Validate section title matching
            target_section = sections_by_order[sec_order]
            if chunk["section_title"] != target_section["title"]:
                raise ValueError(
                    f"Section title mismatch for chunk {chunk_id}: "
                    f"chunk says '{chunk['section_title']}', section says '{target_section['title']}'."
                )

            # Basic limits
            if chunk["chunk_order"] <= 0:
                raise ValueError(f"Chunk {chunk_id} 'chunk_order' must be greater than 0.")
            if not (1 <= chunk["token_count"] <= 220):
                raise ValueError(f"Chunk {chunk_id} 'token_count' must be between 1 and 220.")
            if not str(chunk["text"]).strip():
                raise ValueError(f"Chunk {chunk_id} text cannot be empty.")

            chunks_by_section.setdefault(sec_order, []).append(chunk)

        # 4. Check continuity of chunks within each section
        for sec_order, sec_chunks in chunks_by_section.items():
            sorted_chunks = sorted(sec_chunks, key=lambda c: c["chunk_order"])
            chunk_orders = [c["chunk_order"] for c in sorted_chunks]
            expected_chunk_orders = list(range(1, len(sec_chunks) + 1))
            if chunk_orders != expected_chunk_orders:
                raise ValueError(
                    f"Chunk orders for section {sec_order} must be contiguous starting from 1. "
                    f"Got {chunk_orders}"
                )

    def ingest(self, document: dict, sections: list[dict], chunks: list[dict], replace: bool = False) -> dict:
        """
        Executes the content ingestion inside a single SQL transaction.
        Removes existing content if replace is True; raises ValueError on conflict if replace is False.
        """
        doc_id = document["document_id"]

        with get_connection() as conn:
            with conn.transaction():
                # Check document existence
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM documents WHERE document_id = %s;", (doc_id,))
                    exists = cur.fetchone() is not None

                if exists:
                    if not replace:
                        raise ValueError(f"Document {doc_id} already exists. Use --replace to replace existing content.")
                    else:
                        logger.warning(f"WARNING: --replace deletes existing chunks and any associated embeddings for document '{doc_id}'.")
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM documents WHERE document_id = %s;", (doc_id,))

                # 1. Insert Document
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO documents (document_id, title, author, source_name, source_reference)
                        VALUES (%(document_id)s, %(title)s, %(author)s, %(source_name)s, %(source_reference)s);
                        """,
                        {
                            "document_id": doc_id,
                            "title": document["title"],
                            "author": document.get("author"),
                            "source_name": document["source_name"],
                            "source_reference": document.get("source_reference")
                        }
                    )

                # 2. Insert Sections & collect generated ids
                section_id_map = {}
                with conn.cursor() as cur:
                    for section in sections:
                        cur.execute(
                            """
                            INSERT INTO sections (document_id, section_order, title, section_text)
                            VALUES (%s, %s, %s, %s)
                            RETURNING section_id;
                            """,
                            (
                                doc_id,
                                section["section_order"],
                                section["title"],
                                section["text"] # Mapping 'text' to 'section_text'
                            )
                        )
                        generated_sec_id = cur.fetchone()[0]
                        section_id_map[section["section_order"]] = generated_sec_id

                # 3. Batch Insert Chunks using executemany
                chunk_rows = [
                    {
                        "chunk_uid": chunk["chunk_id"],
                        "section_id": section_id_map[chunk["section_order"]],
                        "chunk_order": chunk["chunk_order"],
                        "token_count": chunk["token_count"],
                        "overlap_tokens": chunk.get("overlap_tokens", 0),
                        "chunk_text": chunk["text"]
                    }
                    for chunk in chunks
                ]

                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO chunks (chunk_uid, section_id, chunk_order, token_count, overlap_tokens, chunk_text)
                        VALUES (%(chunk_uid)s, %(section_id)s, %(chunk_order)s, %(token_count)s, %(overlap_tokens)s, %(chunk_text)s);
                        """,
                        chunk_rows
                    )

                # 4. Post-Ingestion database quantity verification
                with conn.cursor() as cur:
                    # Document count
                    cur.execute("SELECT COUNT(*) FROM documents WHERE document_id = %s;", (doc_id,))
                    actual_docs = cur.fetchone()[0]
                    if actual_docs != 1:
                        raise ValueError(f"Post-ingestion check failed. Document count for '{doc_id}' is {actual_docs}, expected 1.")

                    # Section count
                    cur.execute("SELECT COUNT(*) FROM sections WHERE document_id = %s;", (doc_id,))
                    actual_sections = cur.fetchone()[0]
                    if actual_sections != len(sections):
                        raise ValueError(f"Post-ingestion check failed. Section count for '{doc_id}' is {actual_sections}, expected {len(sections)}.")

                    # Chunk count
                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM chunks c
                        JOIN sections s ON s.section_id = c.section_id
                        WHERE s.document_id = %s;
                        """,
                        (doc_id,)
                    )
                    actual_chunks = cur.fetchone()[0]
                    if actual_chunks != len(chunks):
                        raise ValueError(f"Post-ingestion check failed. Chunk count for '{doc_id}' is {actual_chunks}, expected {len(chunks)}.")

                    # Embeddings count (should be 0)
                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM minilm_embeddings e
                        JOIN chunks c ON c.chunk_id = e.chunk_id
                        JOIN sections s ON s.section_id = c.section_id
                        WHERE s.document_id = %s;
                        """,
                        (doc_id,)
                    )
                    actual_embeddings = cur.fetchone()[0]
                    if actual_embeddings != 0:
                        raise ValueError(f"Post-ingestion check failed. Embedding count for '{doc_id}' is {actual_embeddings}, expected 0.")

        # Ingestion was successful
        return {
            "document_id": doc_id,
            "document_count": 1,
            "section_count": len(sections),
            "chunk_count": len(chunks),
            "embedding_count": 0,
            "replace_mode": replace,
            "status": "success"
        }
