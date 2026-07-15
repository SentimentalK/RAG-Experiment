import pytest
import numpy as np
import json
import hashlib
from app.db.connection import get_connection
from app.providers.minilm_provider import MiniLMProvider
from app.services.vector_search_service import VectorSearchService
from app.services.content_ingestion_service import ContentIngestionService
from app.services.embedding_ingestion_service import EmbeddingIngestionService
from app.core.config import settings
from app.core.exceptions import (
    InvalidRagRequestError,
    DocumentNotFoundError,
    RetrievalUnavailableError,
)


@pytest.fixture(autouse=True)
def clean_test_documents():
    """
    Autouse fixture that runs after each test to clean up any test documents
    added during testing, leaving the production Sherlock documents untouched.
    """
    yield
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE document_id LIKE 'test-vector-search-%';")
        conn.commit()

@pytest.fixture
def provider() -> MiniLMProvider:
    return MiniLMProvider(device="cpu")

@pytest.fixture
def service(provider) -> VectorSearchService:
    return VectorSearchService(provider)

@pytest.fixture
def production_doc_id() -> str:
    return "gutenberg-1661"

@pytest.fixture(autouse=True)
def loaded_production_data():
    """
    Auto-ingests gutenberg-1661 and its embeddings if they are missing or incomplete.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM documents WHERE document_id = 'gutenberg-1661');")
            doc_exists = cur.fetchone()[0]
            
            chunk_count = 0
            emb_count = 0
            if doc_exists:
                cur.execute(
                    """
                    SELECT
                        COUNT(c.chunk_id) AS chunk_count,
                        COUNT(e.chunk_id) AS embedding_count
                    FROM chunks c
                    JOIN sections s ON s.section_id = c.section_id
                    LEFT JOIN minilm_embeddings e ON e.chunk_id = c.chunk_id AND e.model_name = 'sentence-transformers/all-MiniLM-L6-v2'
                    WHERE s.document_id = 'gutenberg-1661';
                    """
                )
                chunk_count, emb_count = cur.fetchone()

    if not doc_exists or chunk_count != 909 or emb_count != 909:
        # Load files and ingest
        doc_path = settings.PROCESSED_DATA_DIR / "document.json"
        sec_path = settings.PROCESSED_DATA_DIR / "sections.jsonl"
        chk_path = settings.PROCESSED_DATA_DIR / "chunks.jsonl"
        
        with doc_path.open("r", encoding="utf-8") as f:
            doc = json.load(f)
        if "document_id" not in doc:
            doc["document_id"] = "gutenberg-1661"
        if "source_name" not in doc:
            doc["source_name"] = "Project Gutenberg"
        if "source_reference" not in doc:
            doc["source_reference"] = "1661"
            
        sections = []
        with sec_path.open("r", encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    sections.append(json.loads(l))
                    
        chunks = []
        with chk_path.open("r", encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    chunks.append(json.loads(l))
                    
        content_service = ContentIngestionService()
        content_service.ingest(doc, sections, chunks, replace=True)
        
        # Load embeddings
        npy_path = settings.DATA_DIR / "artifacts" / "minilm_embeddings.npy"
        index_path = settings.DATA_DIR / "artifacts" / "minilm_embedding_index.jsonl"
        
        embeddings = np.load(npy_path, allow_pickle=False)
        index_records = []
        with index_path.open("r", encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    index_records.append(json.loads(l))
                    
        expected_chunks = {
            c["chunk_id"]: {
                "section_order": c["section_order"],
                "section_title": c["section_title"],
                "chunk_order": c["chunk_order"],
                "token_count": c["token_count"],
                "text_sha256": hashlib.sha256(c["text"].encode("utf-8")).hexdigest()
            }
            for c in chunks
        }
        
        emb_service = EmbeddingIngestionService()
        emb_service.ingest(
            document_id="gutenberg-1661",
            embeddings=embeddings,
            index_records=index_records,
            expected_chunks=expected_chunks,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            replace=True
        )

# ----------------- Input validations tests -----------------

def test_search_invalid_question_type(service):
    with pytest.raises(InvalidRagRequestError, match="Question must be a string"):
        service.search(None, "gutenberg-1661")

def test_search_empty_question(service):
    with pytest.raises(InvalidRagRequestError, match="Question cannot be empty"):
        service.search("   ", "gutenberg-1661")

def test_search_invalid_top_k(service):
    with pytest.raises(InvalidRagRequestError, match="top_k must be between 1 and 50"):
        service.search("Query", "gutenberg-1661", top_k=0)
    with pytest.raises(InvalidRagRequestError, match="top_k must be between 1 and 50"):
        service.search("Query", "gutenberg-1661", top_k=51)

def test_search_too_long_question(service, provider):
    # Construct a question that has more than 256 tokens
    long_question = "word " * 300
    with pytest.raises(InvalidRagRequestError, match="Question contains .* tokens, but the model limit is"):
        service.search(long_question, "gutenberg-1661")

# ----------------- Database Coverage validations tests -----------------

def test_search_document_not_found(service):
    with pytest.raises(DocumentNotFoundError, match="Document not found: test-vector-search-non-existent"):
        service.search("Sherlock Holmes", "test-vector-search-non-existent")

def test_search_document_no_chunks(service):
    # Insert a document but no sections or chunks
    doc_id = "test-vector-search-empty"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (document_id, title, author, source_name)
                VALUES (%s, 'Empty Doc', 'Author', 'Source');
                """,
                (doc_id,)
            )
        conn.commit()

    with pytest.raises(RetrievalUnavailableError, match="contains no chunks"):
        service.search("Sherlock Holmes", doc_id)

