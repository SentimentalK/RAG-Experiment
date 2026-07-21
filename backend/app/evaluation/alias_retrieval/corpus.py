import hashlib
import json
from pathlib import Path
from typing import Any


def load_chunks_jsonl(path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def canonical_chunk_record(chunk: dict[str, Any], default_document_id: str = "gutenberg-1661") -> dict[str, Any]:
    return {
        "chunk_uid": chunk.get("chunk_uid") or chunk.get("chunk_id"),
        "document_id": chunk.get("document_id", default_document_id),
        "section_id": chunk.get("section_id"),
        "section_order": chunk.get("section_order"),
        "chunk_index": chunk.get("chunk_index", chunk.get("chunk_order")),
        "chunk_order": chunk.get("chunk_order"),
        "chunk_text": chunk.get("chunk_text", chunk.get("text", "")),
    }


def compute_corpus_content_sha256(chunks: list[dict[str, Any]], default_document_id: str = "gutenberg-1661") -> str:
    canonical = [canonical_chunk_record(chunk, default_document_id) for chunk in chunks]
    canonical.sort(key=lambda item: item["chunk_uid"])
    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

