import argparse
import json
import logging
import platform
import sys
from pathlib import Path
import numpy as np
import sentence_transformers

# Add the parent directory of backend/app to sys.path to run cleanly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import settings
from app.providers.minilm_provider import MiniLMProvider

def load_chunk(input_path: Path, chunk_id: str | None) -> dict:
    """
    Loads a specific chunk from chunks.jsonl by ID.
    If chunk_id is None, returns the first chunk.
    """
    with input_path.open("r", encoding="utf-8") as file:
        for line in file:
            chunk = json.loads(line)
            if chunk_id is None:
                return chunk
            if chunk["chunk_id"] == chunk_id:
                return chunk
    raise ValueError(f"Chunk not found: {chunk_id}")

def main():
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger = logging.getLogger("embed_sample_cli")

    parser = argparse.ArgumentParser(description="Generate sample embedding for a single chunk.")
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.PROCESSED_DATA_DIR / "chunks.jsonl",
        help="Path to the chunks.jsonl file."
    )
    parser.add_argument(
        "--chunk-id",
        type=str,
        default=None,
        help="Chunk ID to encode. Defaults to first chunk."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.DATA_DIR / "artifacts" / "embedding_sample.json",
        help="Path to save the output JSON."
    )

    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found at {args.input}")
        sys.exit(1)

    try:
        # 1. Load chunk
        logger.info(f"Loading chunk from {args.input}...")
        chunk = load_chunk(args.input, args.chunk_id)
        
        # 2. Validate essential fields
        required_fields = {
            "chunk_id",
            "section_order",
            "section_title",
            "chunk_order",
            "token_count",
            "text",
        }
        for field in required_fields:
            if field not in chunk:
                raise ValueError(f"Missing required field '{field}' in chunk.")

        if not chunk["chunk_id"] or not chunk["chunk_id"].strip():
            raise ValueError("chunk_id cannot be empty.")
            
        if not chunk["text"] or not chunk["text"].strip():
            raise ValueError("text cannot be empty.")
            
        if chunk["token_count"] <= 0:
            raise ValueError("token_count must be greater than 0.")

        print(f"Loading chunk:\n  ID: {chunk['chunk_id']}\n  Story: {chunk['section_title']}\n  Chunk order: {chunk['chunk_order']}\n  Token count: {chunk['token_count']}")

        # 3. Load provider
        print(f"\nLoading embedding model:\n  Model: {MiniLMProvider.MODEL_NAME}\n  Device: cpu")
        provider = MiniLMProvider(device="cpu")

        # 4. Re-calculate actual token count using model's tokenizer
        actual_token_count = provider.count_tokens(chunk["text"])
        
        if actual_token_count != chunk["token_count"]:
            raise ValueError(
                f"Stored token count {chunk['token_count']} does not match "
                f"MiniLM tokenizer count {actual_token_count}."
            )
            
        if actual_token_count > 220:
            raise ValueError(
                f"Chunk exceeds the 220-token project limit: {actual_token_count}."
            )
            
        if actual_token_count > provider.max_sequence_length:
            raise ValueError(
                f"Chunk exceeds model maximum sequence length: {provider.max_sequence_length}."
            )
            
        print(f"  Verified MiniLM tokens: {actual_token_count}\n  Maximum sequence length: {provider.max_sequence_length}")

        # 5. Generate embedding using provider
        embedding = provider.encode(chunk["text"])

        # 6. Metadata verification
        vector_norm = float(np.linalg.norm(embedding))
        finite_count = sum(1 for v in embedding if np.isfinite(v))

        print(f"\nEmbedding generated:\n  Dimensions: {provider.dimensions}\n  Data type: {embedding.dtype}\n  Vector norm: {vector_norm:.6f}\n  Finite values: {finite_count} / {provider.dimensions}")

        # Print first 10 values formatted
        print("\nFirst 10 values:")
        formatted_10 = ", ".join(f"{v:.6f}" for v in embedding[:10])
        print(f"  [{formatted_10}, ...]")

        # 7. Safe JSON payload assembly with environment versions
        payload = {
            "chunk_id": chunk["chunk_id"],
            "section_order": chunk["section_order"],
            "section_title": chunk["section_title"],
            "chunk_order": chunk["chunk_order"],
            "stored_token_count": chunk["token_count"],
            "verified_token_count": actual_token_count,
            "text_preview": chunk["text"][:100] + "..." if len(chunk["text"]) > 100 else chunk["text"],
            "model_name": provider.model_name,
            "model_max_sequence_length": provider.max_sequence_length,
            "device": "cpu",
            "dimensions": provider.dimensions,
            "dtype": str(embedding.dtype),
            "normalized": True,
            "vector_norm": round(vector_norm, 6),
            "sentence_transformers_version": sentence_transformers.__version__,
            "numpy_version": np.__version__,
            "python_version": platform.python_version(),
            "embedding": embedding.tolist()
        }

        # Ensure directory exists
        args.output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            
        print(f"\nOutput:\n  {args.output}\n")

    except Exception as e:
        logger.error(f"Failed to execute embed sample command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