def test_search_incomplete_embeddings(service):
    doc_id = "test-vector-search-incomplete"
    
    # 1. Ingest document, section, and 3 chunks
    document = {
        "document_id": doc_id,
        "title": "Incomplete Book",
        "author": "Author",
        "source_name": "Source"
    }
    sections = [
        {"section_order": 1, "title": "Sec 1", "text": "Sec text 1"}
    ]
    chunks = [
        {"chunk_id": "test-c-1", "section_order": 1, "section_title": "Sec 1", "chunk_order": 1, "token_count": 5, "text": "Text one"},
        {"chunk_id": "test-c-2", "section_order": 1, "section_title": "Sec 1", "chunk_order": 2, "token_count": 5, "text": "Text two"},
        {"chunk_id": "test-c-3", "section_order": 1, "section_title": "Sec 1", "chunk_order": 3, "token_count": 5, "text": "Text three"}
    ]
    
    content_service = ContentIngestionService()
    content_service.ingest(document, sections, chunks, replace=False)

    # 2. Manually insert embeddings for only 2 out of the 3 chunks
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT chunk_id FROM chunks WHERE chunk_uid = 'test-c-1';")
            db_cid_1 = cur.fetchone()[0]
            cur.execute("SELECT chunk_id FROM chunks WHERE chunk_uid = 'test-c-2';")
            db_cid_2 = cur.fetchone()[0]
            
            dummy_vector = [1.0] + [0.0] * 383
            cur.execute(
                """
                INSERT INTO minilm_embeddings (chunk_id, model_name, dimensions, normalized, embedding)
                VALUES (%s, 'sentence-transformers/all-MiniLM-L6-v2', 384, TRUE, %s),
                       (%s, 'sentence-transformers/all-MiniLM-L6-v2', 384, TRUE, %s);
                """,
                (db_cid_1, dummy_vector, db_cid_2, dummy_vector)
            )
        conn.commit()

    # 3. Assert search fails due to incomplete coverage
    with pytest.raises(RetrievalUnavailableError, match="Embedding coverage incomplete: chunks=3, embeddings=2"):
        service.search("Sherlock Holmes", doc_id)

# ----------------- Exact vector search behavior tests -----------------

def test_search_results_math_and_order(service, production_doc_id):
    """
    Verifies rank metrics (distance / similarity) mathematical relation,
    and rank distance order is non-decreasing.
    """
    res = service.search("Why did Sherlock Holmes remember Irene Adler?", production_doc_id, top_k=10)
    
    assert res["status"] == "success"
    assert len(res["results"]) == 10
    
    distances = []
    for item in res["results"]:
        dist = item["cosine_distance"]
        sim = item["cosine_similarity"]
        
        # Verify cosine_similarity = 1.0 - cosine_distance
        assert np.isclose(sim, 1.0 - dist, atol=1e-6)
        distances.append(dist)

    # Verify rank order is non-decreasing (distance is sorting key ascending)
    assert all(distances[i] <= distances[i + 1] for i in range(len(distances) - 1))

