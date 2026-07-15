import os
import httpx
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class GutenbergProvider:
    """
    Provider for downloading and loading books from Project Gutenberg.
    """
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        # Using standard headers to mimic a browser, preventing potential blocking from Gutenberg CDN
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def download_book(self, url: str, output_path: Path) -> Path:
        """
        Downloads a book from the specified Gutenberg URL and saves it to output_path.
        If the download fails, raises an exception.
        """
        logger.info(f"Downloading book from {url} to {output_path}...")
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                    
            logger.info(f"Successfully downloaded book and saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to download book from {url}: {e}")
            raise

    def load_local(self, file_path: Path) -> str:
        """
        Loads the content of a locally saved book HTML file.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Local book file not found at {file_path}")
            
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
