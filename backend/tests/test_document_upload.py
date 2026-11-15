import hashlib
import os

import pytest
from fastapi.testclient import TestClient

from aegiscore.document_service import MAX_FILE_SIZE
from aegiscore.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path / "aegiscore-data"))


def test_upload_valid_txt():
    content = b"Evidence grounded AI document."
    response = client.post(
        "/documents/upload",
        files={"file": ("notes.txt", content, "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["duplicate"] is False
    assert payload["document"]["filename"] == "notes.txt"
    assert payload["document"]["size_bytes"] == len(content)
    assert payload["document"]["sha256"] == hashlib.sha256(content).hexdigest()


def test_upload_valid_markdown():
    response = client.post(
        "/documents/upload",
        files={"file": ("notes.md", b"# Project notes\nSome content.", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["document"]["extension"] == ".md"


def test_upload_pdf_with_signature():
    content = b"%PDF-1.7\nMinimal signature fixture"
    response = client.post(
        "/documents/upload",
        files={"file": ("sample.pdf", content, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["document"]["content_type"] == "application/pdf"


def test_unsupported_extension_is_rejected():
    response = client.post(
        "/documents/upload",
        files={"file": ("payload.exe", b"not supported", "application/octet-stream")},
    )

    assert response.status_code == 415


def test_empty_file_is_rejected():
    response = client.post(
        "/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert response.status_code == 400


def test_whitespace_only_text_is_rejected():
    response = client.post(
        "/documents/upload",
        files={"file": ("blank.txt", b"  \n\t ", "text/plain")},
    )

    assert response.status_code == 400


def test_invalid_pdf_signature_is_rejected():
    response = client.post(
        "/documents/upload",
        files={"file": ("broken.pdf", b"not actually a PDF", "application/pdf")},
    )

    assert response.status_code == 400


def test_invalid_utf8_text_is_rejected():
    response = client.post(
        "/documents/upload",
        files={"file": ("broken.txt", b"\xff\xfe\xfa", "text/plain")},
    )

    assert response.status_code == 400


def test_oversized_upload_is_rejected():
    content = b"x" * (MAX_FILE_SIZE + 1)
    response = client.post(
        "/documents/upload",
        files={"file": ("large.txt", content, "text/plain")},
    )

    assert response.status_code == 413


def test_duplicate_content_is_not_stored_twice():
    content = b"Same content, same hash."
    first = client.post(
        "/documents/upload",
        files={"file": ("first.txt", content, "text/plain")},
    )
    second = client.post(
        "/documents/upload",
        files={"file": ("renamed.txt", content, "text/plain")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert first.json()["document"]["document_id"] == second.json()["document"]["document_id"]

    data_dir = os.environ["AEGISCORE_DATA_DIR"]
    stored_files = list((__import__("pathlib").Path(data_dir) / "uploads").glob("*"))
    assert len(stored_files) == 1
    assert stored_files[0].suffix == ".txt"


def test_list_documents_returns_registered_metadata():
    client.post(
        "/documents/upload",
        files={"file": ("notes.txt", b"List me.", "text/plain")},
    )

    response = client.get("/documents")

    assert response.status_code == 200
    assert len(response.json()["documents"]) == 1
    assert response.json()["documents"][0]["filename"] == "notes.txt"


def test_document_upload_routes_are_in_openapi():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/documents/upload" in paths
    assert "/documents" in paths