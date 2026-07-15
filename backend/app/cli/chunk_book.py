import json
import logging
import sys
from pathlib import Path

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.services.chunking_service import ChunkingService

def main():
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    logger = logging.getLogger("chunk_book_cli")
    logger.info("Starting chunking script for Sherlock Holmes book...")
    
    sections_jsonl_path = settings.PROCESSED_DATA_DIR / "sections.jsonl"
    if not sections_jsonl_path.exists():
        logger.error(f"Processed sections file not found at {sections_jsonl_path}. Run process_book first.")
        sys.exit(1)
        
    try:
        # Load sections
        sections = []
        with open(sections_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    sections.append(json.loads(line))
                    
        logger.info(f"Loaded {len(sections)} sections from {sections_jsonl_path}")
        
        # Run chunking service
        service = ChunkingService()
        chunks = service.chunk_document(sections)
        
        # Calculate stats
        chunk_count = len(chunks)
        token_counts = [c["token_count"] for c in chunks]
        
        min_tokens = min(token_counts) if chunks else 0
        max_tokens = max(token_counts) if chunks else 0
        avg_tokens = sum(token_counts) / chunk_count if chunks else 0
        
        empty_chunks = sum(1 for c in chunks if not c["text"].strip())
        chunks_over_limit = sum(1 for c in chunks if c["token_count"] > service.MAX_TOKENS)
        
        # Chunks per section
        chunks_per_section = []
        for sec in sections:
            sec_order = sec["section_order"]
            sec_chunks = sum(1 for c in chunks if c["section_order"] == sec_order)
            chunks_per_section.append({
                "section_order": sec_order,
                "title": sec["title"],
                "chunk_count": sec_chunks
            })
            
        # Write chunks.jsonl
        chunks_jsonl_path = settings.PROCESSED_DATA_DIR / "chunks.jsonl"
        with open(chunks_jsonl_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                
        # Write report
        report = {
            "section_count": len(sections),
            "chunk_count": chunk_count,
            "minimum_tokens": min_tokens,
            "maximum_tokens": max_tokens,
            "average_tokens": round(avg_tokens, 1),
            "empty_chunks": empty_chunks,
            "chunks_over_limit": chunks_over_limit,
            "chunks_per_section": chunks_per_section
        }
        
        report_path = settings.PROCESSED_DATA_DIR / "chunking_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        # Print expected output
        print(f"\nLoaded sections: {len(sections)}")
        print(f"Generated chunks: {chunk_count}")
        print(f"Minimum tokens: {min_tokens}")
        print(f"Maximum tokens: {max_tokens}")
        print(f"Average tokens: {round(avg_tokens, 1)}")
        print(f"Chunks over limit: {chunks_over_limit}")
        print(f"Empty chunks: {empty_chunks}")
        print(f"\nOutput:\n{chunks_jsonl_path}\n{report_path}\n")
        
    except Exception as e:
        logger.error(f"Failed to execute chunk book command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
