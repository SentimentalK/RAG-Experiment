import pytest
from app.services.cleaning_service import CleaningService

def test_clean_html_with_markers():
    service = CleaningService()
    raw_html = (
        "Some Gutenberg Header\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK THE ADVENTURES OF SHERLOCK HOLMES ***\n"
        "<div>Actual Content</div>\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK THE ADVENTURES OF SHERLOCK HOLMES ***\n"
        "Some Gutenberg License Footer"
    )
    
    cleaned = service.clean_html(raw_html)
    assert "Actual Content" in cleaned
    assert "Gutenberg Header" not in cleaned
    assert "Gutenberg License Footer" not in cleaned

def test_clean_html_missing_markers():
    service = CleaningService()
    raw_html = "<div>No markers here</div>"
    cleaned = service.clean_html(raw_html)
    assert cleaned == "<div>No markers here</div>"

def test_clean_text_whitespace():
    service = CleaningService()
    text = "  Some   text \t with  multiple \n\n\n newlines  "
    cleaned = service.clean_text(text)
    assert cleaned == "Some text with multiple\n\nnewlines"
