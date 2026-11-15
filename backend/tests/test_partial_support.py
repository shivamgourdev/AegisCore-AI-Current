"""AEGISCORE_PHASE3_TESTS_PARTIAL_SUPPORT
Unit tests for the partial support detection module.
"""

import pytest

from aegiscore.partial_support import (
    assess_support,
    combine_confidence_and_support,
)


class TestAssessSupport:
    def test_fully_supported(self):
        result = assess_support(
            "Revenue was 42 million [S1].",
            [{"source_id": "S1", "filename": "doc1.txt", "text": "Revenue was 42 million.", "similarity": 0.9}],
            ["S1"],
        )
        assert result.support_level == "fully_supported"
        assert not result.should_abstain
        assert len(result.uncited_claims) == 0

    def test_unsupported_no_citations(self):
        result = assess_support(
            "Revenue was 42 million dollars.",
            [],
            [],
        )
        assert result.support_level == "unsupported"
        assert result.should_abstain
        assert len(result.uncited_claims) > 0

    def test_invalid_citation(self):
        result = assess_support(
            "Revenue was 42 million [S99].",
            [{"source_id": "S1", "filename": "doc1.txt", "text": "Revenue was 42 million.", "similarity": 0.9}],
            ["S1"],
        )
        assert result.support_level == "unsupported"
        assert result.should_abstain
        assert "S99" in result.invalid_citations

    def test_partially_supported(self):
        result = assess_support(
            "Revenue was 42 million [S1]. The CEO is Sarah.",
            [{"source_id": "S1", "filename": "doc1.txt", "text": "Revenue was 42 million.", "similarity": 0.9}],
            ["S1"],
        )
        assert result.support_level == "partially_supported"
        assert not result.should_abstain
        assert len(result.uncited_claims) > 0  # "Sarah" is uncited

    def test_empty_answer(self):
        result = assess_support("", [], [])
        assert result.support_level == "unsupported"
        assert result.should_abstain

    def test_no_factual_claims(self):
        result = assess_support(
            "I don't know the answer.",
            [],
            [],
        )
        assert result.support_level == "fully_supported"
        assert not result.should_abstain
