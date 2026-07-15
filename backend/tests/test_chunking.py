import pytest
from app.services.chunking_service import ChunkingService

def test_split_into_sentences_abbreviations():
    service = ChunkingService()
    
    assert service.split_into_sentences("Mr. Holmes entered the room.") == ["Mr. Holmes entered the room."]
    assert service.split_into_sentences("Dr. Watson replied immediately.") == ["Dr. Watson replied immediately."]
    assert service.split_into_sentences("Mrs. Hudson opened the door.") == ["Mrs. Hudson opened the door."]
    assert service.split_into_sentences("St. James's Street was quiet.") == ["St. James's Street was quiet."]
    assert service.split_into_sentences("J. H. Watson wrote the account.") == ["J. H. Watson wrote the account."]
    assert service.split_into_sentences("“What happened?” asked Holmes.") == ["“What happened?” asked Holmes."]
    
    # Standard multi-sentence check
    text = "First sentence. Second sentence! Third sentence? Yes."
    assert service.split_into_sentences(text) == [
        "First sentence.",
        "Second sentence!",
        "Third sentence?",
        "Yes."
    ]

def test_chunking_hard_ceiling_and_overlong_sentences():
    service = ChunkingService()
    
    # Create an extremely long sentence (e.g. 250 repeating words) to trigger fallback splitting
    giant_sentence = " ".join(["word"] * 250) + "."
    giant_len = service.count_tokens(giant_sentence)
    assert giant_len > 220
    
    section = {
        "section_order": 1,
        "title": "Mock Section",
        "text": giant_sentence
    }
    
    chunks = service.chunk_section(section)
    assert len(chunks) > 0
    for chunk in chunks:
        # Verify strict 220 token ceiling
        assert chunk["token_count"] <= 220
        assert chunk["token_count"] > 0
        assert chunk["text"].strip() != ""

def test_chunking_preserves_all_content():
    service = ChunkingService()
    
    text = (
        "This is the first sentence. Mr. Holmes was sitting by the fire. "
        "He looked at the letter attentively for some time. Then he sighed.\n\n"
        "Another paragraph starts here. Dr. Watson was present too. "
        "They both discussed the case. The mystery was deep."
    )
    
    section = {
        "section_order": 2,
        "title": "Mock Preservation",
        "text": text
    }
    
    chunks = service.chunk_section(section)
    assert len(chunks) > 0
    
    # Reconstruct sentence list from chunks without overlap
    reconstructed_sentences = []
    for idx, chunk in enumerate(chunks):
        chunk_sents = service.split_into_sentences(chunk["text"])
        if idx == 0:
            reconstructed_sentences.extend(chunk_sents)
        else:
            # Find overlap length between end of reconstructed and start of chunk_sents
            overlap_len = 0
            for match_len in range(min(len(reconstructed_sentences), len(chunk_sents)), 0, -1):
                if reconstructed_sentences[-match_len:] == chunk_sents[:match_len]:
                    overlap_len = match_len
                    break
            reconstructed_sentences.extend(chunk_sents[overlap_len:])
            
    # Get original sentences
    paragraphs = text.split("\n\n")
    original_sentences = []
    for para in paragraphs:
        original_sentences.extend(service.split_into_sentences(para))
        
    assert reconstructed_sentences == original_sentences

def test_chunking_formatting_and_order():
    service = ChunkingService()
    
    text = " ".join([f"This is sentence {i}." for i in range(50)])
    section = {
        "section_order": 3,
        "title": "Mock Formatting",
        "text": text
    }
    
    chunks = service.chunk_section(section)
    assert len(chunks) > 1
    
    # Check ID formats, order increments, and overlap tracking
    for idx, chunk in enumerate(chunks):
        order = idx + 1
        assert chunk["chunk_id"] == f"g1661-s03-c{order:04d}"
        assert chunk["section_order"] == 3
        assert chunk["section_title"] == "Mock Formatting"
        assert chunk["chunk_order"] == order
        assert chunk["token_count"] <= 220
        
        if order == 1:
            assert chunk["overlap_tokens"] == 0
        else:
            # Since there is overlap, overlap_tokens should represent the common tokens with previous chunk
            assert chunk["overlap_tokens"] > 0

def test_chunking_determinism():
    service = ChunkingService()
    
    text = " ".join([f"This is sentence {i}." for i in range(50)])
    section = {
        "section_order": 4,
        "title": "Mock Determinism",
        "text": text
    }
    
    chunks1 = service.chunk_section(section)
    chunks2 = service.chunk_section(section)
    
    assert chunks1 == chunks2

def test_chunking_empty_and_short_inputs():
    service = ChunkingService()
    
    # Empty input
    assert service.chunk_section({"section_order": 5, "title": "Empty", "text": ""}) == []
    assert service.chunk_section({"section_order": 5, "title": "Empty", "text": "   \n\n  "}) == []
    
    # Very short input (less than target size)
    section = {
        "section_order": 6,
        "title": "Short",
        "text": "Only one short sentence."
    }
    chunks = service.chunk_section(section)
    assert len(chunks) == 1
    assert chunks[0]["overlap_tokens"] == 0
    assert chunks[0]["token_count"] > 0
