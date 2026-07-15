import argparse
import sys
import logging
from app.core.config import settings
from app.providers.minilm_provider import MiniLMProvider
from app.services.vector_search_service import VectorSearchService
from app.clients.groq_gpt_oss_client import GroqGptOssClient, GroqApiError
from app.services.rag_answer_service import RagAnswerService, InvalidRagResponseError

def main():
    parser = argparse.ArgumentParser(description="Run RAG pipeline to answer a question using retrieved chunks.")
    parser.add_argument(
        "question",
        type=str,
        help="The question to ask RAG assistant."
    )
    args = parser.parse_args()

    # Configure basic logging level
    logging.basicConfig(level=logging.WARNING)

    # Initialize dependencies
    try:
        # Load MiniLM model
        provider = MiniLMProvider()
        search_service = VectorSearchService(provider)
        
        # Groq client & RAG Service
        groq_client = GroqGptOssClient(settings)
        rag_service = RagAnswerService(search_service, groq_client)
    except Exception as e:
        print(f"Error during initialization: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        # Run service
        response = rag_service.generate_answer(args.question)
    except GroqApiError as e:
        print(f"Groq API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except InvalidRagResponseError as e:
        print(f"Invalid RAG Response Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        groq_client.close()

    # Print clean formatted console output
    ret = response.retrieval
    gen = response.generation

    print("\nQuestion:")
    print(f"  {response.question}")

    print("\nRetrieval:")
    print(f"  Top K: {ret.top_k}")
    print(f"  Embedding: {ret.embedding_duration_ms:.1f} ms")
    print(f"  Database: {ret.database_duration_ms:.1f} ms")

    print("\nGeneration:")
    print(f"  Model: {gen.model_name}")
    print(f"  Duration: {gen.generation_duration_ms:.1f} ms")
    print(f"  Evidence sufficient: {'yes' if gen.evidence_sufficient else 'no'}")
    print(f"  Confidence: {gen.confidence:.2f}")
    print(f"  Attempt Count: {gen.attempt_count}")
    
    if gen.usage:
        usage = gen.usage
        print(f"  Token Usage: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")
    else:
        print("  Token Usage: N/A")

    print("\nAnswer:")
    print(f"  {gen.answer}")

    print("\nCitations:")
    if gen.citations:
        for citation in gen.citations:
            print(f"  - {citation.chunk_uid}: {citation.reason}")
    else:
        print("  (None)")
    print()

if __name__ == "__main__":
    main()
