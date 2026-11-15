"""AEGISCORE_PART4_CITATION
Citation integrity and answer safety tests.
Covers invalid citation IDs, missing citations, malformed output,
missing source metadata, multiple claims, contradictory passages,
unsupported questions, and low-confidence retrieval.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

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
    generation = ""
    search_results = None

    def __init__(self, *args, **kwargs):
        self.url = kwargs.get("base_url", "")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):
        if url == "/search":
            results = self.search_results if self.search_results is not None else [{
                "filename": "facts.txt",
                "page_number": 1,
                "text": "Project Orion revenue was 42 million dollars in Q3.",
                "similarity": 0.9,
            }]
            return _FakeResponse(payload={"results": results})
        if url.endswith("/api/generate"):
            return _FakeResponse(payload={"response": self.generation})
        raise AssertionError(f"Unexpected mocked URL: {url}")


def _run_ask(monkeypatch, answer, search_results=None):
    _FakeAsyncClient.generation = answer
    _FakeAsyncClient.search_results = search_results
    monkeypatch.setattr(main_module._rag_httpx, "AsyncClient", _FakeAsyncClient)
    return asyncio.run(main_module.ask_documents({
        "query": "What was Project Orion revenue?",
        "top_k": 5,
        "min_similarity": 0.4,
    }))


class TestInvalidCitationIDs:
    def test_nonexistent_citation_id_abstains(self, monkeypatch):
        result = _run_ask(monkeypatch, "Revenue was 42 million [S99].")
        assert result["abstained"] is True
        assert result["citations"] == []

    def test_invalid_citation_claim_not_silently_retained(self, monkeypatch):
        result = _run_ask(monkeypatch, "Revenue was 42 million [S99].")
        assert "42 million" not in result["answer"]

    def test_mixed_valid_and_invalid_citations_abstains(self, monkeypatch):
        result = _run_ask(
            monkeypatch,
            "Revenue was 42 million [S1] and [S99].",
        )
        assert result["abstained"] is True
        assert result["citations"] == []

    def test_zero_citation_is_invalid(self, monkeypatch):
        result = _run_ask(monkeypatch, "Revenue was 42 million [S0].")
        assert result["abstained"] is True
        assert result["citations"] == []


class TestMissingCitations:
    def test_factual_answer_without_citations_abstains(self, monkeypatch):
        result = _run_ask(monkeypatch, "Revenue was 42 million dollars.")
        assert result["abstained"] is True
        assert result["citations"] == []

    def test_answer_with_only_narrative_no_facts_no_citations(self, monkeypatch):
        result = _run_ask(monkeypatch, "The documents discuss financial matters.")
        assert result["abstained"] is True
        assert result["citations"] == []


class TestMalformedModelOutput:
    def test_empty_answer_raises_502(self, monkeypatch):
        _FakeAsyncClient.generation = ""
        monkeypatch.setattr(main_module._rag_httpx, "AsyncClient", _FakeAsyncClient)
        with pytest.raises(Exception) as exc_info:
            asyncio.run(main_module.ask_documents({
                "query": "What was Project Orion revenue?",
                "top_k": 5,
                "min_similarity": 0.4,
            }))
        # Empty answer should raise HTTPException 502
        assert exc_info.value.status_code == 502

    def test_whitespace_only_answer_raises_502(self, monkeypatch):
        _FakeAsyncClient.generation = "   \n\t  "
        monkeypatch.setattr(main_module._rag_httpx, "AsyncClient", _FakeAsyncClient)
        with pytest.raises(Exception) as exc_info:
            asyncio.run(main_module.ask_documents({
                "query": "What was Project Orion revenue?",
                "top_k": 5,
                "min_similarity": 0.4,
            }))
        assert exc_info.value.status_code == 502


class TestCitationsWithMissingMetadata:
    def test_citation_with_missing_filename_still_valid(self, monkeypatch):
        search_results = [{
            "filename": None,
            "page_number": None,
            "text": "Project Orion revenue was 42 million dollars in Q3.",
            "similarity": 0.9,
        }]
        result = _run_ask(
            monkeypatch,
            "Revenue was 42 million [S1].",
            search_results=search_results,
        )
        assert result["abstained"] is False
        assert result["citations"][0]["source_id"] == "S1"
        assert result["citations"][0]["filename"] == "unknown"


class TestMultipleClaimsDifferentDocuments:
    def test_two_claims_two_documents_both_cited(self, monkeypatch):
        search_results = [
            {
                "filename": "finance.txt",
                "page_number": 1,
                "text": "Project Orion revenue was 42 million dollars in Q3.",
                "similarity": 0.9,
            },
            {
                "filename": "hiring.txt",
                "page_number": 1,
                "text": "The hiring team plans to recruit six junior Python engineers.",
                "similarity": 0.85,
            },
        ]
        result = _run_ask(
            monkeypatch,
            "Orion revenue was 42 million [S1] and six engineers are being hired [S2].",
            search_results=search_results,
        )
        assert result["abstained"] is False
        citation_ids = {c["source_id"] for c in result["citations"]}
        assert citation_ids == {"S1", "S2"}
        filenames = {c["filename"] for c in result["citations"]}
        assert filenames == {"finance.txt", "hiring.txt"}


class TestContradictoryPassages:
    def test_contradictory_sources_both_available_for_citation(self, monkeypatch):
        search_results = [
            {
                "filename": "report_a.txt",
                "page_number": 1,
                "text": "Project Orion revenue was 42 million dollars in Q3.",
                "similarity": 0.9,
            },
            {
                "filename": "report_b.txt",
                "page_number": 1,
                "text": "Project Orion revenue was 50 million dollars in Q3.",
                "similarity": 0.88,
            },
        ]
        result = _run_ask(
            monkeypatch,
            "Revenue figures conflict: report A says 42 million [S1] while report B says 50 million [S2].",
            search_results=search_results,
        )
        assert result["abstained"] is False
        citation_ids = {c["source_id"] for c in result["citations"]}
        assert citation_ids == {"S1", "S2"}


class TestUnsupportedQuestions:
    def test_unsupported_question_abstains_no_citations(self, monkeypatch):
        search_results = []
        result = _run_ask(
            monkeypatch,
            "I don't have enough evidence.",
            search_results=search_results,
        )
        assert result["abstained"] is True
        assert result["citations"] == []
        assert result["model"] is None


class TestLowConfidenceRetrieval:
    def test_below_threshold_results_are_filtered(self, monkeypatch):
        search_results = [
            {
                "filename": "facts.txt",
                "page_number": 1,
                "text": "Project Orion revenue was 42 million dollars in Q3.",
                "similarity": 0.1,  # Below default 0.45 threshold
            },
        ]
        result = _run_ask(
            monkeypatch,
            "I don't have enough evidence.",
            search_results=search_results,
        )
        assert result["abstained"] is True
        assert result["citations"] == []

    def test_low_similarity_still_retrieves_when_threshold_lowered(self, monkeypatch):
        search_results = [
            {
                "filename": "facts.txt",
                "page_number": 1,
                "text": "Project Orion revenue was 42 million dollars in Q3.",
                "similarity": 0.3,
            },
        ]
        _FakeAsyncClient.generation = "Revenue was 42 million [S1]."
        _FakeAsyncClient.search_results = search_results
        monkeypatch.setattr(main_module._rag_httpx, "AsyncClient", _FakeAsyncClient)
        result = asyncio.run(main_module.ask_documents({
            "query": "What was Project Orion revenue?",
            "top_k": 5,
            "min_similarity": 0.2,
        }))
        assert result["abstained"] is False
        assert result["citations"][0]["source_id"] == "S1"


class TestCitationIDAppearsInAnswer:
    def test_each_returned_citation_id_is_referenced(self, monkeypatch):
        search_results = [
            {
                "filename": "facts.txt",
                "page_number": 1,
                "text": "Project Orion revenue was 42 million dollars in Q3.",
                "similarity": 0.9,
            },
        ]
        result = _run_ask(
            monkeypatch,
            "Revenue was 42 million [S1].",
            search_results=search_results,
        )
        assert result["abstained"] is False
        for citation in result["citations"]:
            assert f"[{citation['source_id']}]" in result["answer"]
