"""AEGISCORE_PART4B_GENERATED
Persistent storage for page-aware document chunks.
"""

import sqlite3
from typing import Any, Iterable

from aegiscore.chunking_service import chunk_document
from aegiscore.document_service import _database_connection


def _ensure_chunk_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            text_sha256 TEXT NOT NULL,
            UNIQUE(document_id, page_number, chunk_index),
            FOREIGN KEY(document_id) REFERENCES documents(document_id)
        )
        """
    )


def store_document_chunks(
    document_id: str,
    filename: str,
    pages: Iterable[Any],
) -> list[dict[str, Any]]:
    """Replace a document's chunks atomically and return the saved records."""
    chunks = chunk_document(document_id, filename, pages)
    connection = _database_connection()

    try:
        _ensure_chunk_table(connection)
        connection.execute("BEGIN")
        connection.execute(
            "DELETE FROM document_chunks WHERE document_id = ?",
            (document_id,),
        )
        connection.executemany(
            """
            INSERT INTO document_chunks (
                chunk_id, document_id, filename, page_number,
                chunk_index, text, char_count, text_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["chunk_id"],
                    item["document_id"],
                    item["filename"],
                    item["page_number"],
                    item["chunk_index"],
                    item["text"],
                    item["char_count"],
                    item["text_sha256"],
                )
                for item in chunks
            ],
        )
        connection.commit()
        return chunks
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_document_chunks(document_id: str) -> list[dict[str, Any]] | None:
    """Return saved chunks, or None when the document does not exist."""
    connection = _database_connection()

    try:
        _ensure_chunk_table(connection)
        document = connection.execute(
            "SELECT document_id FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()

        if document is None:
            return None

        rows = connection.execute(
            """
            SELECT chunk_id, document_id, filename, page_number,
                   chunk_index, text, char_count, text_sha256
            FROM document_chunks
            WHERE document_id = ?
            ORDER BY page_number, chunk_index
            """,
            (document_id,),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()
