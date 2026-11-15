"""Persist extracted document text and page-level source metadata."""

import json
import sqlite3

from aegiscore.document_service import _database_connection, get_data_dir
from aegiscore.extraction_service import extract_document


def extract_and_store(document: dict, content: bytes) -> dict:
    """Extract a saved document and persist its searchable text and page data."""
    try:
        result = extract_document(document["filename"], content)
        status = result.status
        error = None
        pages = [
            {"page_number": page.page_number, "text": page.text}
            for page in result.pages
        ]
        full_text = result.full_text
    except Exception as exc:
        status = "extraction_failed"
        error = str(exc)
        pages = []
        full_text = ""

    connection = _database_connection()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_extractions (
                document_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                full_text TEXT NOT NULL,
                pages_json TEXT NOT NULL,
                error TEXT,
                FOREIGN KEY(document_id) REFERENCES documents(document_id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO document_extractions
                (document_id, status, full_text, pages_json, error)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                status=excluded.status,
                full_text=excluded.full_text,
                pages_json=excluded.pages_json,
                error=excluded.error
            """,
            (
                document["document_id"],
                status,
                full_text,
                json.dumps(pages, ensure_ascii=False),
                error,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    return {
        "document_id": document["document_id"],
        "status": status,
        "page_count": len(pages),
        "character_count": len(full_text),
        "error": error,
    }


def get_extraction(document_id: str) -> dict | None:
    """Return stored extracted text and source pages for one document."""
    connection = _database_connection()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_extractions (
                document_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                full_text TEXT NOT NULL,
                pages_json TEXT NOT NULL,
                error TEXT,
                FOREIGN KEY(document_id) REFERENCES documents(document_id)
            )
            """
        )
        row = connection.execute(
            """
            SELECT document_id, status, full_text, pages_json, error
            FROM document_extractions WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "document_id": row["document_id"],
            "status": row["status"],
            "text": row["full_text"],
            "pages": json.loads(row["pages_json"]),
            "error": row["error"],
        }
    finally:
        connection.close()
