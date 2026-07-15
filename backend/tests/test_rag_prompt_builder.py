from app.services.rag_prompt_builder import RagPromptBuilder

def test_render_chunk_escaping():
    # Test text containing HTML/XML entities
    chunk = {
        "rank": 1,
        "chunk_uid": "c-1-1",
        "section_title": 'A "Great" Story & Mystery',
        "cosine_similarity": 0.876543,
        "chunk_text": "Holmes said: <element> & others & \"quotes\""
    }
    
    rendered = RagPromptBuilder.render_chunk(chunk)
    
    # Assert tag properties are properly quoted with quoteattr (escapes internal double quotes)
    assert 'rank="1"' in rendered
    assert 'chunk_uid="c-1-1"' in rendered
    assert "section_title='A \"Great\" Story &amp; Mystery'" in rendered
    assert 'cosine_similarity="0.876543"' in rendered
    
    # Assert text content is properly escaped using escape
    assert "Holmes said: &lt;element&gt; &amp; others &amp; \"quotes\"" in rendered
    assert "</retrieved_chunk>" in rendered

def test_build_messages():
    chunks = [
        {
            "rank": 1,
            "chunk_uid": "c-1-1",
            "section_title": "Title 1",
            "cosine_similarity": 0.95,
            "chunk_text": "This is chunk 1."
        },
        {
            "rank": 2,
            "chunk_uid": "c-1-2",
            "section_title": "Title 2",
            "cosine_similarity": 0.91,
            "chunk_text": "This is chunk 2."
        }
    ]
    
    question = "Who is Holmes?"
    messages = RagPromptBuilder.build_messages(question, chunks)
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    
    system_prompt = messages[0]["content"]
    assert "retrieval-augmented question-answering assistant" in system_prompt
    assert "Do not use outside knowledge" in system_prompt
    
    user_prompt = messages[1]["content"]
    assert "Question:\nWho is Holmes?" in user_prompt
    assert 'chunk_uid="c-1-1"' in user_prompt
    assert 'chunk_uid="c-1-2"' in user_prompt
    assert "This is chunk 1." in user_prompt
    assert "This is chunk 2." in user_prompt
