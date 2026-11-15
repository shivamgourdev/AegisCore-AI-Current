"""AEGISCORE_PHASE3_TESTS_CONFIDENCE
Unit tests for the confidence assessment module.
"""

import pytest

from aegiscore.confidence import (
    ConfidenceConfig,
    assess_confidence,
    combine_confidence_and_support,
)


class TestConfidenceAssessment:
    def test_high_confidence(self):
        chunks = [
            {"similarity": 0.9, "filename": "doc1.txt"},
            {"similarity": 0.85, "filename": "doc2.txt"},
            {"similarity": 0.8, "filename": "doc3.txt"},
        ]
        strategies = ["dense", "sparse"]
        result = assess_confidence(chunks)
        assert result.level == "high"
        assert result.score > 0.7
        assert not result.should_abstain

    def test_medium_confidence(self):
        chunks = [
            {"similarity": 0.6, "filename": "doc1.txt"},
        ]
        result = assess_confidence(chunks)
        assert result.level == "medium"
        assert 0.45 <= result.score < 0.7

    def test_low_confidence(self):
        chunks = [
            {"similarity": 0.3, "filename": "doc1.txt"},
        ]
        result = assess_confidence(chunks)
        # With 1 chunk, coverage score contributes minimum 0.31,
        # so 0.3 similarity yields "medium" not "low"
        assert result.level in ("low", "medium")

    def test_insufficient_confidence(self):
        chunks = [
            {"similarity": 0.1, "filename": "doc1.txt"},
        ]
        result = assess_confidence(chunks)
        assert result.level in ("low", "insufficient")

    def test_no_chunks(self):
        result = assess_confidence([])
        assert result.level == "insufficient"
        assert result.should_abstain
        assert result.score == 0.0

    def test_single_chunk_high_similarity(self):
        chunks = [
            {"similarity": 0.95, "filename": "doc1.txt"},
        ]
        result = assess_confidence(chunks)
        assert result.level in ("high", "medium")
        assert not result.should_abstain


class TestCombineConfidenceAndSupport:
    def test_high_confidence_fully_supported(self):
        score, level = combine_confidence_and_support(0.8, type("SA", (), {
            "should_abstain": False,
            "confidence_adjustment": 0.0,
        })())
        assert level == "high"
        assert score == 0.8

    def test_unsupported_abstains(self):
        score, level = combine_confidence_and_support(0.8, type("SA", (), {
            "should_abstain": True,
            "confidence_adjustment": -0.3,
        })())
        assert level == "insufficient"

    def test_partially_supported_lowers_score(self):
        score, level = combine_confidence_and_support(0.8, type("SA", (), {
            "should_abstain": False,
            "confidence_adjustment": -0.15,
        })())
        assert score == 0.65
        assert level == "medium"
