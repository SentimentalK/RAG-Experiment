import logging
import sys
from pathlib import Path

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.source_service import SourceService

def main():
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    logger = logging.getLogger("download_book_cli")
    logger.info("Starting download script for Sherlock Holmes...")
    
    try:
        service = SourceService()
        metadata = service.download_and_save(force=True)
        
        logger.info("Download completed successfully!")
        logger.info(f"Metadata: {metadata}")
    except Exception as e:
        logger.error(f"Failed to execute download command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