def test_search_closed_loop_self_match(service, production_doc_id):
    """
    Closed-loop validation: querying with the exact text of a chunk
    must yield the chunk itself as Rank 1 with distance close to 0.
    """
    # 1. Fetch a sample chunk from the database
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.chunk_uid, c.chunk_text
                FROM chunks c
                JOIN sections s ON s.section_id = c.section_id
                WHERE s.document_id = %s
                LIMIT 1;
                """,
                (production_doc_id,)
            )
            chunk_uid, chunk_text = cur.fetchone()

    # 2. Search using the chunk text
    res = service.search(chunk_text, production_doc_id, top_k=3)
    
    top_result = res["results"][0]
    assert top_result["chunk_uid"] == chunk_uid
    assert top_result["cosine_distance"] < 1e-5

def test_search_results_against_numpy_brute_force(service, provider, production_doc_id):
    """
    Validates PostgreSQL exact cosine search ranking results against NumPy local brute-force matrix multiplication.
    Tolerates float precision swaps within tie groups (<= 1e-6 score difference).
    """
    question = "Why did Sherlock Holmes remember Irene Adler?"
    
    # 1. Load local cache matrices
    npy_path = settings.DATA_DIR / "artifacts" / "minilm_embeddings.npy"
    index_path = settings.DATA_DIR / "artifacts" / "minilm_embedding_index.jsonl"
    
    local_embeddings = np.load(npy_path, allow_pickle=False)
    index_records = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                index_records.append(json.loads(line))

    # 2. Local NumPy cosine similarity & distance brute-force calculation
    query_emb = provider.encode(question)
    
    # Since both vectors are L2 normalized, similarity is the dot product
    local_similarities = local_embeddings @ query_emb
    
    local_scored = [
        {
            "chunk_uid": index_records[i]["chunk_id"],
            "similarity": float(local_similarities[i]),
            "distance": float(1.0 - local_similarities[i])
        }
        for i in range(len(index_records))
    ]
    
    # Sort local results: ascending by distance, then by chunk_uid
    local_scored.sort(key=lambda x: (x["distance"], x["chunk_uid"]))
    local_top_10 = local_scored[:10]

    # 3. Fetch RAG database results
    res = service.search(question, production_doc_id, top_k=10)
    db_top_10 = res["results"]
    
    assert len(db_top_10) == len(local_top_10)

    # 4. Group results by distance tie groups to handle potential float-swapping
    def get_groups(records):
        groups = []
        if not records:
            return groups
        current_group = [records[0]]
        for r in records[1:]:
            dist_key = "cosine_distance" if "cosine_distance" in r else "distance"
            curr_dist_key = "cosine_distance" if "cosine_distance" in current_group[0] else "distance"
            if abs(r[dist_key] - current_group[0][curr_dist_key]) <= 1e-6:
                current_group.append(r)
            else:
                groups.append(current_group)
                current_group = [r]
        groups.append(current_group)
        return groups

    local_groups = get_groups(local_top_10)
    db_groups = get_groups(db_top_10)

    # Check similarities match
    for idx in range(10):
        assert np.isclose(db_top_10[idx]["cosine_similarity"], local_top_10[idx]["similarity"], atol=1e-5)

    # Verify tie groups contain the same set of chunk uids
    assert len(local_groups) == len(db_groups)
    for lg, dg in zip(local_groups, db_groups):
        lg_uids = {x["chunk_uid"] for x in lg}
        dg_uids = {x["chunk_uid"] for x in dg}
        assert lg_uids == dg_uids

def test_search_isolation_multiple_documents(service):
    """
    Verifies document filtration: query results can only contain chunks belonging
    to the requested document_id.
    """
    # 1. Setup doc A
    doc_a = "test-vector-search-doc-a"
    document_a = {"document_id": doc_a, "title": "Doc A", "author": "A", "source_name": "S"}
    sections_a = [{"section_order": 1, "title": "Sec A", "text": "Sec text A"}]
    chunks_a = [{"chunk_id": "chk-a1", "section_order": 1, "section_title": "Sec A", "chunk_order": 1, "token_count": 5, "text": "Common matching query content"}]
    
    # 2. Setup doc B
    doc_b = "test-vector-search-doc-b"
    document_b = {"document_id": doc_b, "title": "Doc B", "author": "B", "source_name": "S"}
    sections_b = [{"section_order": 1, "title": "Sec B", "text": "Sec text B"}]
    chunks_b = [{"chunk_id": "chk-b1", "section_order": 1, "section_title": "Sec B", "chunk_order": 1, "token_count": 5, "text": "Common matching query content"}]

    content_service = ContentIngestionService()
    content_service.ingest(document_a, sections_a, chunks_a)
    content_service.ingest(document_b, sections_b, chunks_b)

    # 3. Setup embeddings for both docs
    emb_service = EmbeddingIngestionService()
    matrix = np.zeros((1, 384), dtype=np.float32)
    matrix[0, 0] = 1.0 # norm = 1.0
    
    index_a = [{"row_index": 0, "chunk_id": "chk-a1", "section_order": 1, "section_title": "Sec A", "chunk_order": 1, "token_count": 5}]
    exp_a = {"chk-a1": {"section_order": 1, "section_title": "Sec A", "chunk_order": 1, "token_count": 5, "text_sha256": hashlib.sha256("Common matching query content".encode("utf-8")).hexdigest()}}
    emb_service.ingest(doc_a, matrix, index_a, exp_a, "sentence-transformers/all-MiniLM-L6-v2")

    index_b = [{"row_index": 0, "chunk_id": "chk-b1", "section_order": 1, "section_title": "Sec B", "chunk_order": 1, "token_count": 5}]
    exp_b = {"chk-b1": {"section_order": 1, "section_title": "Sec B", "chunk_order": 1, "token_count": 5, "text_sha256": hashlib.sha256("Common matching query content".encode("utf-8")).hexdigest()}}
    emb_service.ingest(doc_b, matrix, index_b, exp_b, "sentence-transformers/all-MiniLM-L6-v2")

    # 4. Search on document A
    res_a = service.search("Common matching query content", doc_a, top_k=10)
    assert len(res_a["results"]) == 1
    assert res_a["results"][0]["chunk_uid"] == "chk-a1"

    # 5. Search on document B
    res_b = service.search("Common matching query content", doc_b, top_k=10)
    assert len(res_b["results"]) == 1
    assert res_b["results"][0]["chunk_uid"] == "chk-b1"
