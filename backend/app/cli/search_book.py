import argparse
import json
import logging
import sys
from pathlib import Path

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.providers.minilm_provider import MiniLMProvider
from app.services.vector_search_service import VectorSearchService

logger = logging.getLogger("search_book_cli")

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="Query the RAG database using exact cosine similarity search.")
    parser.add_argument(
        "question",
        type=str,
        help="The query question string."
    )
    parser.add_argument(
        "--document-id",
        type=str,
        default="gutenberg-1661",
        help="Target document ID."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of top matching chunks to retrieve (1-50)."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "vector_search_sample.json",
        help="Path to output the vector search result JSON."
    )

    args = parser.parse_args()

    try:
        # 1. Initialize provider and service
        provider = MiniLMProvider(device="cpu")
        service = VectorSearchService(provider)

        # 2. Run search
        res = service.search(args.question, args.document_id, args.top_k)

        # Calculate a preview of the query embedding to print (first 10 values)
        query_embedding = provider.encode(args.question)
        preview_vals = [round(float(v), 6) for v in query_embedding[:10]]

        # 3. Format console output
        print(f"Question:")
        print(f"  {res['question']}")
        print()
        print(f"Query encoding:")
        print(f"  Model: {res['model_name']}")
        print(f"  Tokens: {res['query_token_count']}")
        print(f"  Dimensions: {res['query_dimensions']}")
        print(f"  Norm: {res['query_vector_norm']:.6f}")
        print(f"  First 10 values: {preview_vals}")
        print(f"  Encoding time: {res['embedding_duration_ms']:.2f} ms")
        print()
        print(f"Database:")
        print(f"  Document: {res['document_id']}")
        print(f"  Search mode: {res['search_mode']}")
        print(f"  Available chunks: {res['available_chunk_count']}")
        print(f"  Available embeddings: {res['available_embedding_count']}")
        print(f"  Database time: {res['database_duration_ms']:.2f} ms")
        print(f"  Results: {len(res['results'])}")
        print()

        for idx, item in enumerate(res["results"], start=1):
            print(f"Rank {item['rank']}")
            print(f"Similarity: {item['cosine_similarity']:.6f}")
            print(f"Distance: {item['cosine_distance']:.6f}")
            print(f"Story: {item['section_title']}")
            print(f"Chunk: {item['chunk_uid']}")
            print(f"Chunk order: {item['chunk_order']}")
            print(f"Tokens: {item['token_count']}")
            print()
            print(item["chunk_text"])
            print("-" * 50)
            print()

        # 4. Save atomic JSON output if output path is requested
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temp_output_path = args.output.with_suffix(args.output.suffix + ".tmp")
            try:
                with temp_output_path.open("w", encoding="utf-8") as f:
                    json.dump(res, f, indent=2, ensure_ascii=False)
                temp_output_path.replace(args.output)
                print(f"Search results saved to {args.output}\n")
            finally:
                temp_output_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Failed to execute vector search command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
