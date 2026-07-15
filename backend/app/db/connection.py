from contextlib import contextmanager
from collections.abc import Iterator
import psycopg
from psycopg import Connection
from pgvector.psycopg import register_vector
from app.core.config import settings

@contextmanager
def get_connection() -> Iterator[Connection]:
    """
    Context manager to yield a psycopg database connection with pgvector support registered.
    Transaction lifecycle (commit/rollback) is controlled by the caller.
    """
    connection = psycopg.connect(settings.DATABASE_URL)
    register_vector(connection)
    try:
        yield connection
    finally:
        connection.close()
