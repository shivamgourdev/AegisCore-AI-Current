"""AEGISCORE_PHASE3_TESTS_RAG_INTEGRATION
Integration tests for the enhanced RAG QA endpoint with Phase 3 features.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from aegiscore.main import app


class TestEnhancedAskEndpoint:
    def setup_method(self):
        self.client = TestClient(app)

    def test_ask_returns_confidence(self):
        """Test that /ask returns confidence information."""
        # We need to mock the Ollama call. Since we can't easily mock httpx
        # in a TestClient context, we test that the endpoint structure works
        # by checking the response shape when search returns no results.
        response = self.client.post("/ask", json={
            "query": "What is unknown topic xyz123?",
            "top_k": 5,
            "min_similarity": 0.45,
        })
        assert response.status_code == 200
        data = response.json()
        # Should have the new Phase 3 fields
        assert "query_processing" in data
        assert "confidence" in data
        assert "support_assessment" in data
        assert "diagnostics" in data

    def test_ask_diagnose_endpoint(self):
        """Test the /ask/diagnose endpoint."""
        response = self.client.post("/ask/diagnose", json={
            "query": "What is revenue?",
            "top_k": 5,
            "mode": "dense",
            "min_similarity": 0.45,
        })
        assert response.status_code == 200
        data = response.json()
        assert "query_processing" in data
        assert "retrieval" in data
        assert "context_selection" in data
        assert "diagnostics" in data

    def test_ask_diagnose_invalid_query(self):
        """Test diagnose endpoint with invalid query."""
        response = self.client.post("/ask/diagnose", json={
            "query": "",
            "top_k": 5,
        })
        assert response.status_code == 422

    def test_ask_preserves_existing_fields(self):
        """Test that /ask still returns existing fields."""
        response = self.client.post("/ask", json={
            "query": "What is unknown topic xyz456?",
            "top_k": 5,
            "min_similarity": 0.45,
        })
        assert response.status_code == 200
        data = response.json()
        # Existing fields must still be present
        assert "answer" in data
        assert "abstained" in data
        assert "citations" in data
        assert "model" in data

    def test_ask_rejects_invalid_mode(self):
        """Test that invalid mode is rejected."""
        response = self.client.post("/ask", json={
            "query": "What is revenue?",
            "mode": "invalid_mode",
        })
        assert response.status_code == 400

    def test_ask_diagnose_preserves_query_processing(self):
        """Test that diagnose endpoint includes query processing info."""
        response = self.client.post("/ask/diagnose", json={
            "query": "What is revenue and profit?",
            "top_k": 5,
            "mode": "hybrid",
        })
        assert response.status_code == 200
        data = response.json()
        qp = data["query_processing"]
        assert qp["original_query"] == "What is revenue and profit?"
        assert "normalized_query" in qp
        assert "num_subqueries" in qp
