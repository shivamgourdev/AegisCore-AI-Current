"""AEGISCORE_PHASE3_QUERY_PROCESSING
Advanced RAG Intelligence Engine — Query Processing Module.

Provides query normalization, validation, decomposition, and optional
expansion for the RAG question-answering pipeline. Reuses existing V1
validation patterns; does not duplicate business logic.

All functions are deterministic and safe for use with local Ollama models.
No paid APIs or external services are required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


MAX_QUERY_LENGTH = 5000
MIN_QUERY_LENGTH = 1

# Common English stop words used for query expansion and decomposition.
STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "to", "was", "were", "will", "with",
})


@dataclass(frozen=True)
class QueryConfig:
    """Configuration for query processing."""

    enable_expansion: bool = False
    enable_decomposition: bool = True
    max_subqueries: int = 5
    dense_weight: float = 0.6
    sparse_weight: float = 0.4
    min_similarity: float = 0.45
    max_query_length: int = MAX_QUERY_LENGTH


@dataclass(frozen=True)
class Subquery:
    """A decomposed subquery traceable to the original query."""

    subquery_id: str
    text: str
    source: str  # "original" or "decomposed"
    parent_query: str


@dataclass(frozen=True)
class ProcessedQuery:
    """Result of query processing pipeline."""

    original_query: str
    normalized_query: str
    subqueries: list[Subquery]
    expansion_terms: list[str]
    config: QueryConfig
    validation_errors: list[str] = field(default_factory=list)
    is_valid: bool = field(default_factory=lambda: True)


def normalize_query(query: str) -> str:
    """Normalize a query string.

    - Strips leading/trailing whitespace
    - Collapses internal whitespace runs to a single space
    - Preserves original casing (casing is semantically meaningful for
      proper nouns and acronyms)
    """
    if not isinstance(query, str):
        return ""
    # Collapse all whitespace runs (including tabs/newlines) to single space
    normalized = re.sub(r"\s+", " ", query.strip())
    return normalized


def validate_query(query: str, max_length: int = MAX_QUERY_LENGTH) -> list[str]:
    """Validate a query string.

    Returns a list of error messages. An empty list means the query is valid.
    """
    errors: list[str] = []

    if not isinstance(query, str):
        errors.append("query must be a string.")
        return errors

    if not query.strip():
        errors.append("query must be non-empty text.")
        return errors

    if len(query) > max_length:
        errors.append(
            f"query exceeds maximum length of {max_length} characters "
            f"({len(query)} characters provided)."
        )

    return errors


def decompose_query(
    query: str,
    max_subqueries: int = 5,
) -> list[Subquery]:
    """Decompose a complex multi-part question into subqueries.

    Uses simple heuristics (conjunctions, question marks) to split queries
    that contain multiple distinct information needs. Each subquery is
    traceable to the original query via ``parent_query``.

    Returns a list with the original query as the first element when no
    decomposition is possible.
    """
    if not query or not query.strip():
        return []

    normalized = normalize_query(query)
    subqueries: list[Subquery] = []

    # Split on sentence-ending punctuation followed by conjunctions,
    # or on standalone question marks that indicate separate questions.
    # Pattern: split on ";", " and ", " or ", " but ", " however ",
    # or question marks that are followed by more text.
    split_pattern = r"(?:\s+and\s+|\s+or\s+|\s+but\s+|\s+however\s+|;\s*|\?\s+(?=[A-Z]))"

    parts = re.split(split_pattern, normalized, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) <= 1:
        # No decomposition possible; return the original as a single subquery.
        return [
            Subquery(
                subquery_id="sq-0",
                text=normalized,
                source="original",
                parent_query=normalized,
            )
        ]

    for index, part in enumerate(parts[:max_subqueries]):
        subqueries.append(
            Subquery(
                subquery_id=f"sq-{index}",
                text=part,
                source="decomposed",
                parent_query=normalized,
            )
        )

    return subqueries


def expand_query(
    query: str,
    enable_expansion: bool = False,
) -> list[str]:
    """Optional synonym-based query expansion.

    Returns a list of expansion terms (not full expanded queries).
    Disabled by default to avoid changing query semantics unexpectedly.

    Expansion uses a small built-in synonym map for common business/technical
    terms. Terms not in the map produce no expansion.
    """
    if not enable_expansion or not query:
        return []

    normalized = normalize_query(query).casefold()
    tokens = re.findall(r"[a-z0-9]+", normalized)

    # Small synonym map for common terms. Kept minimal to avoid semantic drift.
    synonym_map: dict[str, list[str]] = {
        "revenue": ["income", "earnings", "sales"],
        "profit": ["earnings", "net income"],
        "engineer": ["developer", "programmer"],
        "python": ["python programming"],
        "sql": ["structured query language"],
        "ml": ["machine learning"],
        "ai": ["artificial intelligence"],
        "rag": ["retrieval augmented generation"],
        "api": ["application programming interface"],
    }

    expansion_terms: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        if token in STOP_WORDS:
            continue
        synonyms = synonym_map.get(token, [])
        for synonym in synonyms:
            if synonym not in seen:
                seen.add(synonym)
                expansion_terms.append(synonym)

    return expansion_terms


def process_query(
    query: str,
    config: QueryConfig | None = None,
) -> ProcessedQuery:
    """Run the full query processing pipeline.

    Steps:
    1. Validate the raw query.
    2. Normalize the query.
    3. Optionally decompose into subqueries.
    4. Optionally expand with synonyms.

    Returns a ProcessedQuery with all intermediate results and any
    validation errors. The caller should check ``is_valid`` before
    proceeding to retrieval.
    """
    if config is None:
        config = QueryConfig()

    validation_errors = validate_query(query, max_length=config.max_query_length)
    is_valid = len(validation_errors) == 0

    normalized = normalize_query(query) if is_valid else ""

    subqueries: list[Subquery] = []
    if is_valid and config.enable_decomposition:
        subqueries = decompose_query(normalized, max_subqueries=config.max_subqueries)

    expansion_terms: list[str] = []
    if is_valid and config.enable_expansion:
        expansion_terms = expand_query(normalized, enable_expansion=True)

    return ProcessedQuery(
        original_query=query,
        normalized_query=normalized,
        subqueries=subqueries,
        expansion_terms=expansion_terms,
        config=config,
        validation_errors=validation_errors,
        is_valid=is_valid,
    )


def build_retrieval_queries(
    processed: ProcessedQuery,
) -> list[tuple[str, float, float]]:
    """Build a list of (query_text, dense_weight, sparse_weight) tuples
    for retrieval.

    Uses the original (normalized) query as the primary retrieval query,
    plus any decomposed subqueries. Each query carries the configured
    dense/sparse weights for hybrid fusion.

    Expansion terms are not used as standalone queries; they are meant to
    be combined with the original query terms at retrieval time (future
    enhancement).
    """
    queries: list[tuple[str, float, float]] = []

    if not processed.is_valid or not processed.normalized_query:
        return queries

    # Primary query (normalized original)
    queries.append((
        processed.normalized_query,
        processed.config.dense_weight,
        processed.config.sparse_weight,
    ))

    # Decomposed subqueries (use same weights)
    for subquery in processed.subqueries:
        if subquery.source == "decomposed":
            queries.append((
                subquery.text,
                processed.config.dense_weight,
                processed.config.sparse_weight,
            ))

    return queries
