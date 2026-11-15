"""AEGISCORE_V1_HARDENING
Regression tests for document status and delete endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from aegiscore.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path / "aegiscore-data"))


class TestDocumentStatus:
    def test_status_for_uploaded_txt_document(self):
        upload = client.post(
            "/documents/upload",
            files={"file": ("notes.txt", b"Hello world content.", "text/plain")},
        )
        assert upload.status_code == 200
        doc_id = upload.json()["document"]["document_id"]

        status = client.get(f"/documents/{doc_id}/status")
        assert status.status_code == 200
        data = status.json()
        assert data["document_id"] == doc_id
        assert data["filename"] == "notes.txt"
        assert data["extension"] == ".txt"
        assert data["status"] == "text_extracted"
        assert data["page_count"] >= 1
        assert data["chunk_count"] >= 1
        assert data["embedding_count"] == 0  # Not embedded yet

    def test_status_for_unknown_document(self):
        status = client.get(
            "/documents/00000000-0000-0000-0000-000000000000/status"
        )
        assert status.status_code == 404

    def test_status_after_embedding(self):
        upload = client.post(
            "/documents/upload",
            files={"file": ("notes.txt", b"Hello world content.", "text/plain")},
        )
        doc_id = upload.json()["document"]["document_id"]

        embed = client.post(f"/documents/{doc_id}/embed")
        assert embed.status_code == 200

        status = client.get(f"/documents/{doc_id}/status")
        assert status.status_code == 200
        data = status.json()
        assert data["embedding_count"] >= 1
        assert data["embedding_model"] is not None


class TestDocumentDelete:
    def test_delete_txt_document(self):
        upload = client.post(
            "/documents/upload",
            files={"file": ("notes.txt", b"Content to delete.", "text/plain")},
        )
        assert upload.status_code == 200
        doc_id = upload.json()["document"]["document_id"]

        # Embed it first
        client.post(f"/documents/{doc_id}/embed")

        # Verify it exists
        status = client.get(f"/documents/{doc_id}/status")
        assert status.status_code == 200

        # Delete it
        delete = client.delete(f"/documents/{doc_id}")
        assert delete.status_code == 200
        assert delete.json()["deleted"] is True

        # Verify it's gone
        status = client.get(f"/documents/{doc_id}/status")
        assert status.status_code == 404

        chunks = client.get(f"/documents/{doc_id}/chunks")
        assert chunks.status_code == 404

    def test_delete_unknown_document(self):
        delete = client.delete(
            "/documents/00000000-0000-0000-0000-000000000000"
        )
        assert delete.status_code == 404

    def test_delete_pdf_document(self):
        pdf_content = b"%PDF-1.7\nMinimal signature fixture"
        upload = client.post(
            "/documents/upload",
            files={"file": ("sample.pdf", pdf_content, "application/pdf")},
        )
        assert upload.status_code == 200
        doc_id = upload.json()["document"]["document_id"]

        delete = client.delete(f"/documents/{doc_id}")
        assert delete.status_code == 200
        assert delete.json()["deleted"] is True

        status = client.get(f"/documents/{doc_id}/status")
        assert status.status_code == 404
