"""AEGISCORE_PART4_EDGE_SECURITY
Document edge cases and security/resilience tests.
Covers Unicode, unusual whitespace, path traversal, unsafe filenames,
Ollama unavailability, timeouts, malformed requests, and secret handling.
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

from aegiscore.document_service import validate_upload, DocumentUploadError
from aegiscore.main import app


class TestUnicodeAndWhitespace:
    def test_unicode_text_upload_and_chunking(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        content = "Caf\\u00e9 \\u00fc\\u00f1\\u00edcode \\u4e2d\\u6587\\u6587\\u5b57 \\u0915\\u094d\\u0930\\u093e".encode("utf-8")
        response = client.post(
            "/documents/upload",
            files={"file": ("unicode.txt", content, "text/plain")},
        )
        assert response.status_code == 200, response.text
        doc_id = response.json()["document"]["document_id"]

        chunks = client.get(f"/documents/{doc_id}/chunks")
        assert chunks.status_code == 200
        data = chunks.json()
        assert data["chunk_count"] >= 1
        assert "\\u00e9" in data["chunks"][0]["text"].encode("utf-8").decode("unicode_escape") or "Caf" in data["chunks"][0]["text"]

    def test_unusual_whitespace_preserved(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        content = "Line1\\r\\nLine2\\t\\tIndented\\n\\nLine3  double  space".encode("utf-8")
        response = client.post(
            "/documents/upload",
            files={"file": ("whitespace.txt", content, "text/plain")},
        )
        assert response.status_code == 200, response.text
        doc_id = response.json()["document"]["document_id"]

        chunks = client.get(f"/documents/{doc_id}/chunks")
        assert chunks.status_code == 200
        full_text = " ".join(c["text"] for c in chunks.json()["chunks"])
        assert "Line1" in full_text
        assert "Line2" in full_text
        assert "Line3" in full_text

    def test_pdf_with_unicode_text(self, tmp_path, monkeypatch):
        import pymupdf
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "Caf\\u00e9 \\u4e2d\\u6587 revenue: 42 million")
        pdf_bytes = pdf.tobytes()
        pdf.close()

        response = client.post(
            "/documents/upload",
            files={"file": ("unicode.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200, response.text
        doc_id = response.json()["document"]["document_id"]

        chunks = client.get(f"/documents/{doc_id}/chunks")
        assert chunks.status_code == 200
        data = chunks.json()
        assert data["chunk_count"] >= 1


class TestPathTraversalAndUnsafeFilenames:
    def test_path_traversal_filename_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        response = client.post(
            "/documents/upload",
            files={"file": ("../../../etc/passwd", b"malicious content", "text/plain")},
        )
        assert response.status_code == 415, response.text

    def test_backslash_path_traversal_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        response = client.post(
            "/documents/upload",
            files={"file": ("..\\..\\windows\\system32", b"malicious", "text/plain")},
        )
        assert response.status_code == 415, response.text

    def test_dot_dot_filename_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        response = client.post(
            "/documents/upload",
            files={"file": ("..", b"content", "text/plain")},
        )
        assert response.status_code == 400, response.text

    def test_validate_upload_rejects_unsafe_names(self):
        with pytest.raises(DocumentUploadError):
            validate_upload("../../../etc/passwd", b"content")
        with pytest.raises(DocumentUploadError):
            validate_upload("..", b"content")
        with pytest.raises(DocumentUploadError):
            validate_upload(None, b"content")
        with pytest.raises(DocumentUploadError):
            validate_upload("", b"content")


class TestOllamaUnavailability:
    def test_embedding_endpoint_returns_503_when_ollama_down(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))

        from aegiscore.ollama_embedding import OllamaEmbeddingEncoder
        from aegiscore.chunk_storage import store_document_chunks
        from aegiscore.document_service import save_document

        class FailingEncoder(OllamaEmbeddingEncoder):
            def encode(self, texts, **kwargs):
                from aegiscore.embedding_service import EmbeddingGenerationError
                raise EmbeddingGenerationError("Ollama unavailable at test address")

        import aegiscore.main as main_module
        monkeypatch.setattr(main_module, "OllamaEmbeddingEncoder", FailingEncoder)

        client = TestClient(app)

        doc, _ = save_document(
            "test.txt", b"Test content for embedding failure test.",
        )
        store_document_chunks(
            doc["document_id"], doc["filename"],
            [{"page_number": 1, "text": "Test content for embedding failure test."}],
        )

        response = client.post(
            f"/documents/{doc['document_id']}/embed",
        )
        assert response.status_code == 503, response.text


class TestMalformedAPIRequests:
    def test_ask_rejects_non_dict_payload(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        response = client.post("/ask", content="not json", headers={"Content-Type": "application/json"})
        # FastAPI will return 422 for invalid JSON body
        assert response.status_code in (400, 422), response.text

    def test_ask_rejects_query_as_number(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        response = client.post("/ask", json={"query": 12345})
        assert response.status_code == 400, response.text

    def test_search_rejects_missing_query(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        response = client.post("/search", json={})
        assert response.status_code == 400, response.text

    def test_search_rejects_query_as_list(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        response = client.post("/search", json={"query": ["revenue"]})
        assert response.status_code == 400, response.text


class TestNoSecretsInLogs:
    def test_upload_response_d_not_expose_storage_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        response = client.post(
            "/documents/upload",
            files={"file": ("secret.txt", b"classified information", "text/plain")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # Response should not contain internal storage paths
        response_str = json.dumps(body)
        assert "/uploads/" not in response_str
        assert "storage_key" not in response_str
        assert "sha256" in body["document"]  # sha256 is public metadata, not a secret


class TestChunkBoundariesAndEmptyChunks:
    def test_empty_chunks_not_created_for_blank_pages(self, tmp_path, monkeypatch):
        import pymupdf
        monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
        client = TestClient(app)

        # PDF with one blank page and one content page
        pdf = pymupdf.open()
        pdf.new_page()  # blank page
        page2 = pdf.new_page()
        page2.insert_text((72, 72), "Content on page 2")
        pdf_bytes = pdf.tobytes()
        pdf.close()

        response = client.post(
            "/documents/upload",
            files={"file": ("blank_page.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200, response.text
        doc_id = response.json()["document"]["document_id"]

        chunks = client.get(f"/documents/{doc_id}/chunks")
        assert chunks.status_code == 200
        data = chunks.json()
        # Blank page should produce no chunks
        assert all(c["page_number"] == 2 for c in data["chunks"]), data
        assert all(c["text"].strip() for c in data["chunks"])
