"""AEGISCORE_PHASE3_CONFIDENCE
Advanced RAG Intelligence Engine — Confidence Assessment.

Provides transparent confidence scoring based on actual retrieval evidence
(similarity scores, retrieval strategies, result counts, context coverage).
Does NOT pretend LLM-generated percentages are calibrated confidence.

Confidence levels: HIGH, MEDIUM, LOW, INSUFFICIENT.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConfidenceConfig:
    """Configuration for confidence assessment.

    Thresholds are configurable via environment variables:
    - AEGISCORE_CONFIDENCE_HIGH_THRESHOLD (default 0.70)
    - AEGISCORE_CONFIDENCE_MEDIUM_THRESHOLD (default 0.45)
    - AEGISCORE_CONFIDENCE_LOW_THRESHOLD (default 0.25)
    """

    high_threshold: float
    medium_threshold: float
    low_threshold: float
    min_chunks_for_high: int = 2
    min_docs_for_high: int = 1

    @classmethod
    def from_env(cls) -> "ConfidenceConfig":
        """Build config from environment variables with safe defaults."""
        return cls(
            high_threshold=float(
                os.environ.get("AEGISCORE_CONFIDENCE_HIGH_THRESHOLD", "0.70")
            ),
            medium_threshold=float(
                os.environ.get("AEGISCORE_CONFIDENCE_MEDIUM_THRESHOLD", "0.45")
            ),
            low_threshold=float(
                os.environ.get("AEGISCORE_CONFIDENCE_LOW_THRESHOLD", "0.25")
            ),
            min_chunks_for_high=int(
                os.environ.get("AEGISCORE_CONFIDENCE_MIN_CHUNKS_HIGH", "2")
            ),
            min_docs_for_high=int(
                os.environ.get("AEGISCORE_CONFIDENCE_MIN_DOCS_HIGH", "1")
            ),
        )


@dataclass(frozen=True)
class ConfidenceAssessment:
    """Transparent confidence assessment based on retrieval evidence."""

    level: str  # "high", "medium", "low", "insufficient"
    score: float  # 0.0 to 1.0
    explanation: str
    factors: dict[str, Any] = field(default_factory=dict)
    should_abstain: bool = False
    abstention_reason: str | None = None


def _similarity_factor(similarities: list[float]) -> float:
    """Compute similarity-based confidence factor (0.0 to 1.0).

    Uses the maximum similarity as the primary signal, dampened by
    the spread between top and second results.
    """
    if not similarities:
        return 0.0

    max_sim = max(similarities)
    if max_sim <= 0.0:
        return 0.0

    # Primary signal: max similarity, clamped to [0, 1]
    score = min(max_sim, 1.0)

    # Dampen if there's a large gap between top and second result
    # (indicates the top result may be an outlier)
    if len(similarities) >= 2:
        second_sim = sorted(similarities, reverse=True)[1]
        gap = max_sim - second_sim
        if gap > 0.3:
            # Large gap: reduce confidence slightly as top result may be an outlier
            score *= 0.9

    return score


def _coverage_factor(
    num_chunks: int,
    num_documents: int,
    min_chunks_for_high: int,
    min_docs_for_high: int,
) -> float:
    """Compute coverage-based confidence factor (0.0 to 1.0).

    More chunks and more documents increase confidence that the evidence
    is comprehensive.
    """
    if num_chunks == 0:
        return 0.0

    # Chunk coverage: fraction of desired chunks present
    chunk_score = min(num_chunks / max(min_chunks_for_high, 1), 1.0)

    # Document coverage: fraction of desired documents present
    doc_score = min(num_documents / max(min_docs_for_high, 1), 1.0)

    # Weighted combination
    return 0.6 * chunk_score + 0.4 * doc_score


def _strategy_factor(retrieval_strategies: list[str]) -> float:
    """Compute retrieval strategy diversity factor (0.0 to 1.0).

    Hybrid retrieval (dense + sparse) is more reliable than a single
    strategy because it combines semantic and lexical signals.
    """
    if not retrieval_strategies:
        return 0.5  # Unknown strategy: neutral

    unique_strategies = set(retrieval_strategies)
    if "dense" in unique_strategies and "sparse" in unique_strategies:
        return 1.0  # Hybrid: both semantic and lexical coverage
    if "dense" in unique_strategies or "sparse" in unique_strategies:
        return 0.7  # Single strategy: moderate confidence
    return 0.5  # Unknown: neutral


def assess_confidence(
    selected_chunks: list[dict[str, Any]],
    config: ConfidenceConfig | None = None,
) -> ConfidenceAssessment:
    """Assess confidence based on retrieval evidence.

    Factors considered:
    - Maximum similarity score (primary signal)
    - Number of chunks and documents (coverage)
    - Retrieval strategy diversity (dense + sparse = hybrid)
    - Similarity spread (outlier detection)

    Returns a ConfidenceAssessment with level, score, explanation,
    and abstention recommendation.
    """
    if config is None:
        config = ConfidenceConfig.from_env()

    if not selected_chunks:
        return ConfidenceAssessment(
            level="insufficient",
            score=0.0,
            explanation=(
                "No document chunks were retrieved. The uploaded documents "
                "do not contain evidence relevant to this question."
            ),
            should_abstain=True,
            abstention_reason="no_relevant_documents",
            factors={
                "num_chunks": 0,
                "num_documents": 0,
                "max_similarity": 0.0,
                "retrieval_strategies": [],
            },
        )

    similarities = [float(c.get("similarity", 0.0)) for c in selected_chunks]
    max_similarity = max(similarities) if similarities else 0.0
    num_chunks = len(selected_chunks)
    num_documents = len({str(c.get("filename", "unknown")) for c in selected_chunks})
    retrieval_strategies: list[str] = []
    for c in selected_chunks:
        strategies = c.get("strategies") or []
        if isinstance(strategies, list):
            retrieval_strategies.extend(strategies)
        strategy = c.get("retrieval_strategy")
        if strategy and strategy not in retrieval_strategies:
            retrieval_strategies.append(strategy)

    # Compute factor scores
    sim_score = _similarity_factor(similarities)
    coverage_score = _coverage_factor(
        num_chunks,
        num_documents,
        config.min_chunks_for_high,
        config.min_docs_for_high,
    )
    strategy_score = _strategy_factor(retrieval_strategies)

    # Weighted combination: similarity is the primary signal (50%),
    # coverage is secondary (30%), strategy diversity is tertiary (20%)
    overall_score = round(
        0.50 * sim_score + 0.30 * coverage_score + 0.20 * strategy_score,
        3,
    )

    # Determine level
    if overall_score >= config.high_threshold:
        level = "high"
        should_abstain = False
        abstention_reason = None
        explanation = (
            f"High confidence: {num_chunks} chunk(s) from {num_documents}"
            f" document{'s' if num_documents != 1 else ''} retrieved with "
            f"strong similarity (max {max_similarity:.2f})."
        )
    elif overall_score >= config.medium_threshold:
        level = "medium"
        should_abstain = False
        abstention_reason = None
        explanation = (
            f"Medium confidence: {num_chunks} chunk(s) retrieved with "
            f"moderate similarity (max {max_similarity:.2f}). Answer may "
            f"be partially supported."
        )
    elif overall_score >= config.low_threshold:
        level = "low"
        should_abstain = False
        abstention_reason = None
        explanation = (
            f"Low confidence: {num_chunks} chunk(s) retrieved with weak "
            f"similarity (max {max_similarity:.2f}). Evidence is limited."
        )
    else:
        level = "insufficient"
        should_abstain = True
        abstention_reason = "insufficient_evidence"
        explanation = (
            f"Insufficient evidence: {num_chunks} chunk(s) retrieved with "
            f"very low similarity (max {max_similarity:.2f}). The uploaded "
            f"documents do not contain evidence that answers this question."
        )

    return ConfidenceAssessment(
        level=level,
        score=overall_score,
        explanation=explanation,
        factors={
            "num_chunks": num_chunks,
            "num_documents": num_documents,
            "max_similarity": round(max_similarity, 3),
            "retrieval_strategies": sorted(set(retrieval_strategies)),
            "similarity_score": round(sim_score, 3),
            "coverage_score": round(coverage_score, 3),
            "strategy_score": round(strategy_score, 3),
        },
        should_abstain=should_abstain,
        abstention_reason=abstention_reason,
    )


def combine_confidence_and_support(
    confidence_score: float,
    support_assessment: SupportAssessment,
) -> tuple[float, str]:
    """Combine confidence score with support assessment.

    Returns (adjusted_score, adjusted_level).

    The confidence score is adjusted downward for partial support and
    unsupported answers. The level is recalculated based on the adjusted
    score.
    """
    adjusted_score = max(0.0, min(1.0, confidence_score + support_assessment.confidence_adjustment))

    if support_assessment.should_abstain:
        return adjusted_score, "insufficient"
    if adjusted_score >= 0.70:
        return adjusted_score, "high"
    if adjusted_score >= 0.45:
        return adjusted_score, "medium"
    if adjusted_score >= 0.25:
        return adjusted_score, "low"
    return adjusted_score, "insufficient"
