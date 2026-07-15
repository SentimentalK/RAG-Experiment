from dataclasses import dataclass
from time import perf_counter
import numpy as np
import psycopg
from app.db.connection import get_connection
from app.providers.minilm_provider import MiniLMProvider
from app.core.exceptions import (
    InvalidRagRequestError,
    DocumentNotFoundError,
    RetrievalUnavailableError,
)

@dataclass(frozen=True)
class VectorSearchResult:
    rank: int
    chunk_uid: str
    section_order: int
    section_title: str
    chunk_order: int
    token_count: int
    chunk_text: str
    cosine_distance: float
    cosine_similarity: float

class VectorSearchService:
    """
    Service responsible for encoding query strings and running exact cosine similarity searches
    against the PostgreSQL database.
    """

    def __init__(self, provider: MiniLMProvider) -> None:
        self._provider = provider

    def search(self, question: str, document_id: str, top_k: int = 10) -> dict:
        """
        Validates arguments, runs model-aware database coverage audits,
        generates the query embedding, and returns top_k matching chunks sorted by cosine distance.
        """
        # 1. Question validation
        if not isinstance(question, str):
            raise InvalidRagRequestError("Question must be a string.")

        question = question.strip()
        if not question:
            raise InvalidRagRequestError("Question cannot be empty.")

        # 2. top_k validation
        if not (1 <= top_k <= 50):
            raise InvalidRagRequestError("top_k must be between 1 and 50.")

        # 3. Question Token length validation
        query_token_count = self._provider.count_tokens(question)
        if query_token_count > self._provider.max_sequence_length:
            raise InvalidRagRequestError(
                f"Question contains {query_token_count} tokens, "
                f"but the model limit is {self._provider.max_sequence_length}."
            )

        with get_connection() as conn:
            # 4. Document existence check
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM documents WHERE document_id = %s);",
                    (document_id,)
                )
                doc_exists = cur.fetchone()[0]

            if not doc_exists:
                raise DocumentNotFoundError(f"Document not found: {document_id}")

            # 5. Database coverage checks filtered by document and model name
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(c.chunk_id) AS chunk_count,
                        COUNT(e.chunk_id) AS embedding_count
                    FROM chunks c
                    JOIN sections s ON s.section_id = c.section_id
                    LEFT JOIN minilm_embeddings e
                      ON e.chunk_id = c.chunk_id
                     AND e.model_name = %s
                    WHERE s.document_id = %s;
                    """,
                    (self._provider.model_name, document_id)
                )
                chunk_count, embedding_count = cur.fetchone()

            if chunk_count == 0:
                raise RetrievalUnavailableError(f"Document contains no chunks: {document_id}")

            if embedding_count != chunk_count:
                raise RetrievalUnavailableError(
                    f"Embedding coverage incomplete: chunks={chunk_count}, "
                    f"embeddings={embedding_count} for model '{self._provider.model_name}'."
                )

            # 6. Generate embedding & measure encoding duration
            start_encode = perf_counter()
            query_embedding = self._provider.encode(question)
            encoding_duration_ms = (perf_counter() - start_encode) * 1000

            # 7. Execute Exact Cosine Search & measure database duration
            start_db = perf_counter()
            results = []
            
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH query_vector AS (
                        SELECT %s::vector(384) AS embedding
                    ),
                    scored_chunks AS (
                        SELECT
                            c.chunk_uid,
                            s.section_order,
                            s.title AS section_title,
                            c.chunk_order,
                            c.token_count,
                            c.chunk_text,
                            e.embedding <=> q.embedding AS cosine_distance
                        FROM minilm_embeddings e
                        JOIN chunks c ON c.chunk_id = e.chunk_id
                        JOIN sections s ON s.section_id = c.section_id
                        CROSS JOIN query_vector q
                        WHERE s.document_id = %s
                          AND e.model_name = %s
                    )
                    SELECT
                        chunk_uid,
                        section_order,
                        section_title,
                        chunk_order,
                        token_count,
                        chunk_text,
                        cosine_distance,
                        1.0 - cosine_distance AS cosine_similarity
                    FROM scored_chunks
                    ORDER BY
                        cosine_distance ASC,
                        chunk_uid ASC
                    LIMIT %s;
                    """,
                    (query_embedding, document_id, self._provider.model_name, top_k)
                )
                rows = cur.fetchall()

            db_duration_ms = (perf_counter() - start_db) * 1000

            for rank_idx, row in enumerate(rows, start=1):
                uid, sec_order, sec_title, chk_order, tokens, text, distance, similarity = row
                results.append(
                    VectorSearchResult(
                        rank=rank_idx,
                        chunk_uid=uid,
                        section_order=sec_order,
                        section_title=sec_title,
                        chunk_order=chk_order,
                        token_count=tokens,
                        chunk_text=text,
                        cosine_distance=float(distance),
                        cosine_similarity=float(similarity)
                    )
                )

        return {
            "status": "success",
            "question": question,
            "document_id": document_id,
            "model_name": self._provider.model_name,
            "search_mode": "exact_cosine",
            "query_token_count": query_token_count,
            "query_dimensions": 384,
            "query_vector_norm": float(np.linalg.norm(query_embedding)),
            "embedding_duration_ms": encoding_duration_ms,
            "database_duration_ms": db_duration_ms,
            "top_k": top_k,
            "available_chunk_count": chunk_count,
            "available_embedding_count": embedding_count,
            "results": [
                {
                    "rank": r.rank,
                    "chunk_uid": r.chunk_uid,
                    "section_order": r.section_order,
                    "section_title": r.section_title,
                    "chunk_order": r.chunk_order,
                    "token_count": r.token_count,
                    "cosine_distance": r.cosine_distance,
                    "cosine_similarity": r.cosine_similarity,
                    "chunk_text": r.chunk_text
                }
                for r in results
            ]
        }
