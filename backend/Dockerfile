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

EXPOSE 8000

CMD [ \
  "uvicorn", \
  "app.api.main:app", \
  "--host", "0.0.0.0", \
  "--port", "8000", \
  "--workers", "1" \
]
