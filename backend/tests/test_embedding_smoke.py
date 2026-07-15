import pytest
import json
import numpy as np
from app.providers.minilm_provider import MiniLMProvider

@pytest.fixture(scope="session")
def provider() -> MiniLMProvider:
    """
    Session-scoped fixture to load the MiniLM model only once for the entire test session.
    """
    return MiniLMProvider(device="cpu")

@pytest.fixture(scope="session")
def sample_chunk() -> dict:
    """
    Sample chunk metadata and text matching the first chunk structure.
    """
    return {
        "chunk_id": "g1661-s01-c0001",
        "section_order": 1,
        "section_title": "A Scandal in Bohemia",
        "chunk_order": 1,
        "token_count": 41, # Calculated token count for the exact text below
        "text": (
            "I. To Sherlock Holmes she is always the woman. I have seldom heard him "
            "mention her under any other name. In his eyes she eclipses and predominates "
            "the whole of her sex."
        )
    }

def test_real_chunk_can_be_encoded(provider: MiniLMProvider, sample_chunk: dict):
    """
    Verifies that a valid text from a chunk is correctly converted to a 384-dim np.float32 vector
    which is properly normalized to unit length.
    """
    embedding = provider.encode(sample_chunk["text"])
    
    assert embedding.shape == (384,)
    assert embedding.dtype == np.float32
    assert np.isfinite(embedding).all()
    
    # L2 norm check
    norm = np.linalg.norm(embedding)
    assert np.isclose(norm, 1.0, atol=1e-5)

def test_empty_and_invalid_inputs_rejected(provider: MiniLMProvider):
    """
    Verifies that empty strings, whitespace, or invalid types are rejected with correct exceptions.
    """
    # Empty string
    with pytest.raises(ValueError):
        provider.encode("")
        
    # Whitespace only
    with pytest.raises(ValueError):
        provider.encode("   ")
        
    # Non-string types
    with pytest.raises(TypeError):
        provider.encode(None)
        
    with pytest.raises(TypeError):
        provider.encode(123)

def test_embedding_determinism(provider: MiniLMProvider, sample_chunk: dict):
    """
    Verifies that encoding the exact same text twice results in near-identical values.
    """
    embedding_a = provider.encode(sample_chunk["text"])
    embedding_b = provider.encode(sample_chunk["text"])
    
    np.testing.assert_allclose(
        embedding_a,
        embedding_b,
        rtol=1e-5,
        atol=1e-6
    )

def test_different_texts_produce_different_embeddings(provider: MiniLMProvider):
    """
    Verifies that two distinct text sentences do not produce identical embedding values.
    """
    embedding_a = provider.encode("Sherlock Holmes examined the room.")
    embedding_b = provider.encode("The weather was warm and sunny.")
    
    assert not np.allclose(embedding_a, embedding_b)

def test_stored_token_count_matches_model_tokenizer(provider: MiniLMProvider, sample_chunk: dict):
    """
    Verifies that the token count computed by provider matches the expected value,
    and conforms to MAX_TOKENS and max sequence length limits.
    """
    actual = provider.count_tokens(sample_chunk["text"])
    
    assert actual == sample_chunk["token_count"]
    assert actual <= 220
    assert actual <= provider.max_sequence_length

def test_embedding_json_serialization(provider: MiniLMProvider, sample_chunk: dict):
    """
    Verifies that the numpy float32 array can be converted to standard python float lists
    and safely serialized into standard JSON strings.
    """
    embedding = provider.encode(sample_chunk["text"])
    
    payload = {
        "vector_norm": float(np.linalg.norm(embedding)),
        "embedding": embedding.tolist(),
    }
    
    serialized = json.dumps(payload)
    assert serialized
    assert len(payload["embedding"]) == 384
    assert all(isinstance(v, float) for v in payload["embedding"])
