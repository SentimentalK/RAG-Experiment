FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry install --only main --no-root

COPY backend/ ./

# Copy deterministic dataset artifacts
COPY data/processed/document.json ./data/processed/document.json
COPY data/processed/sections.jsonl ./data/processed/sections.jsonl
COPY data/processed/chunks.jsonl ./data/processed/chunks.jsonl

COPY data/artifacts/minilm_embeddings.npy ./data/artifacts/minilm_embeddings.npy
COPY data/artifacts/minilm_embedding_index.jsonl ./data/artifacts/minilm_embedding_index.jsonl
COPY data/artifacts/embedding_report.json ./data/artifacts/embedding_report.json
COPY data/artifacts/content_ingestion_report.json ./data/artifacts/content_ingestion_report.json
COPY data/artifacts/embedding_ingestion_report.json ./data/artifacts/embedding_ingestion_report.json

# Copy frozen alias dataset used by the runtime AliasRegistry
COPY experiments/noun_units_v2a/candidates/review/sherlock_entity_alias_groups_final.json ./experiments/noun_units_v2a/candidates/review/sherlock_entity_alias_groups_final.json


EXPOSE 8000

CMD [ \
  "uvicorn", \
  "app.api.main:app", \
  "--host", "0.0.0.0", \
  "--port", "8000", \
  "--workers", "1" \
]
