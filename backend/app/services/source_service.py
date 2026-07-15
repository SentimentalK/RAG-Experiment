import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.core.config import settings
from app.providers.gutenberg_provider import GutenbergProvider

logger = logging.getLogger(__name__)

class SourceService:
    """
    Service responsible for managing raw source documents, downloading them,
    and storing their metadata.
    """
    def __init__(self, provider: GutenbergProvider = None):
        self.provider = provider or GutenbergProvider()

    def download_and_save(self, force: bool = False) -> Dict[str, Any]:
        """
        Downloads the Sherlock Holmes book from Gutenberg if it doesn't already exist locally.
        Saves metadata to source_metadata.json.
        """
        raw_html_path = settings.raw_html_path
        metadata_path = settings.metadata_path
        
        # Check if already downloaded and not forcing re-download
        if not force and raw_html_path.exists() and metadata_path.exists():
            logger.info("Sherlock Holmes book already downloaded. Loading local metadata...")
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # Ensure directory exists
        settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Download HTML file
        self.provider.download_book(settings.SHERLOCK_URL, raw_html_path)

        # Create metadata
        metadata = {
            "source": "Project Gutenberg",
            "ebook_id": 1661,
            "title": "The Adventures of Sherlock Holmes",
            "author": "Arthur Conan Doyle",
            "format": "html",
            "url": settings.SHERLOCK_URL,
            "downloaded_at": datetime.utcnow().isoformat() + "Z"
        }

        # Write metadata
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info("Metadata saved successfully.")
        return metadata

    def get_raw_content(self) -> str:
        """
        Returns the raw HTML content of the downloaded book.
        """
        raw_html_path = settings.raw_html_path
        if not raw_html_path.exists():
            # Auto-download if not exists
            self.download_and_save()
            
        return self.provider.load_local(raw_html_path)
