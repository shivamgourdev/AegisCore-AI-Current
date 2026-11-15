"""AEGISCORE_PART4D_GENERATED
Persistent normalized vectors and cosine-similarity search using SQLite.
"""
import json
import math
import sqlite3
from typing import Any

from aegiscore.document_service import _database_connection


def _ensure_vector_table(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS document_chunk_embeddings (
            chunk_id TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            embedding_json TEXT NOT NULL,
            FOREIGN KEY(chunk_id) REFERENCES document_chunks(chunk_id)
        )
    """)


def store_chunk_embeddings(
    document_id: str,
    embedded_chunks: list[dict[str, Any]],
    model_name: str,
) -> int:
    """Atomically replace a document's saved vectors after validating them."""
    prepared = []
    expected_dimension = None

    for item in embedded_chunks:
        vector = item.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ValueError("Every chunk must have a non-empty embedding.")
        vector = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Embedding contains a non-finite value.")

        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isclose(norm, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError("Only L2-normalized embeddings may be persisted.")

        if expected_dimension is None:
            expected_dimension = len(vector)
        elif len(vector) != expected_dimension:
            raise ValueError("Embedding dimensions are inconsistent.")

        prepared.append((
            item["chunk_id"], model_name, len(vector),
            json.dumps(vector, separators=(",", ":")),
        ))

    connection = _database_connection()
    try:
        _ensure_vector_table(connection)
        connection.execute("BEGIN")

        document = connection.execute(
            "SELECT document_id FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        if document is None:
            raise ValueError("Document does not exist.")

        chunk_rows = connection.execute(
            "SELECT chunk_id FROM document_chunks WHERE document_id = ?",
            (document_id,),
        ).fetchall()
        valid_ids = {row["chunk_id"] for row in chunk_rows}
        if any(item[0] not in valid_ids for item in prepared):
            raise ValueError("Embedding references a chunk outside this document.")

        connection.execute("""
            DELETE FROM document_chunk_embeddings
            WHERE chunk_id IN (
                SELECT chunk_id FROM document_chunks WHERE document_id = ?
            )
        """, (document_id,))

        connection.executemany("""
            INSERT INTO document_chunk_embeddings
                (chunk_id, model_name, dimension, embedding_json)
            VALUES (?, ?, ?, ?)
        """, prepared)

        connection.commit()
        return len(prepared)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_document_embeddings(document_id: str):
    """Return vector metadata, not the full numerical vectors."""
    connection = _database_connection()
    try:
        _ensure_vector_table(connection)
        document = connection.execute(
            "SELECT document_id FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        if document is None:
            return None

        rows = connection.execute("""
            SELECT c.chunk_id, c.filename, c.page_number, c.chunk_index,
                   e.model_name, e.dimension, e.embedding_json
            FROM document_chunks c
            JOIN document_chunk_embeddings e ON e.chunk_id = c.chunk_id
            WHERE c.document_id = ?
            ORDER BY c.page_number, c.chunk_index
        """, (document_id,)).fetchall()

        result = []
        for row in rows:
            vector = json.loads(row["embedding_json"])
            norm = math.sqrt(sum(value * value for value in vector))
            result.append({
                "chunk_id": row["chunk_id"],
                "filename": row["filename"],
                "page_number": row["page_number"],
                "chunk_index": row["chunk_index"],
                "model": row["model_name"],
                "dimension": row["dimension"],
                "vector_norm": norm,
            })
        return result
    finally:
        connection.close()


def search_similar_chunks(
    query_vector: list[float],
    top_k: int = 5,
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    """Rank persisted chunks by cosine similarity; vectors are normalized."""
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 50:
        raise ValueError("top_k must be an integer between 1 and 50.")

    query = [float(value) for value in query_vector]
    if not query or not all(math.isfinite(value) for value in query):
        raise ValueError("Query vector is empty or invalid.")

    norm = math.sqrt(sum(value * value for value in query))
    if norm == 0:
        raise ValueError("Query vector must not be zero.")
    query = [value / norm for value in query]

    connection = _database_connection()
    try:
        _ensure_vector_table(connection)
        if model_name:
            rows = connection.execute("""
                SELECT c.chunk_id, c.document_id, c.filename, c.page_number,
                       c.chunk_index, c.text, e.model_name, e.dimension,
                       e.embedding_json
                FROM document_chunks c
                JOIN document_chunk_embeddings e ON e.chunk_id = c.chunk_id
                WHERE e.model_name = ? AND e.dimension = ?
            """, (model_name, len(query))).fetchall()
        else:
            rows = connection.execute("""
                SELECT c.chunk_id, c.document_id, c.filename, c.page_number,
                       c.chunk_index, c.text, e.model_name, e.dimension,
                       e.embedding_json
                FROM document_chunks c
                JOIN document_chunk_embeddings e ON e.chunk_id = c.chunk_id
                WHERE e.dimension = ?
            """, (len(query),)).fetchall()

        ranked = []
        for row in rows:
            vector = json.loads(row["embedding_json"])
            score = sum(a * b for a, b in zip(query, vector))
            ranked.append({
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "filename": row["filename"],
                "page_number": row["page_number"],
                "chunk_index": row["chunk_index"],
                "text": row["text"],
                "model": row["model_name"],
                "similarity": float(score),
            })

        ranked.sort(key=lambda item: item["similarity"], reverse=True)
        return ranked[:top_k]
    finally:
        connection.close()
