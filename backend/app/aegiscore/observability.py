"""AEGISCORE_PHASE3_OBSERVABILITY
Advanced RAG Intelligence Engine — Retrieval Observability.

Provides structured diagnostics for the RAG retrieval pipeline, tracking
every stage from query processing through citation validation. All data
is safe for logging (no secrets, no full document content).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """Structured diagnostics for a single RAG retrieval operation.

    All fields are safe for logging. No document content, secrets, or
    personal data is included.
    """

    # Query information
    original_query: str
    processed_query: str
    query_normalized: bool
    query_decomposed: bool
    num_subqueries: int

    # Retrieval stage information
    retrieval_mode: str  # "dense", "sparse", "hybrid"
    dense_candidate_count: int = 0
    sparse_candidate_count: int = 0
    hybrid_candidate_count: int = 0
    deduped_count: int = 0

    # Reranking information
    reranking_enabled: bool = False
    reranking_applied: bool = False
    reranking_skipped_reason: str | None = None

    # Context selection information
    context_chunks_selected: int = 0
    context_chunks_dropped_budget: int = 0
    context_chunks_dropped_duplicate: int = 0
    context_chunks_dropped_low_similarity: int = 0
    context_total_chars: int = 0
    context_truncated: bool = False

    # Citation validation information
    citations_returned: int = 0
    citations_validated: int = 0
    citation_validation_failures: int = 0

    # Performance and failure information
    total_duration_seconds: float = 0.0
    embedding_duration_seconds: float | None = None
    retrieval_duration_seconds: float | None = None
    generation_duration_seconds: float | None = None

    # Failure and fallback information
    status: str = "success"  # "success", "abstained", "failed", "fallback"
    error_message: str | None = None
    fallback_reason: str | None = None
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dictionary for JSON serialization/API response."""
        return {
            "query": {
                "original": self.original_query,
                "processed": self.processed_query,
                "normalized": self.query_normalized,
                "decomposed": self.query_decomposed,
                "num_subqueries": self.num_subqueries,
            },
            "retrieval": {
                "mode": self.retrieval_mode,
                "dense_candidates": self.dense_candidate_count,
                "sparse_candidates": self.sparse_candidate_count,
                "hybrid_candidates": self.hybrid_candidate_count,
                "deduped": self.deduped_count,
            },
            "reranking": {
                "enabled": self.reranking_enabled,
                "applied": self.reranking_applied,
                "skipped_reason": self.reranking_skipped_reason,
            },
            "context": {
                "chunks_selected": self.context_chunks_selected,
                "chunks_dropped_budget": self.context_chunks_dropped_budget,
                "chunks_dropped_duplicate": self.context_chunks_dropped_duplicate,
                "chunks_dropped_low_similarity": self.context_chunks_dropped_low_similarity,
                "total_chars": self.context_total_chars,
                "truncated": self.context_truncated,
            },
            "citations": {
                "returned": self.citations_returned,
                "validated": self.citations_validated,
                "validation_failures": self.citation_validation_failures,
            },
            "performance": {
                "total_duration_seconds": self.total_duration_seconds,
                "embedding_duration_seconds": self.embedding_duration_seconds,
                "retrieval_duration_seconds": self.retrieval_duration_seconds,
                "generation_duration_seconds": self.generation_duration_seconds,
            },
            "status": self.status,
            "error": self.error_message,
            "fallback": {
                "used": self.fallback_used,
                "reason": self.fallback_reason,
            },
        }


