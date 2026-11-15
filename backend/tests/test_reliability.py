"""Reliability regression tests for document upload and extraction."""

import pytest
from fastapi.testclient import TestClient
from aegiscore.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path / "data"))
    with TestClient(app) as test_client:
        yield test_client


def test_duplicate_txt_upload_preserves_original_extraction(client):
    payload = b"Reliability check: the stored source text must remain readable."

    first = client.post(
        "/documents/upload",
        files={"file": ("original.txt", payload, "text/plain")},
    )
    assert first.status_code == 200, first.text
    first_data = first.json()
    first_id = first_data["document"]["document_id"]
    assert first_data["extraction"]["status"] == "text_extracted"

    second = client.post(
        "/documents/upload",
        files={"file": ("original.txt", payload, "text/plain")},
    )
    assert second.status_code == 200, second.text
    second_data = second.json()

    assert second_data["duplicate"] is True
    assert second_data["document"]["document_id"] == first_id
    assert second_data["extraction"]["status"] == "text_extracted"

    readback = client.get(f"/documents/{first_id}/extraction")
    assert readback.status_code == 200, readback.text
    assert "stored source text must remain readable" in readback.json()["text"]

    listing = client.get("/documents")
    assert listing.status_code == 200, listing.text
    listing_json = listing.json()
    documents = (
        listing_json.get("documents", [])
        if isinstance(listing_json, dict)
        else listing_json
    )
    matching = [
        item for item in documents
        if item.get("document_id") == first_id
    ]
    assert len(matching) == 1


def test_corrupt_pdf_failure_is_persisted_and_repeatable(client):
    payload = b"%PDF-this-is-intentionally-corrupt"

    first = client.post(
        "/documents/upload",
        files={"file": ("broken.pdf", payload, "application/pdf")},
    )
    assert first.status_code == 200, first.text
    first_data = first.json()
    first_id = first_data["document"]["document_id"]

    assert first_data["extraction"]["status"] == "extraction_failed"
    assert first_data["extraction"]["error"]

    readback = client.get(f"/documents/{first_id}/extraction")
    assert readback.status_code == 200, readback.text
    stored = readback.json()
    assert stored["status"] == "extraction_failed"
    assert stored["error"]

    second = client.post(
        "/documents/upload",
        files={"file": ("broken.pdf", payload, "application/pdf")},
    )
    assert second.status_code == 200, second.text
    second_data = second.json()

    assert second_data["duplicate"] is True
    assert second_data["document"]["document_id"] == first_id
    assert second_data["extraction"]["status"] == "extraction_failed"

    # A document-level extraction error must not take down the service.
    health = client.get("/health")
    assert health.status_code == 200, health.text


def test_unknown_extraction_id_returns_404_without_crashing(client):
    response = client.get(
        "/documents/00000000-0000-0000-0000-000000000000/extraction"
    )
    assert response.status_code == 404
    assert client.get("/health").status_code == 200
