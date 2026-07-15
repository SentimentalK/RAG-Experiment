import pytest
from app.services.section_service import SectionService

def test_title_case_formatting():
    service = SectionService()
    
    assert service._to_title_case("I. A SCANDAL IN BOHEMIA") == "A Scandal in Bohemia"
    assert service._to_title_case("II. THE RED-HEADED LEAGUE") == "The Red-Headed League"
    assert service._to_title_case("IX. THE ADVENTURE OF THE ENGINEER’S THUMB") == "The Adventure of the Engineer's Thumb"
    assert service._to_title_case("XII. THE ADVENTURE OF THE COPPER BEECHES") == "The Adventure of the Copper Beeches"
    assert service._to_title_case("THE MAN WITH THE TWISTED LIP") == "The Man with the Twisted Lip"

def test_process_mock_book(tmp_path, monkeypatch):
    # Setup test configuration directories using monkeypatch
    from app.core import config
    
    # Create mock HTML data
    mock_html = """
    *** START OF THE PROJECT GUTENBERG EBOOK THE ADVENTURES OF SHERLOCK HOLMES ***
    <div class="chapter">
        <h2>I.<br>A SCANDAL IN BOHEMIA</h2>
        <p>To Sherlock Holmes she is always the woman.</p>
        <h3>I.</h3>
        <p>I had seen little of Holmes lately.</p>
    </div>
    <div class="chapter">
        <h2>II.<br>THE RED-HEADED LEAGUE</h2>
        <p>I had called upon my friend, Mr. Sherlock Holmes...</p>
    </div>
    *** END OF THE PROJECT GUTENBERG EBOOK THE ADVENTURES OF SHERLOCK HOLMES ***
    """
    
    # Mock settings directories
    monkeypatch.setattr(config.settings, "RAW_DATA_DIR", tmp_path / "raw")
    monkeypatch.setattr(config.settings, "PROCESSED_DATA_DIR", tmp_path / "processed")
    
    # Save mock raw HTML file
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with open(raw_dir / config.settings.SHERLOCK_RAW_HTML_FILENAME, "w", encoding="utf-8") as f:
        f.write(mock_html)
        
    # Also write a dummy source_metadata.json
    import json
    with open(raw_dir / config.settings.SHERLOCK_METADATA_FILENAME, "w", encoding="utf-8") as f:
        json.dump({"downloaded_at": "2026-07-15T02:00:00Z"}, f)
        
    service = SectionService()
    doc_metadata = service.process_book()
    
    # Verify metadata
    assert doc_metadata["sections_count"] == 2
    assert doc_metadata["sections"][0]["title"] == "A Scandal in Bohemia"
    assert doc_metadata["sections"][1]["title"] == "The Red-Headed League"
    
    # Verify created files
    processed_dir = tmp_path / "processed"
    assert (processed_dir / "document.json").exists()
    assert (processed_dir / "sections.jsonl").exists()
    
    # Check content of sections.jsonl
    with open(processed_dir / "sections.jsonl", "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 2
        sec1 = json.loads(lines[0])
        assert sec1["section_order"] == 1
        assert sec1["title"] == "A Scandal in Bohemia"
        # The h3 tag text "I." and paragraph text should both be present, joined by double newlines
        assert "To Sherlock Holmes she is always the woman.\n\nI.\n\nI had seen little of Holmes lately." in sec1["text"]
