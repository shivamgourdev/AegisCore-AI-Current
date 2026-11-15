"""AEGISCORE_PART4B_GENERATED
Integration tests for persisted document chunks.
"""

import pymupdf
from fastapi.testclient import TestClient

from aegiscore.main import app


def make_pdf(*texts):
    pdf = pymupdf.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    content = pdf.tobytes()
    pdf.close()
    return content


def test_txt_upload_persists_chunks_with_source_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/documents/upload",
        files={"file": ("facts.txt", b"Reliable chunk source text.", "text/plain")},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()["document"]["document_id"]

    result = client.get(f"/documents/{document_id}/chunks")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["chunk_count"] == 1
    chunk = data["chunks"][0]
    assert chunk["document_id"] == document_id
    assert chunk["filename"] == "facts.txt"
    assert chunk["page_number"] == 1
    assert chunk["chunk_index"] == 0
    assert chunk["text"] == "Reliable chunk source text."
    assert chunk["text_sha256"]
    assert chunk["char_count"] == len(chunk["text"])


def test_pdf_upload_preserves_page_numbers_in_saved_chunks(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "report.pdf",
                make_pdf("First page citation", "Second page citation"),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 200, response.text
    document_id = response.json()["document"]["document_id"]

    data = client.get(f"/documents/{document_id}/chunks").json()
    assert data["chunk_count"] == 2
    assert [c["page_number"] for c in data["chunks"]] == [1, 2]
    assert "First page citation" in data["chunks"][0]["text"]
    assert "Second page citation" in data["chunks"][1]["text"]


def test_duplicate_upload_keeps_same_chunk_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    file_data = {"file": ("stable.txt", b"Stable chunk identity.", "text/plain")}

    first = client.post("/documents/upload", files=file_data)
    assert first.status_code == 200, first.text
    document_id = first.json()["document"]["document_id"]
    first_chunks = client.get(f"/documents/{document_id}/chunks").json()["chunks"]
    first_ids = [item["chunk_id"] for item in first_chunks]

    second = client.post(
        "/documents/upload",
        files={"file": ("stable.txt", b"Stable chunk identity.", "text/plain")},
    )
    assert second.status_code == 200, second.text
    second_chunks = client.get(f"/documents/{document_id}/chunks").json()["chunks"]

    assert second.json()["duplicate"] is True
    assert [item["chunk_id"] for item in second_chunks] == first_ids
    assert len(second_chunks) == len(first_ids)


def test_corrupt_pdf_has_no_chunks_and_unknown_document_is_404(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/documents/upload",
        files={"file": ("broken.pdf", b"%PDF-broken", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    document_id = response.json()["document"]["document_id"]
    assert response.json()["extraction"]["status"] == "extraction_failed"

    chunks = client.get(f"/documents/{document_id}/chunks")
    assert chunks.status_code == 200, chunks.text
    assert chunks.json()["chunk_count"] == 0
    assert chunks.json()["chunks"] == []

    unknown = client.get(
        "/documents/00000000-0000-0000-0000-000000000000/chunks"
    )
    assert unknown.status_code == 404
