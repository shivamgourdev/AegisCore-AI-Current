"""AEGISCORE_PART4C_SPARSE
BM25 sparse lexical retrieval over persisted document chunks.
"""

import math
import re
import sqlite3
from collections import Counter
from typing import Any

from aegiscore.document_service import _database_connection


def _tokenize(text: str) -> list[str]:
    """Lowercase and split text into alphanumeric tokens."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25_score(
    query_terms: list[str],
    doc_tokens: list[str],
    doc_count: int,
    avg_doc_len: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Compute BM25 score for one document against a query."""
    if not query_terms or not doc_tokens:
        return 0.0

    doc_len = len(doc_tokens)
    term_counts = Counter(doc_tokens)
    score = 0.0

    for term in query_terms:
        n = sum(
            1
            for _ in [0]
            if term in term_counts
        )
        if n == 0:
            continue

        # IDF: Robertson-Sparck Jones variant
        idf = math.log((doc_count - n + 0.5) / (n + 0.5) + 1.0)

        tf = term_counts[term]
        numerator = tf * (k1 + 1.0)
        denominator = tf + k1 * (1.0 - b + b * (doc_len / avg_doc_len))
        score += idf * (numerator / denominator)

    return score


def search_sparse_chunks(
    query: str,
    top_k: int = 5,
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    """Rank persisted chunks by BM25 lexical relevance.

    Falls back gracefully when no chunks are indexed. Returns chunks with
    source metadata and a ``similarity`` field holding the BM25 score.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty text.")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 50:
        raise ValueError("top_k must be an integer between 1 and 50.")

    connection = _database_connection()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                text_sha256 TEXT NOT NULL,
                UNIQUE(document_id, page_number, chunk_index),
                FOREIGN KEY(document_id) REFERENCES documents(document_id)
            )
            """
        )

        if model_name:
            rows = connection.execute("""
                SELECT c.chunk_id, c.document_id, c.filename, c.page_number,
                       c.chunk_index, c.text
                FROM document_chunks c
                ORDER BY c.page_number, c.chunk_index
            """).fetchall()
        else:
            rows = connection.execute("""
                SELECT c.chunk_id, c.document_id, c.filename, c.page_number,
                       c.chunk_index, c.text
                FROM document_chunks c
                ORDER BY c.page_number, c.chunk_index
            """).fetchall()

        if not rows:
            return []

        query_terms = _tokenize(query)
        doc_count = len(rows)
        tokenized_docs = [_tokenize(row["text"]) for row in rows]
        avg_doc_len = sum(len(d) for d in tokenized_docs) / doc_count

        scored = []
        for row, tokens in zip(rows, tokenized_docs):
            score = _bm25_score(query_terms, tokens, doc_count, avg_doc_len)
            if score > 0:
                scored.append({
                    "chunk_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "filename": row["filename"],
                    "page_number": row["page_number"],
                    "chunk_index": row["chunk_index"],
                    "text": row["text"],
                    "model": "bm25",
                    "similarity": float(score),
                    "retrieval_strategy": "sparse",
                })

        scored.sort(key=lambda item: item["similarity"], reverse=True)
        return scored[:top_k]
    finally:
        connection.close()


def hybrid_search(
    query: str,
    dense_results: list[dict[str, Any]],
    sparse_results: list[dict[str, Any]],
    top_k: int = 5,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse dense and sparse results using Reciprocal Rank Fusion.

    Each result must carry a ``chunk_id`` for deduplication. RRF score:
    sum over strategies of 1 / (rrf_k + rank).
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty text.")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 50:
        raise ValueError("top_k must be an integer between 1 and 50.")

    fused: dict[str, dict[str, Any]] = {}
    strategies: dict[str, set[str]] = {}

    for rank, item in enumerate(dense_results, start=1):
        chunk_id = item.get("chunk_id")
        if not chunk_id:
            continue
        if chunk_id not in fused:
            fused[chunk_id] = dict(item)
            fused[chunk_id]["rrf_score"] = 0.0
            fused[chunk_id]["retrieval_strategies"] = []
            strategies[chunk_id] = set()
        fused[chunk_id]["rrf_score"] += 1.0 / (rrf_k + rank)
        fused[chunk_id]["retrieval_strategies"].append("dense")
        strategies[chunk_id].add("dense")

    for rank, item in enumerate(sparse_results, start=1):
        chunk_id = item.get("chunk_id")
        if not chunk_id:
            continue
        if chunk_id not in fused:
            fused[chunk_id] = dict(item)
            fused[chunk_id]["rrf_score"] = 0.0
            fused[chunk_id]["retrieval_strategies"] = []
            strategies[chunk_id] = set()
        fused[chunk_id]["rrf_score"] += 1.0 / (rrf_k + rank)
        if "sparse" not in fused[chunk_id]["retrieval_strategies"]:
            fused[chunk_id]["retrieval_strategies"].append("sparse")
        strategies[chunk_id].add("sparse")

    for chunk_id in fused:
        # Normalize RRF score to a 0-1 scale comparable to cosine similarity.
        # Max theoretical RRF (rank 1 in both strategies) is 2 / (rrf_k + 1).
        max_rrf = 2.0 / (rrf_k + 1.0)
        normalized = min(fused[chunk_id]["rrf_score"] / max_rrf, 1.0)
        fused[chunk_id]["similarity"] = normalized
        fused[chunk_id]["retrieval_strategy"] = "hybrid"
        fused[chunk_id]["strategies"] = sorted(strategies[chunk_id])

    ranked = sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)
    return ranked[:top_k]
