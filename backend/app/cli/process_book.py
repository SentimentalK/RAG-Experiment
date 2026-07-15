import logging
import sys
from pathlib import Path

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.section_service import SectionService

def main():
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    logger = logging.getLogger("process_book_cli")
    logger.info("Starting processing script for Sherlock Holmes book...")
    
    try:
        service = SectionService()
        doc_metadata = service.process_book()
        
        logger.info("Processing completed successfully!")
        logger.info(f"Total Stories Processed: {doc_metadata['sections_count']}")
        logger.info(f"Total Characters: {doc_metadata['total_character_count']}")
        logger.info(f"Total Words: {doc_metadata['total_word_count']}")
        
        for idx, sec in enumerate(doc_metadata['sections'], 1):
            logger.info(f"  [{idx}] {sec['title']} ({sec['word_count']} words)")
            
    except Exception as e:
        logger.error(f"Failed to execute process book command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
