"""AEGISCORE_PART4D_GENERATED
Tests for vector persistence, embedding API, and semantic retrieval.
"""
from fastapi.testclient import TestClient
import pytest

from aegiscore import main as main_module


class FakeOllamaEncoder:
    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            lower = text.lower()
            if "revenue" in lower or "financial" in lower:
                vectors.append([1.0, 0.0, 0.0])
            elif "customer" in lower:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(main_module, "OllamaEmbeddingEncoder", FakeOllamaEncoder)
    return TestClient(main_module.app)


def upload_text(client, filename, text):
    response = client.post(
        "/documents/upload",
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200, response.text
    return response.json()["document"]["document_id"]


def test_embedding_endpoint_persists_normalized_vector_metadata(client):
    document_id = upload_text(
        client, "revenue.txt", "Revenue grew during the quarter."
    )

    response = client.post(f"/documents/{document_id}/embed")
    assert response.status_code == 200, response.text
    assert response.json()["embedding_count"] == 1
    assert response.json()["dimension"] == 3

    stored = client.get(f"/documents/{document_id}/embeddings")
    assert stored.status_code == 200, stored.text
    data = stored.json()
    assert data["embedding_count"] == 1
    assert data["embeddings"][0]["model"] == "nomic-embed-text:latest"
    assert data["embeddings"][0]["dimension"] == 3
    assert data["embeddings"][0]["vector_norm"] == pytest.approx(1.0)
    assert data["embeddings"][0]["filename"] == "revenue.txt"


def test_semantic_search_ranks_matching_source_first(client):
    revenue_id = upload_text(
        client, "revenue.txt", "Revenue and financial performance improved."
    )
    customer_id = upload_text(
        client, "customers.txt", "Customer satisfaction improved."
    )

    assert client.post(f"/documents/{revenue_id}/embed").status_code == 200
    assert client.post(f"/documents/{customer_id}/embed").status_code == 200

    response = client.post(
        "/search", json={"query": "What happened to revenue?", "top_k": 5}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["result_count"] == 2
    assert data["results"][0]["filename"] == "revenue.txt"
    assert data["results"][0]["similarity"] == pytest.approx(1.0)
    assert data["results"][0]["page_number"] == 1
    assert data["results"][0]["text"]


def test_unknown_document_embedding_endpoint_returns_404(client):
    response = client.post(
        "/documents/00000000-0000-0000-0000-000000000000/embed"
    )
    assert response.status_code == 404


def test_unknown_document_embedding_metadata_returns_404(client):
    response = client.get(
        "/documents/00000000-0000-0000-0000-000000000000/embeddings"
    )
    assert response.status_code == 404


@pytest.mark.parametrize("payload", [
    {},
    {"query": ""},
    {"query": "   "},
    {"query": 123},
])
def test_search_rejects_invalid_queries(client, payload):
    response = client.post("/search", json=payload)
    assert response.status_code == 400


@pytest.mark.parametrize("top_k", [0, -1, 51, True, "3"])
def test_search_rejects_invalid_top_k(client, top_k):
    response = client.post("/search", json={"query": "revenue", "top_k": top_k})
    assert response.status_code == 400
