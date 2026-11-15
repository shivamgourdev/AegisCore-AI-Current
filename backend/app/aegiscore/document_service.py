"""Validated local document storage for AegisCore AI."""

import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class DocumentUploadError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def get_data_dir() -> Path:
    """Resolve local storage, allowing tests to use isolated temporary paths."""
    override = os.environ.get("AEGISCORE_DATA_DIR")
    if override:
        return Path(override).resolve()

    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data"


def _database_connection():
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(data_dir / "aegiscore.db"), timeout=10)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            extension TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            storage_key TEXT NOT NULL UNIQUE,
            uploaded_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def _public_document(row):
    """Return metadata only; never expose the internal storage path."""
    return {
        "document_id": row["document_id"],
        "filename": row["filename"],
        "extension": row["extension"],
        "content_type": row["content_type"],
        "size_bytes": row["size_bytes"],
        "sha256": row["sha256"],
        "uploaded_at": row["uploaded_at"],
    }


def validate_upload(filename: str | None, content: bytes) -> tuple[str, str]:
    """Validate the name, size, extension and basic file signature/content."""
    if not filename or not filename.strip():
        raise DocumentUploadError("A filename is required.", 400)

    # Treat Windows and POSIX separators as path separators.
    safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()

    if not safe_name or safe_name in {".", ".."}:
        raise DocumentUploadError("The filename is invalid.", 400)

    extension = Path(safe_name).suffix.lower()

    if extension not in ALLOWED_TYPES:
        raise DocumentUploadError(
            "Unsupported file type. Upload a PDF, TXT or MD file.",
            415,
        )

    if not content:
        raise DocumentUploadError("The uploaded file is empty.", 400)

    if len(content) > MAX_FILE_SIZE:
        raise DocumentUploadError(
            "File exceeds the maximum allowed size of 10 MB.",
            413,
        )

    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise DocumentUploadError(
                "The PDF signature is invalid or missing.",
                400,
            )
    else:
        try:
            decoded = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise DocumentUploadError(
                "Text files must contain valid UTF-8 text.",
                400,
            ) from exc

        if "\x00" in decoded:
            raise DocumentUploadError(
                "Binary content is not accepted as a text document.",
                400,
            )

        if not decoded.strip():
            raise DocumentUploadError(
                "The uploaded text document contains no text.",
                400,
            )

    return safe_name, extension


