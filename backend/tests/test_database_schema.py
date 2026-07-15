import pytest
import psycopg
import numpy as np
from pgvector import Vector
from pgvector.psycopg import register_vector
from app.core.config import settings

@pytest.fixture
def connection():
    """
    Fixture that establishes a psycopg connection to the Postgres database,
    registers the vector extension type handler, yields the connection,
    and rolls back any changes to ensure the database remains empty.
    """
    conn = psycopg.connect(settings.DATABASE_URL)
    register_vector(conn)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()

@pytest.fixture
def test_chunk_id(connection) -> int:
    """
    Fixture to insert a test document, section, and chunk within the transaction.
    Returns the chunk_id generated for subsequent embedding tests.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO documents (document_id, title, author, source_name)
            VALUES ('pytest-test-doc', 'Pytest Doc', 'Pytest Author', 'Local')
            RETURNING document_id;
            """
        )
        doc_id = cursor.fetchone()[0]
        
        cursor.execute(
            """
            INSERT INTO sections (document_id, section_order, title, section_text)
            VALUES (%s, 1, 'Pytest Section', 'Pytest section text.')
            RETURNING section_id;
            """,
            (doc_id,)
        )
        sec_id = cursor.fetchone()[0]
        
        cursor.execute(
            """
            INSERT INTO chunks (chunk_uid, section_id, chunk_order, token_count, overlap_tokens, chunk_text)
            VALUES ('pytest-test-chunk-uid', %s, 1, 10, 0, 'Pytest chunk text.')
            RETURNING chunk_id;
            """,
            (sec_id,)
        )
        chunk_id = cursor.fetchone()[0]
        return chunk_id

def test_pgvector_extension_exists(connection):
    """
    Verifies that the 'vector' extension is loaded in the PostgreSQL instance.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_extension
                WHERE extname = 'vector'
            );
            """
        )
        assert cursor.fetchone()[0] is True

def test_base_tables_exist(connection):
    """
    Verifies that all 4 required schema tables exist in the database.
    """
    expected_tables = {"documents", "sections", "chunks", "minilm_embeddings"}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public';
            """
        )
        existing_tables = {row[0] for row in cursor.fetchall()}
        assert expected_tables.issubset(existing_tables)

def test_embedding_dimensions_and_insert(connection, test_chunk_id):
    """
    Verifies that a valid 384-dimensional unit vector can be successfully inserted
    into minilm_embeddings and retrieved with the correct dimensions and norm.
    """
    embedding_vector = Vector(
        np.concatenate([
            np.array([1.0], dtype=np.float32),
            np.zeros(383, dtype=np.float32)
        ])
    )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO minilm_embeddings (chunk_id, model_name, dimensions, normalized, embedding)
            VALUES (%s, 'test-model', 384, TRUE, %s);
            """,
            (test_chunk_id, embedding_vector)
        )
        
        cursor.execute(
            """
            SELECT vector_dims(embedding), vector_norm(embedding)
            FROM minilm_embeddings
            WHERE chunk_id = %s;
            """,
            (test_chunk_id,)
        )
        dims, norm = cursor.fetchone()
        assert dims == 384
        assert np.isclose(norm, 1.0, atol=1e-5)

def test_wrong_vector_dimension_is_rejected(connection, test_chunk_id):
    """
    Verifies that trying to insert a vector of incorrect dimension (e.g. 383-dim)
    is rejected by PostgreSQL. Uses a savepoint (connection.transaction()) to keep
    the main transaction state alive.
    """
    wrong_vector = Vector(np.zeros(383, dtype=np.float32))

    with pytest.raises(psycopg.Error):
        with connection.transaction():
            connection.execute(
                """
                INSERT INTO minilm_embeddings (chunk_id, model_name, dimensions, normalized, embedding)
                VALUES (%s, 'wrong-dim-model', 384, FALSE, %s);
                """,
                (test_chunk_id, wrong_vector)
            )

def test_overlong_chunk_token_count_is_rejected(connection):
    """
    Verifies that inserting a chunk with a token_count exceeding 220 is rejected
    by the CHECK constraint on the chunks table.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO documents (document_id, title, author, source_name)
            VALUES ('pytest-token-doc', 'Pytest Doc', 'Pytest Author', 'Local')
            RETURNING document_id;
            """
        )
        doc_id = cursor.fetchone()[0]
        
        cursor.execute(
            """
            INSERT INTO sections (document_id, section_order, title, section_text)
            VALUES (%s, 1, 'Pytest Section', 'Pytest section text.')
            RETURNING section_id;
            """,
            (doc_id,)
        )
        sec_id = cursor.fetchone()[0]

    # Attempt to insert chunk with token_count = 221
    with pytest.raises(psycopg.Error):
        with connection.transaction():
            connection.execute(
                """
                INSERT INTO chunks (chunk_uid, section_id, chunk_order, token_count, overlap_tokens, chunk_text)
                VALUES ('pytest-overlong-chunk', %s, 1, 221, 0, 'Test chunk text.')
                """,
                (sec_id,)
            )

def test_cascade_delete_works(connection, test_chunk_id):
    """
    Verifies that deleting a document cascades down to clear out all sections,
    chunks, and embeddings referencing it.
    """
    # Insert embedding to establish complete chain
    embedding_vector = Vector(
        np.concatenate([
            np.array([1.0], dtype=np.float32),
            np.zeros(383, dtype=np.float32)
        ])
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO minilm_embeddings (chunk_id, model_name, dimensions, normalized, embedding)
            VALUES (%s, 'test-model', 384, TRUE, %s);
            """,
            (test_chunk_id, embedding_vector)
        )
        
        # Verify rows exist
        cursor.execute("SELECT COUNT(*) FROM documents WHERE document_id = 'pytest-test-doc';")
        assert cursor.fetchone()[0] == 1
        
        cursor.execute("SELECT COUNT(*) FROM minilm_embeddings WHERE chunk_id = %s;", (test_chunk_id,))
        assert cursor.fetchone()[0] == 1

        # Delete document
        cursor.execute("DELETE FROM documents WHERE document_id = 'pytest-test-doc';")

        # Verify cascades
        cursor.execute("SELECT COUNT(*) FROM documents WHERE document_id = 'pytest-test-doc';")
        assert cursor.fetchone()[0] == 0
        
        cursor.execute("SELECT COUNT(*) FROM sections WHERE document_id = 'pytest-test-doc';")
        assert cursor.fetchone()[0] == 0
        
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE chunk_uid = 'pytest-test-chunk-uid';")
        assert cursor.fetchone()[0] == 0
        
        cursor.execute("SELECT COUNT(*) FROM minilm_embeddings WHERE chunk_id = %s;", (test_chunk_id,))
        assert cursor.fetchone()[0] == 0
