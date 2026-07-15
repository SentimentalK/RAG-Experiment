import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class CleaningService:
    """
    Service responsible for cleaning the raw Gutenberg HTML content.
    It removes headers, footers, licensing text, and converts HTML to clean structured text.
    """
    
    def __init__(self):
        self.start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
        self.end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"

    def clean_html(self, raw_html: str) -> str:
        """
        Cleans raw Gutenberg HTML by isolating the content between the start and end markers.
        Returns the sliced HTML string.
        """
        logger.info("Cleaning raw HTML content...")
        
        # Locate the start and end markers in the raw string
        start_idx = raw_html.find(self.start_marker)
        if start_idx == -1:
            logger.warning("Start marker not found. Parsing entire HTML.")
            start_idx = 0
        else:
            # Move index past the line containing the start marker
            start_line_end = raw_html.find("\n", start_idx)
            if start_line_end != -1:
                start_idx = start_line_end + 1

        end_idx = raw_html.find(self.end_marker)
        if end_idx == -1:
            logger.warning("End marker not found. Parsing to end of file.")
            end_idx = len(raw_html)
        else:
            # We want to stop before the div/element containing the end marker
            # Let's find the start of the line or element containing the end marker
            end_line_start = raw_html.rfind("<", 0, end_idx)
            if end_line_start != -1 and end_line_start > start_idx:
                end_idx = end_line_start

        cleaned_html = raw_html[start_idx:end_idx].strip()
        logger.info(f"HTML cleaned. Reduced size from {len(raw_html)} to {len(cleaned_html)} characters.")
        return cleaned_html

    def clean_text(self, text: str) -> str:
        """
        Performs general text normalization:
        - Strips leading and trailing spaces on every line
        - Normalizes inline whitespace (multiple spaces/tabs to a single space)
        - Normalizes multiple newlines to double newlines (standard paragraph breaks)
        """
        if not text:
            return ""
            
        # Split by lines, strip each line
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(lines)
        
        # Replace multiple spaces/tabs within a line with a single space
        text = re.sub(r"[ \t]+", " ", text)
        
        # Replace 3 or more consecutive newlines with exactly 2 newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        return text.strip()
