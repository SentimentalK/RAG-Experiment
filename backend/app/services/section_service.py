import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from bs4 import BeautifulSoup

from app.core.config import settings
from app.services.source_service import SourceService
from app.services.cleaning_service import CleaningService

logger = logging.getLogger(__name__)

class SectionService:
    """
    Service responsible for parsing the cleaned HTML book content,
    extracting individual stories (sections), and saving them.
    """
    
    def __init__(self, source_service: SourceService = None, cleaning_service: CleaningService = None):
        self.source_service = source_service or SourceService()
        self.cleaning_service = cleaning_service or CleaningService()

    def _to_title_case(self, title_str: str) -> str:
        """
        Converts all-caps chapter titles to readable Title Case, following standard rules.
        Also strips Roman numerals prefix (e.g. 'I. A SCANDAL IN BOHEMIA' -> 'A Scandal in Bohemia').
        """
        # Clean whitespaces and newlines first
        cleaned = title_str.strip().replace('\n', ' ').replace('\r', '')
        # Remove Roman numeral prefixes like "I. ", "XII. ", "IX. ", etc.
        cleaned = re.sub(r'^[IVXLCDM]+\.?\s*', '', cleaned, flags=re.IGNORECASE).strip()
        
        words = cleaned.lower().split()
        if not words:
            return ""
            
        # Standard lowercase words in English titles
        lowercase_words = {
            "a", "an", "the", "and", "but", "or", "for", "nor", "on", "in", 
            "at", "to", "by", "of", "with", "for", "about", "against", "between",
            "into", "through", "during", "before", "after", "above", "below", "to", 
            "from", "up", "down", "off", "over", "under"
        }
        
        result_words = []
        for i, word in enumerate(words):
            # Always capitalize first and last word of the title
            if i == 0 or i == len(words) - 1:
                parts = word.split('-')
                result_words.append('-'.join(p.capitalize() for p in parts))
            else:
                # Remove symbols for checking matching
                clean_w = re.sub(r'[^a-z]', '', word)
                if clean_w in lowercase_words:
                    result_words.append(word)
                else:
                    parts = word.split('-')
                    result_words.append('-'.join(p.capitalize() for p in parts))
                    
        final_title = ' '.join(result_words)
        # Clean smart apostrophes / quotes
        final_title = final_title.replace("’", "'").replace("‘", "'")
        return final_title

    def process_book(self) -> Dict[str, Any]:
        """
        Extracts sections from the downloaded HTML file, processes them,
        saves metadata and sections to files, and returns execution summary.
        """
        # Ensure directories exist
        settings.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load raw HTML content
        raw_html = self.source_service.get_raw_content()
        
        # Slice raw HTML to get clean book content
        cleaned_html = self.cleaning_service.clean_html(raw_html)
        
        # Parse using BeautifulSoup
        soup = BeautifulSoup(cleaned_html, "html.parser")
        
        # Find all chapters
        chapter_divs = soup.find_all("div", class_="chapter")
        
        if not chapter_divs:
            logger.error("No chapter divs found in the cleaned HTML!")
            raise ValueError("No chapters found in the document. HTML structure might have changed.")
            
        logger.info(f"Found {len(chapter_divs)} stories in the document.")
        
        sections: List[Dict[str, Any]] = []
        
        for idx, div in enumerate(chapter_divs, 1):
            # Find the title (h2 tag)
            h2_tag = div.find("h2")
            if not h2_tag:
                logger.warning(f"Chapter {idx} does not have an h2 tag. Skipping.")
                continue
                
            raw_title = h2_tag.get_text(separator=" ")
            title = self._to_title_case(raw_title)
            
            # Decompose (remove) the h2 tag from copy so it doesn't appear in body text
            div_copy = BeautifulSoup(str(div), "html.parser")
            h2_to_remove = div_copy.find("h2")
            if h2_to_remove:
                h2_to_remove.decompose()
                
            # Extract narrative text (all p and h3 tags)
            paragraphs = div_copy.find_all(["p", "h3"])
            story_parts = []
            
            for p in paragraphs:
                p_text = p.get_text()
                cleaned_p = self.cleaning_service.clean_text(p_text)
                if cleaned_p:
                    story_parts.append(cleaned_p)
                    
            story_text = "\n\n".join(story_parts)
            
            sections.append({
                "section_order": idx,
                "title": title,
                "text": story_text,
                "character_count": len(story_text),
                "word_count": len(story_text.split())
            })
            
            logger.info(f"Processed story {idx}: '{title}' ({len(story_text)} chars)")

        # Save sections to JSONL
        sections_jsonl_path = settings.PROCESSED_DATA_DIR / "sections.jsonl"
        with open(sections_jsonl_path, "w", encoding="utf-8") as f:
            for sec in sections:
                f.write(json.dumps(sec, ensure_ascii=False) + "\n")
                
        # Save overall document metadata to document.json
        doc_metadata = {
            "title": "The Adventures of Sherlock Holmes",
            "author": "Arthur Conan Doyle",
            "sections_count": len(sections),
            "total_character_count": sum(s["character_count"] for s in sections),
            "total_word_count": sum(s["word_count"] for s in sections),
            "processed_at": self.source_service.download_and_save()["downloaded_at"],
            "sections": [
                {
                    "section_order": s["section_order"],
                    "title": s["title"],
                    "character_count": s["character_count"],
                    "word_count": s["word_count"]
                }
                for s in sections
            ]
        }
        
        document_json_path = settings.PROCESSED_DATA_DIR / "document.json"
        with open(document_json_path, "w", encoding="utf-8") as f:
            json.dump(doc_metadata, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Saved document metadata to {document_json_path}")
        logger.info(f"Saved sections to {sections_jsonl_path}")
        
        return doc_metadata