def save_document(filename: str | None, content: bytes) -> tuple[dict, bool]:
    """Store a validated file once and register its metadata transactionally."""
    safe_name, extension = validate_upload(filename, content)
    digest = hashlib.sha256(content).hexdigest()
    content_type = ALLOWED_TYPES[extension]

    data_dir = get_data_dir()
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    connection = _database_connection()
    storage_path = None

    try:
        # Serializes duplicate checks/writes across concurrent upload requests.
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            "SELECT * FROM documents WHERE sha256 = ?",
            (digest,),
        ).fetchone()

        if existing is not None:
            connection.commit()
            return _public_document(existing), True

        document_id = str(uuid.uuid4())
        storage_key = document_id + extension
        storage_path = uploads_dir / storage_key
        temporary_path = uploads_dir / (storage_key + ".tmp")

        try:
            temporary_path.write_bytes(content)
            os.replace(str(temporary_path), str(storage_path))

            uploaded_at = datetime.now(timezone.utc).isoformat()

            connection.execute(
                """
                INSERT INTO documents (
                    document_id, filename, extension, content_type,
                    size_bytes, sha256, storage_key, uploaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    safe_name,
                    extension,
                    content_type,
                    len(content),
                    digest,
                    storage_key,
                    uploaded_at,
                ),
            )
            connection.commit()

        except Exception:
            connection.rollback()
            if storage_path is not None:
                storage_path.unlink(missing_ok=True)
            raise
        finally:
            temporary_path.unlink(missing_ok=True)

        row = connection.execute(
            "SELECT * FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()

        return _public_document(row), False

    finally:
        connection.close()


def list_documents() -> list[dict]:
    """List registered document metadata without exposing stored file paths."""
    connection = _database_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
        return [_public_document(row) for row in rows]
    finally:
        connection.close()

def get_resume_attachment(document_id: str) -> tuple[dict, Path]:
    """Retrieve a stored PDF resume by ID without exposing its path publicly."""
    if not isinstance(document_id, str) or not document_id.strip():
        raise DocumentUploadError("A valid document ID is required.", 400)

    connection = _database_connection()
    try:
        row = connection.execute(
            "SELECT * FROM documents WHERE document_id = ?",
            (document_id.strip(),),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise DocumentUploadError("Resume document was not found.", 404)

    if row["extension"].lower() != ".pdf":
        raise DocumentUploadError("The selected resume must be a PDF.", 415)

    uploads_dir = (get_data_dir() / "uploads").resolve()
    storage_path = (uploads_dir / row["storage_key"]).resolve()

    if storage_path.parent != uploads_dir:
        raise DocumentUploadError("Invalid resume storage reference.", 400)

    if not storage_path.is_file():
        raise DocumentUploadError("Stored resume file is missing.", 404)

    if storage_path.stat().st_size != row["size_bytes"]:
        raise DocumentUploadError("Stored resume file failed integrity checks.", 409)

    file_digest = hashlib.sha256(storage_path.read_bytes()).hexdigest()
    if file_digest != row["sha256"]:
        raise DocumentUploadError("Stored resume file failed integrity checks.", 409)

    metadata = _public_document(row)
    return metadata, storage_path


# ============================================================================
# Resume Version Management (Phase 9)
# ============================================================================

def _ensure_resume_versions_table(connection):
    """Create the resume_versions table if it doesn't exist."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS resume_versions (
            version_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(document_id),
            UNIQUE(document_id, version_number)
        )
    """)


def _ensure_active_resume_table(connection):
    """Create the active_resume table if it doesn't exist."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS active_resume (
            document_id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(document_id),
            FOREIGN KEY(version_id) REFERENCES resume_versions(version_id)
        )
    """)


def save_resume_with_versioning(filename: str, content: bytes) -> tuple[dict, bool]:
    """Save a resume PDF with version management.

    If a document with the same filename exists but different content,
    create a new version. If the same content already exists, return
    the existing document (deduplication).
    """
    # First, try the normal upload
    doc, duplicate = save_document(filename, content)

    if duplicate:
        # Same content already exists, return existing
        return doc, True

    # New content - this is a new version
    connection = _database_connection()
    try:
        _ensure_resume_versions_table(connection)
        _ensure_active_resume_table(connection)

        connection.execute("BEGIN IMMEDIATE")

        # Check if there's already a document with this filename
        existing = connection.execute(
            "SELECT document_id FROM documents WHERE filename = ? AND extension = '.pdf'",
            (filename,),
        ).fetchall()

        if existing:
            existing_doc_id = existing[0]["document_id"]

            # Get the latest version number
            version_row = connection.execute(
                "SELECT MAX(version_number) as max_ver FROM resume_versions WHERE document_id = ?",
                (existing_doc_id,),
            ).fetchone()
            new_version = (version_row["max_ver"] or 0) + 1

            # Deactivate old versions
            connection.execute(
                "UPDATE resume_versions SET is_active = 0 WHERE document_id = ?",
                (existing_doc_id,),
            )

            # Deactivate old active resume
            connection.execute(
                "UPDATE active_resume SET document_id = ? WHERE document_id = ?",
                (doc["document_id"], existing_doc_id),
            )

            # Create new version
            version_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                INSERT INTO resume_versions (version_id, document_id, version_number, is_active, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (version_id, doc["document_id"], new_version, now),
            )

            # Set as active resume
            connection.execute(
                """
                INSERT OR REPLACE INTO active_resume (document_id, version_id, updated_at)
                VALUES (?, ?, ?)
                """,
                (doc["document_id"], version_id, now),
            )

            connection.commit()
            return doc, False
        else:
            # First version of this resume
            version_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                INSERT INTO resume_versions (version_id, document_id, version_number, is_active, created_at)
                VALUES (?, ?, 1, 1, ?)
                """,
                (version_id, doc["document_id"], now),
            )

            # Set as active resume
            connection.execute(
                """
                INSERT OR REPLACE INTO active_resume (document_id, version_id, updated_at)
                VALUES (?, ?, ?)
                """,
                (doc["document_id"], version_id, now),
            )

            connection.commit()
            return doc, False
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_resume_versions(document_id: str) -> list[dict]:
    """Get all versions of a resume document."""
    connection = _database_connection()
    try:
        # First check if this document_id is a resume
        row = connection.execute(
            "SELECT extension FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()

        if row is None:
            raise DocumentUploadError("Document not found.", 404)

        if row["extension"].lower() != ".pdf":
            raise DocumentUploadError("Document is not a PDF resume.", 415)

        rows = connection.execute("""
            SELECT rv.version_id, rv.document_id, rv.version_number, rv.is_active, rv.created_at,
                   d.filename, d.sha256, d.size_bytes, d.uploaded_at
            FROM resume_versions rv
            JOIN documents d ON rv.document_id = d.document_id
            WHERE d.document_id = ?
            ORDER BY rv.version_number
        """, (document_id,)).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


def set_active_resume_version(version_id: str) -> dict:
    """Set a specific version as the active resume."""
    connection = _database_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")

        # Get the document_id for this version
        row = connection.execute(
            "SELECT document_id FROM resume_versions WHERE version_id = ?",
            (version_id,),
        ).fetchone()

        if row is None:
            connection.rollback()
            raise DocumentUploadError("Version not found.", 404)

        document_id = row["document_id"]

        # Verify the document exists and is a PDF
        doc_row = connection.execute(
            "SELECT extension FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()

        if doc_row is None or doc_row["extension"].lower() != ".pdf":
            connection.rollback()
            raise DocumentUploadError("Document is not a PDF resume.", 415)

        # Deactivate all versions for this document
        connection.execute(
            "UPDATE resume_versions SET is_active = 0 WHERE document_id = ?",
            (document_id,),
        )

        # Activate this version
        connection.execute(
            "UPDATE resume_versions SET is_active = 1 WHERE version_id = ?",
            (version_id,),
        )

        # Update active_resume table
        now = datetime.now(timezone.utc).isoformat()
        connection.execute(
            """
            INSERT OR REPLACE INTO active_resume (document_id, version_id, updated_at)
            VALUES (?, ?, ?)
            """,
            (document_id, version_id, now),
        )

        connection.commit()
        return get_resume_versions(document_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_active_resume() -> dict | None:
    """Get the currently active resume document."""
    connection = _database_connection()
    try:
        row = connection.execute("""
            SELECT d.document_id, d.filename, d.extension, d.size_bytes, d.sha256,
                   d.uploaded_at, rv.version_id, rv.version_number, rv.created_at
            FROM active_resume ar
            JOIN documents d ON ar.document_id = d.document_id
            JOIN resume_versions rv ON ar.version_id = rv.version_id
            WHERE ar.version_id = rv.version_id
        """).fetchone()

        if row is None:
            return None

        return dict(row)
    finally:
        connection.close()

