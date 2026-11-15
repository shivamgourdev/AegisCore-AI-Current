"""AEGISCORE_PHASE3_TESTS_OBSERVABILITY
Unit tests for the retrieval observability module.
"""

import pytest

from aegiscore.observability import (
    DiagnosticsCollector,
    RetrievalDiagnostics,
    sanitize_for_logging,
)


class TestDiagnosticsCollector:
    def test_collector_basic_flow(self):
        collector = DiagnosticsCollector(original_query="What is revenue?")
        collector.set_processed_query("What is revenue?", normalized=True, decomposed=False, num_subqueries=0)
        collector.set_retrieval_mode("dense")
        collector.set_dense_candidates(5)
        collector.set_sparse_candidates(0)
        collector.set_hybrid_candidates(0)
        collector.set_context_selection(selected=3, dropped_budget=0, dropped_duplicate=0, dropped_low_similarity=0, total_chars=500)
        collector.set_citations(returned=3, validated=3)
        collector.set_embedding_duration(0.5)
        collector.set_retrieval_duration(0.3)
        collector.set_generation_duration(1.2)
        collector.set_status("success")

        diagnostics = collector.build()
        assert diagnostics.original_query == "What is revenue?"
        assert diagnostics.processed_query == "What is revenue?"
        assert diagnostics.retrieval_mode == "dense"
        assert diagnostics.dense_candidate_count == 5
        assert diagnostics.context_chunks_selected == 3
        assert diagnostics.citations_returned == 3
        assert diagnostics.status == "success"
        assert diagnostics.total_duration_seconds >= 0

    def test_collector_abstained_status(self):
        collector = DiagnosticsCollector(original_query="Unknown question")
        collector.set_processed_query("Unknown question")
        collector.set_retrieval_mode("dense")
        collector.set_dense_candidates(0)
        collector.set_context_selection(selected=0)
        collector.set_citations(returned=0, validated=0)
        collector.set_status("abstained", error_message="no_relevant_documents")

        diagnostics = collector.build()
        assert diagnostics.status == "abstained"
        assert diagnostics.error_message == "no_relevant_documents"

    def test_sanitize_for_logging(self):
        result = sanitize_for_logging("Hello\nWorld\tTest", max_chars=50)
        assert "\n" not in result
        assert "\t" not in result
        assert "Hello World Test" in result

    def test_sanitize_truncation(self):
        long_text = "x" * 200
        result = sanitize_for_logging(long_text, max_chars=50)
        assert len(result) <= 50
        assert result.endswith("...")

    def test_retrieval_diagnostics_to_dict(self):
        diagnostics = RetrievalDiagnostics(
            original_query="test query",
            processed_query="test query",
            query_normalized=True,
            query_decomposed=False,
            num_subqueries=0,
            retrieval_mode="dense",
            dense_candidate_count=3,
            sparse_candidate_count=0,
            hybrid_candidate_count=0,
            deduped_count=0,
        )
        d = diagnostics.to_dict()
        assert d["query"]["original"] == "test query"
        assert d["retrieval"]["mode"] == "dense"
        assert d["retrieval"]["dense_candidates"] == 3
        assert d["status"] == "success"
