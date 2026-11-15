import hashlib
import sqlite3

import pytest

from aegiscore.document_service import (
    DocumentUploadError,
    get_data_dir,
    get_resume_attachment,
    save_document,
)


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    return tmp_path


def test_retrieves_stored_pdf_resume(isolated_storage):
    content = b"%PDF-1.4\nfake test PDF content"
    metadata, duplicate = save_document("resume.pdf", content)

    assert duplicate is False

    public_metadata, path = get_resume_attachment(
        metadata["document_id"]
    )

    assert public_metadata["document_id"] == metadata["document_id"]
    assert public_metadata["filename"] == "resume.pdf"
    assert path.is_file()
    assert path.read_bytes() == content
    assert "storage_key" not in public_metadata


def test_rejects_unknown_document_id(isolated_storage):
    with pytest.raises(DocumentUploadError) as exc:
        get_resume_attachment("missing-document-id")

    assert exc.value.status_code == 404


def test_rejects_non_pdf_document(isolated_storage):
    metadata, _ = save_document("resume.txt", b"Python developer resume")

    with pytest.raises(DocumentUploadError) as exc:
        get_resume_attachment(metadata["document_id"])

    assert exc.value.status_code == 415


def test_rejects_missing_stored_file(isolated_storage):
    metadata, _ = save_document("resume.pdf", b"%PDF-1.4\nfake content")
    stored_path = get_data_dir() / "uploads" / (
        metadata["document_id"] + ".pdf"
    )
    stored_path.unlink()

    with pytest.raises(DocumentUploadError) as exc:
        get_resume_attachment(metadata["document_id"])

    assert exc.value.status_code == 404


def test_rejects_modified_file_size(isolated_storage):
    metadata, _ = save_document("resume.pdf", b"%PDF-1.4\noriginal")
    stored_path = get_data_dir() / "uploads" / (
        metadata["document_id"] + ".pdf"
    )
    stored_path.write_bytes(b"%PDF-1.4\nchanged content")

    with pytest.raises(DocumentUploadError) as exc:
        get_resume_attachment(metadata["document_id"])

    assert exc.value.status_code == 409

def test_rejects_same_size_tampered_file(isolated_storage):
    original = b"%PDF-1.4\noriginal content"
    metadata, _ = save_document("resume.pdf", original)

    stored_path = (
        get_data_dir()
        / "uploads"
        / (metadata["document_id"] + ".pdf")
    )

    tampered = b"%PDF-1.4\nmodified content"
    assert len(tampered) == len(original)

    stored_path.write_bytes(tampered)

    with pytest.raises(DocumentUploadError) as exc:
        get_resume_attachment(metadata["document_id"])

    assert exc.value.status_code == 409
