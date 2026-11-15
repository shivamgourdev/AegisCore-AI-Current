"""AEGISCORE_PHASE3_CONTEXT_SELECTOR
Advanced RAG Intelligence Engine — Context Selection and Budget Management.

Provides context budget management, duplicate/redundant chunk reduction,
source diversity, and context overflow protection for RAG question-answering.
All functions are deterministic and operate on retrieved chunk dictionaries
produced by the existing retrieval pipeline (dense/sparse/hybrid).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextConfig:
    """Configuration for context selection and budget management."""

    max_context_chars: int = 4000
    max_chunks: int = 10
    min_similarity: float = 0.0
    enable_source_diversity: bool = True
    max_chunks_per_document: int = 3
    near_duplicate_threshold: float = 0.85


@dataclass(frozen=True)
class SelectedChunk:
    """A chunk selected for context, with source metadata."""

    source_id: str
    filename: str
    page_number: int | None
    chunk_index: int
    text: str
    similarity: float
    retrieval_strategy: str | None = None
    strategies: list[str] | None = None
    char_count: int = 0


@dataclass(frozen=True)
class ContextSelectionResult:
    """Result of context selection."""

    selected_chunks: list[SelectedChunk]
    total_chars: int
    total_chunks: int
    documents_represented: int
    truncated: bool
    dropped_due_to_budget: int
    dropped_duplicates: int
    dropped_low_similarity: int


def _simple_hash(text: str) -> str:
    """Return a short hash of normalized text for near-duplicate detection."""
    normalized = re.sub(r"\s+", " ", text.strip().casefold())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _text_similarity(text_a: str, text_b: str) -> float:
    """Simple character-overlap similarity (Jaccard on character 3-grams).

    Used only for near-duplicate detection, not semantic similarity.
    """
    if not text_a or not text_b:
        return 0.0

    def _trigrams(text: str) -> set[str]:
        t = re.sub(r"\s+", " ", text.strip().casefold())
        return {t[i : i + 3] for i in range(max(0, len(t) - 2))}

    set_a = _trigrams(text_a)
    set_b = _trigrams(text_b)

    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


def select_context(
    chunks: list[dict[str, Any]],
    config: ContextConfig | None = None,
) -> ContextSelectionResult:
    """Select and rank chunks for context within a character budget.

    Pipeline:
    1. Filter by minimum similarity threshold.
    2. Remove exact duplicates (same text_sha256).
    3. Remove near-duplicates (character 3-gram Jaccard >= threshold).
    4. Apply source diversity (max chunks per document).
    5. Order by similarity (highest first).
    6. Truncate to character budget (preserve highest-relevance chunks).

    Args:
        chunks: List of chunk dicts with keys: source_id, filename,
            page_number, chunk_index, text, similarity, retrieval_strategy,
            strategies, char_count, text_sha256.
        config: ContextConfig with budget and diversity settings.

    Returns:
        ContextSelectionResult with selected chunks and statistics.
    """
    if config is None:
        config = ContextConfig()

    # Step 1: Filter by minimum similarity
    filtered: list[dict[str, Any]] = []
    dropped_low_similarity = 0
    for item in chunks:
        similarity = float(item.get("similarity", 0.0))
        if similarity >= config.min_similarity:
            filtered.append(item)
        else:
            dropped_low_similarity += 1

    # Step 2: Remove exact duplicates by text_sha256
    seen_hashes: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in filtered:
        text_hash = item.get("text_sha256") or _simple_hash(item.get("text", ""))
        if text_hash not in seen_hashes:
            seen_hashes.add(text_hash)
            deduped.append(item)

    # Step 3: Remove near-duplicates by character 3-gram Jaccard
    near_duplicate_hashes: set[str] = set()
    diverse_chunks: list[dict[str, Any]] = []
    dropped_duplicates = 0
    for item in deduped:
        text = item.get("text", "")
        text_hash = _simple_hash(text)
        is_duplicate = False
        for existing_hash in near_duplicate_hashes:
            # We need actual text comparison; store texts alongside hashes
            pass
        # Simpler approach: compare against already-accepted texts
        is_dup = False
        for existing in diverse_chunks:
            existing_text = existing.get("text", "")
            if _text_similarity(text, existing_text) >= config.near_duplicate_threshold:
                is_dup = True
                break
        if not is_dup:
            near_duplicate_hashes.add(text_hash)
            diverse_chunks.append(item)
        else:
            dropped_duplicates += 1

    # Step 4: Apply source diversity (max chunks per document)
    doc_chunk_counts: dict[str, int] = {}
    diversified: list[dict[str, Any]] = []
    for item in diverse_chunks:
        doc_id = item.get("document_id", item.get("filename", "unknown"))
        count = doc_chunk_counts.get(doc_id, 0)
        if count < config.max_chunks_per_document:
            doc_chunk_counts[doc_id] = count + 1
            diversified.append(item)

    # Step 5: Order by similarity (highest first)
    diversified.sort(
        key=lambda item: float(item.get("similarity", 0.0)),
        reverse=True,
    )

    # Step 6: Truncate to character budget
    selected: list[SelectedChunk] = []
    total_chars = 0
    truncated = False
    dropped_due_to_budget = 0

    for item in diversified:
        text = item.get("text", "")
        char_count = int(item.get("char_count", len(text)))

        if total_chars + char_count > config.max_context_chars:
            truncated = True
            dropped_due_to_budget += 1
            continue

        if len(selected) >= config.max_chunks:
            truncated = True
            dropped_due_to_budget += 1
            continue

        selected.append(
            SelectedChunk(
                source_id=str(item.get("source_id", "unknown")),
                filename=str(item.get("filename", "unknown")),
                page_number=item.get("page_number"),
                chunk_index=int(item.get("chunk_index", 0)),
                text=text,
                similarity=float(item.get("similarity", 0.0)),
                retrieval_strategy=item.get("retrieval_strategy"),
                strategies=item.get("strategies"),
                char_count=char_count,
            )
        )
        total_chars += char_count

    documents_represented = len(
        {c.filename for c in selected}
    )

    return ContextSelectionResult(
        selected_chunks=selected,
        total_chars=total_chars,
        total_chunks=len(selected),
        documents_represented=documents_represented,
        truncated=truncated,
        dropped_due_to_budget=dropped_due_to_budget,
        dropped_duplicates=dropped_duplicates,
        dropped_low_similarity=dropped_low_similarity,
    )


def build_context_text(
    selected_chunks: list[SelectedChunk],
    max_chars_per_chunk: int = 1000,
) -> str:
    """Build a context string from selected chunks with source citations.

    Each chunk is prefixed with its source ID and truncated to
    max_chars_per_chunk to prevent any single chunk from dominating.
    """
    parts: list[str] = []
    for chunk in selected_chunks:
        text = chunk.text
        if len(text) > max_chars_per_chunk:
            text = text[: max_chars_per_chunk - 3] + "..."
        page_info = f"page {chunk.page_number}" if chunk.page_number is not None else "page unknown"
        parts.append(
            f"[{chunk.source_id}] File: {chunk.filename}; {page_info}\n"
            f"Evidence: {text}"
        )
    return "\n\n".join(parts)
