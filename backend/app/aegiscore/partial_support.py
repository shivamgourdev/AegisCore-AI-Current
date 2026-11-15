"""AEGISCORE_PHASE3_PARTIAL_SUPPORT
Advanced RAG Intelligence Engine — Partial Support Detection.

Detects whether a generated answer is fully supported, partially supported,
or unsupported by the retrieved evidence. Validates citation-to-chunk
mapping and identifies uncited factual claims.

All functions are deterministic and do not require external NLP models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# Patterns for factual claims that should be cited
FACTUAL_PATTERNS = [
    # Numbers with units (e.g., "42 million", "6 engineers", "$1.5B")
    r"\b\d[\d,]*(\.\d+)?\s*(million|billion|thousand|percent|%|\$|engineers|employees|people|dollars|years|months|days)\b",
    # Years (e.g., "2024", "Q3 2024")
    r"\b(19|20)\d{2}\b",
    # Quarter references (e.g., "Q3", "Q1 2024")
    r"\b[Qq][1-4]\s*\d{0,4}\b",
    # Proper noun phrases (e.g., "Project Orion", "Sarah Connor")
    r"\b[A-Z][a-z]+(\s+[A-Z][a-z]+)+\b",
    # Single capitalized proper names (e.g., "Sarah", "Orion")
    # Only match when mid-sentence (preceded by whitespace) to avoid
    # matching sentence-initial words like "The", "And", "But"
    r"(?<=\s)[A-Z][a-z]{3,}\b",
]


@dataclass(frozen=True)
class SupportAssessment:
    """Result of partial support detection."""

    support_level: str  # "fully_supported", "partially_supported", "unsupported"
    confidence_adjustment: float  # Adjustment to confidence score (-0.3 to 0.0)
    uncited_claims: list[str] = field(default_factory=list)
    valid_citations: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    uncited_factual_patterns: list[str] = field(default_factory=list)
    explanation: str = ""
    should_abstain: bool = False


def _extract_citation_tokens(answer: str) -> list[str]:
    """Extract all [S{N}] citation tokens from an answer."""
    return re.findall(r"\[(S\d+)\]", answer)


def _extract_factual_claims(answer: str) -> list[str]:
    """Extract potential factual claims from an answer.

    Looks for numbers with units, years, quarter references, and proper
    noun phrases that should be backed by citations.
    """
    claims: list[str] = []
    for pattern in FACTUAL_PATTERNS:
        for match in re.finditer(pattern, answer):
            claims.append(match.group(0))
    return claims


def _claim_supported_by_sources(claim: str, sources: list[dict[str, Any]]) -> bool:
    """Check if a claim is supported by any of the cited source texts.

    Uses simple word overlap: if any significant word from the claim
    appears in any cited source text, the claim is considered potentially
    supported.
    """
    claim_words = set(re.findall(r"[A-Za-z0-9]{3,}", claim.casefold()))
    claim_words -= STOP_WORDS

    if not claim_words:
        return True  # Can't determine, assume supported

    for source in sources:
        source_text = source.get("text", "").casefold()
        source_words = set(re.findall(r"[A-Za-z0-9]{3,}", source_text))
        if claim_words & source_words:
            return True

    return False


# Stop words for claim word filtering
STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "to", "was", "were", "will", "with",
    "the", "this", "that", "these", "those",
})


def assess_support(
    answer: str,
    citations: list[dict[str, Any]],
    available_source_ids: list[str],
) -> SupportAssessment:
    """Assess whether an answer is supported by the retrieved evidence.

    Args:
        answer: The generated answer text.
        citations: List of citation dicts with 'source_id', 'filename',
            'page_number', 'text', 'similarity'.
        available_source_ids: List of valid source IDs from retrieval.

    Returns:
        SupportAssessment with support_level, explanation,
        uncited_claims, valid_citations, and should_abstain.
    """
    if not answer or not answer.strip():
        return SupportAssessment(
            support_level="unsupported",
            confidence_adjustment=-0.3,
            explanation="The model returned an empty answer.",
            should_abstain=True,
        )

    citation_tokens = _extract_citation_tokens(answer)
    valid_ids = set(available_source_ids)
    cited_ids = set(citation_tokens)

    # Validate citation IDs
    valid_citations = [cid for cid in cited_ids if cid in valid_ids]
    invalid_citations = [cid for cid in cited_ids if cid not in valid_ids]

    # Extract factual claims that should be cited
    factual_claims = _extract_factual_claims(answer)

    # Check which factual claims are supported by cited sources
    uncited_claims: list[str] = []
    for claim in factual_claims:
        if not _claim_supported_by_sources(claim, citations):
            uncited_claims.append(claim)

    # Determine support level
    if not citation_tokens:
        # No citations at all
        if factual_claims:
            return SupportAssessment(
                support_level="unsupported",
                confidence_adjustment=-0.3,
                explanation=(
                    f"The answer contains {len(factual_claims)} factual claim(s) "
                    f"but provides no citations. Unsupported claims: "
                    f"{', '.join(uncited_claims[:3])}"
                ),
                uncited_claims=uncited_claims,
                should_abstain=True,
            )
        # No factual claims - could be a safe non-factual answer
        return SupportAssessment(
            support_level="fully_supported",
            confidence_adjustment=0.0,
            explanation="No factual claims detected; no citations required.",
            should_abstain=False,
        )

    # Has citations
    if invalid_citations:
        # Invalid citations present - fail closed
        return SupportAssessment(
            support_level="unsupported",
            confidence_adjustment=-0.3,
            explanation=(
                f"Invalid citation(s): {', '.join(invalid_citations)}. "
                f"Citations must refer to retrieved sources."
            ),
            invalid_citations=invalid_citations,
            should_abstain=True,
        )

    if uncited_claims:
        # Some claims are uncited - partially supported
        return SupportAssessment(
            support_level="partially_supported",
            confidence_adjustment=-0.15,
            explanation=(
                f"{len(uncited_claims)} factual claim(s) lack citations: "
                f"{', '.join(uncited_claims[:3])}"
            ),
            uncited_claims=uncited_claims,
            valid_citations=valid_citations,
            should_abstain=False,
        )

    # All claims cited with valid citations
    return SupportAssessment(
        support_level="fully_supported",
        confidence_adjustment=0.0,
        explanation=(
            f"All {len(citation_tokens)} citation(s) reference valid sources. "
            f"No uncited factual claims detected."
        ),
        valid_citations=valid_citations,
        should_abstain=False,
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
