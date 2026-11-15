from fastapi.testclient import TestClient
from aegiscore.main import app

client = TestClient(app)

def test_ask_endpoint_is_in_openapi():
    assert "/ask" in app.openapi()["paths"]

def test_ask_rejects_blank_query_without_calling_models():
    response = client.post("/ask", json={"query": "   "})
    assert response.status_code == 400

def test_ask_rejects_invalid_top_k():
    response = client.post("/ask", json={"query": "revenue", "top_k": 0})
    assert response.status_code == 400

def test_ask_rejects_invalid_similarity_threshold():
    response = client.post("/ask", json={"query": "revenue", "min_similarity": 1.1})
    assert response.status_code == 400

# Part 4F: citation-integrity regression tests
import asyncio
from types import SimpleNamespace

import aegiscore.main as main_module


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")


class _FakeAsyncClient:
    """Mock retrieval and Ollama generation without network/model calls."""
    generation = ""

    def __init__(self, *args, **kwargs):
        self.url = kwargs.get("base_url", "")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):
        if url == "/search":
            return _FakeResponse(payload={
                "results": [{
                    "filename": "facts.txt",
                    "page_number": 1,
                    "text": "Project Orion revenue was 42 million dollars in Q3.",
                    "similarity": 0.9,
                }]
            })
        if url.endswith("/api/generate"):
            return _FakeResponse(payload={"response": self.generation})
        raise AssertionError(f"Unexpected mocked URL: {url}")


def _run_ask_with_model_answer(monkeypatch, answer):
    _FakeAsyncClient.generation = answer
    monkeypatch.setattr(main_module._rag_httpx, "AsyncClient", _FakeAsyncClient)
    return asyncio.run(main_module.ask_documents({
        "query": "What was Project Orion revenue?",
        "top_k": 5,
        "min_similarity": 0.4,
    }))


def test_part4f_invalid_only_citation_does_not_attach_all_sources(monkeypatch):
    result = _run_ask_with_model_answer(monkeypatch, "Revenue was 42 million [S99].")
    assert result["abstained"] is True
    assert result["citations"] == []


def test_part4f_uncited_answer_is_not_returned_as_verified(monkeypatch):
    result = _run_ask_with_model_answer(monkeypatch, "Revenue was 42 million dollars.")
    assert result["abstained"] is True
    assert result["citations"] == []


def test_part4f_valid_citation_is_preserved(monkeypatch):
    result = _run_ask_with_model_answer(
        monkeypatch, "Revenue was 42 million dollars [S1]."
    )
    assert result["abstained"] is False
    assert [citation["source_id"] for citation in result["citations"]] == ["S1"]


def test_part4f_invalid_citation_is_not_silently_removed_from_claim(monkeypatch):
    result = _run_ask_with_model_answer(
        monkeypatch, "Revenue was 42 million dollars [S99]."
    )
    assert result["abstained"] is True
    assert "42 million" not in result["answer"]