class DiagnosticsCollector:
    """Accumulates diagnostics throughout a RAG retrieval operation.

    Usage:
        collector = DiagnosticsCollector(original_query="...")
        collector.set_processed_query("...")
        collector.set_retrieval_mode("hybrid")
        collector.set_dense_candidates(10)
        ...
        diagnostics = collector.build(status="success")
    """

    def __init__(self, original_query: str) -> None:
        self._start_time = time.monotonic()
        self._original_query = original_query
        self._processed_query = original_query
        self._query_normalized = False
        self._query_decomposed = False
        self._num_subqueries = 0
        self._retrieval_mode = "dense"
        self._dense_candidates = 0
        self._sparse_candidates = 0
        self._hybrid_candidates = 0
        self._deduped_count = 0
        self._reranking_enabled = False
        self._reranking_applied = False
        self._reranking_skipped_reason: str | None = None
        self._context_chunks_selected = 0
        self._context_chunks_dropped_budget = 0
        self._context_chunks_dropped_duplicate = 0
        self._context_chunks_dropped_low_similarity = 0
        self._context_total_chars = 0
        self._context_truncated = False
        self._citations_returned = 0
        self._citations_validated = 0
        self._citation_validation_failures = 0
        self._embedding_duration: float | None = None
        self._retrieval_duration: float | None = None
        self._generation_duration: float | None = None
        self._status = "success"
        self._error_message: str | None = None
        self._fallback_used = False
        self._fallback_reason: str | None = None

    def set_processed_query(
        self, query: str, normalized: bool = False, decomposed: bool = False, num_subqueries: int = 0
    ) -> None:
        self._processed_query = query
        self._query_normalized = normalized
        self._query_decomposed = decomposed
        self._num_subqueries = num_subqueries

    def set_retrieval_mode(self, mode: str) -> None:
        self._retrieval_mode = mode

    def set_dense_candidates(self, count: int) -> None:
        self._dense_candidates = count

    def set_sparse_candidates(self, count: int) -> None:
        self._sparse_candidates = count

    def set_hybrid_candidates(self, count: int) -> None:
        self._hybrid_candidates = count

    def set_deduped_count(self, count: int) -> None:
        self._deduped_count = count

    def set_reranking(self, enabled: bool, applied: bool, skipped_reason: str | None = None) -> None:
        self._reranking_enabled = enabled
        self._reranking_applied = applied
        self._reranking_skipped_reason = skipped_reason

    def set_context_selection(
        self,
        selected: int,
        dropped_budget: int = 0,
        dropped_duplicate: int = 0,
        dropped_low_similarity: int = 0,
        total_chars: int = 0,
        truncated: bool = False,
    ) -> None:
        self._context_chunks_selected = selected
        self._context_chunks_dropped_budget = dropped_budget
        self._context_chunks_dropped_duplicate = dropped_duplicate
        self._context_chunks_dropped_low_similarity = dropped_low_similarity
        self._context_total_chars = total_chars
        self._context_truncated = truncated

    def set_citations(
        self, returned: int, validated: int, validation_failures: int = 0
    ) -> None:
        self._citations_returned = returned
        self._citations_validated = validated
        self._citation_validation_failures = validation_failures

    def set_embedding_duration(self, seconds: float) -> None:
        self._embedding_duration = seconds

    def set_retrieval_duration(self, seconds: float) -> None:
        self._retrieval_duration = seconds

    def set_generation_duration(self, seconds: float) -> None:
        self._generation_duration = seconds

    def set_status(
        self,
        status: str,
        error_message: str | None = None,
        fallback_used: bool = False,
        fallback_reason: str | None = None,
    ) -> None:
        self._status = status
        self._error_message = error_message
        self._fallback_used = fallback_used
        self._fallback_reason = fallback_reason

    def build(self) -> RetrievalDiagnostics:
        total_duration = time.monotonic() - self._start_time
        return RetrievalDiagnostics(
            original_query=self._original_query,
            processed_query=self._processed_query,
            query_normalized=self._query_normalized,
            query_decomposed=self._query_decomposed,
            num_subqueries=self._num_subqueries,
            retrieval_mode=self._retrieval_mode,
            dense_candidate_count=self._dense_candidates,
            sparse_candidate_count=self._sparse_candidates,
            hybrid_candidate_count=self._hybrid_candidates,
            deduped_count=self._deduped_count,
            reranking_enabled=self._reranking_enabled,
            reranking_applied=self._reranking_applied,
            reranking_skipped_reason=self._reranking_skipped_reason,
            context_chunks_selected=self._context_chunks_selected,
            context_chunks_dropped_budget=self._context_chunks_dropped_budget,
            context_chunks_dropped_duplicate=self._context_chunks_dropped_duplicate,
            context_chunks_dropped_low_similarity=self._context_chunks_dropped_low_similarity,
            context_total_chars=self._context_total_chars,
            context_truncated=self._context_truncated,
            citations_returned=self._citations_returned,
            citations_validated=self._citations_validated,
            citation_validation_failures=self._citation_validation_failures,
            total_duration_seconds=round(total_duration, 4),
            embedding_duration_seconds=(
                round(self._embedding_duration, 4) if self._embedding_duration is not None else None
            ),
            retrieval_duration_seconds=(
                round(self._retrieval_duration, 4) if self._retrieval_duration is not None else None
            ),
            generation_duration_seconds=(
                round(self._generation_duration, 4) if self._generation_duration is not None else None
            ),
            status=self._status,
            error_message=self._error_message,
            fallback_used=self._fallback_used,
            fallback_reason=self._fallback_reason,
        )


def sanitize_for_logging(text: str, max_chars: int = 100) -> str:
    """Sanitize text for safe logging.

    Truncates to max_chars and replaces newlines with spaces. Does NOT
    include full document content or sensitive data.
    """
    if not isinstance(text, str):
        return str(text)
    sanitized = text.replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()
    if len(sanitized) > max_chars:
        sanitized = sanitized[: max_chars - 3] + "..."
    return sanitized
