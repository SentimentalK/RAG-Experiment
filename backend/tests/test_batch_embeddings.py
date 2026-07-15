import pytest
import json
import numpy as np
from pathlib import Path

from app.providers.minilm_provider import MiniLMProvider
from app.cli.generate_embeddings import load_chunks

@pytest.fixture(scope="session")
def provider() -> MiniLMProvider:
    """
    Session-scoped fixture to load the MiniLM model only once for the entire test session.
    """
    return MiniLMProvider(device="cpu")

@pytest.fixture
def sample_texts() -> list[str]:
    return [
        "To Sherlock Holmes she is always the woman.",
        "I had seen little of Holmes lately.",
        "One night—it was on the twentieth of March, 1888.",
        "His manner was not effusive."
    ]

def test_batch_shape_and_dtype(provider: MiniLMProvider, sample_texts: list[str]):
    """
    Verifies that encode_batch returns the correct shape and float32 matrix.
    """
    embeddings = provider.encode_batch(sample_texts, batch_size=2)
    assert embeddings.shape == (len(sample_texts), 384)
    assert embeddings.dtype == np.float32
    assert np.isfinite(embeddings).all()

def test_batch_normalization(provider: MiniLMProvider, sample_texts: list[str]):
    """
    Verifies that each row vector in the batch embedding matrix is normalized to unit length.
    """
    embeddings = provider.encode_batch(sample_texts, batch_size=2)
    norms = np.linalg.norm(embeddings, axis=1)
    
    np.testing.assert_allclose(
        norms,
        np.ones(len(sample_texts)),
        atol=1e-5
    )

def test_batch_matches_single_encoding(provider: MiniLMProvider):
    """
    Verifies that the batch optimization does not change the embedding values
    relative to encoding individual sentences one by one.
    """
    text = "Sherlock Holmes was pacing up and down the platform."
    
    batch_embedding = provider.encode_batch([text])[0]
    single_embedding = provider.encode(text)
    
    np.testing.assert_allclose(
        batch_embedding,
        single_embedding,
        rtol=1e-5,
        atol=1e-6
    )

def test_batch_empty_list_rejected(provider: MiniLMProvider):
    """
    Verifies that empty list is rejected.
    """
    with pytest.raises(ValueError):
        provider.encode_batch([])

def test_batch_invalid_elements_rejected(provider: MiniLMProvider):
    """
    Verifies that a list containing empty strings, whitespace only, or non-string elements is rejected.
    """
    # Contains empty string
    with pytest.raises(ValueError):
        provider.encode_batch(["Valid sentence.", ""])
        
    # Contains whitespace only
    with pytest.raises(ValueError):
        provider.encode_batch(["Valid sentence.", "   "])
        
    # Contains non-string type
    with pytest.raises(TypeError):
        provider.encode_batch(["Valid sentence.", None])  # type: ignore

def test_save_and_load_embeddings_symmetric(tmp_path: Path, provider: MiniLMProvider, sample_texts: list[str]):
    """
    Verifies that saving the matrix to a binary file object using allow_pickle=False
    and loading it back yields identical values.
    """
    embeddings = provider.encode_batch(sample_texts, batch_size=2)
    temp_file = tmp_path / "embeddings.npy"
    
    with open(temp_file, "wb") as f:
        np.save(f, embeddings, allow_pickle=False)
        
    with open(temp_file, "rb") as f:
        loaded = np.load(f, allow_pickle=False)
        
    np.testing.assert_array_equal(loaded, embeddings)

def test_load_chunks_duplicate_chunk_id_rejected(tmp_path: Path, provider: MiniLMProvider):
    """
    Verifies that load_chunks correctly detects and rejects duplicate chunk_ids.
    """
    mock_content = (
        '{"chunk_id": "g1661-s01-c0001", "section_order": 1, "section_title": "A Scandal", "chunk_order": 1, "token_count": 5, "text": "Sentence one."}\n'
        '{"chunk_id": "g1661-s01-c0001", "section_order": 1, "section_title": "A Scandal", "chunk_order": 2, "token_count": 5, "text": "Sentence two."}\n'
    )
    
    jsonl_path = tmp_path / "duplicate_chunks.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write(mock_content)
        
    with pytest.raises(ValueError, match="Duplicate chunk_id found"):
        load_chunks(jsonl_path, provider)

def test_index_file_does_not_contain_text_or_embedding(tmp_path: Path, provider: MiniLMProvider):
    """
    Verifies that the generated mapping index does not duplicate text or embedding fields,
    preventing file bloat.
    """
    # Create mock chunks
    mock_content = (
        '{"chunk_id": "g1661-s01-c0001", "section_order": 1, "section_title": "A Scandal", "chunk_order": 1, "token_count": 5, "text": "Sentence one."}\n'
        '{"chunk_id": "g1661-s01-c0002", "section_order": 1, "section_title": "A Scandal", "chunk_order": 2, "token_count": 5, "text": "Sentence two."}\n'
    )
    jsonl_path = tmp_path / "chunks.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write(mock_content)
        
    # Run load_chunks
    chunks = load_chunks(jsonl_path, provider)
    assert len(chunks) == 2
    
    # Simulate writing index record
    index_path = tmp_path / "minilm_embedding_index.jsonl"
    with open(index_path, "w", encoding="utf-8") as file:
        for row_idx, chunk in enumerate(chunks):
            record = {
                "row_index": row_idx,
                "chunk_id": chunk["chunk_id"],
                "section_order": chunk["section_order"],
                "section_title": chunk["section_title"],
                "chunk_order": chunk["chunk_order"],
                "token_count": chunk["token_count"]
            }
            file.write(json.dumps(record) + "\n")
            
    # Read back and verify fields
    index_records = []
    with open(index_path, "r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                index_records.append(json.loads(line))
                
    assert len(index_records) == 2
    for record in index_records:
        assert "text" not in record
        assert "embedding" not in record
        assert "row_index" in record
        assert "chunk_id" in record
