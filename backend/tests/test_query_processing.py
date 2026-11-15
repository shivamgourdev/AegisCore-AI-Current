"""AEGISCORE_PHASE3_TESTS_QUERY_PROCESSING
Unit tests for the query processing module.
"""

import pytest

from aegiscore.query_processing import (
    QueryConfig,
    decompose_query,
    expand_query,
    normalize_query,
    process_query,
    validate_query,
    build_retrieval_queries,
)


class TestNormalizeQuery:
    def test_normalize_basic(self):
        assert normalize_query("  Hello   World  ") == "Hello World"

    def test_normalize_tabs_and_newlines(self):
        assert normalize_query("Hello\t\tWorld\n\nTest") == "Hello World Test"

    def test_normalize_empty(self):
        assert normalize_query("") == ""
        assert normalize_query("   ") == ""

    def test_normalize_none(self):
        assert normalize_query(None) == ""


class TestValidateQuery:
    def test_valid_query(self):
        assert validate_query("What is revenue?") == []

    def test_empty_query(self):
        assert validate_query("") == ["query must be non-empty text."]
        assert validate_query("   ") == ["query must be non-empty text."]

    def test_none_query(self):
        assert validate_query(None) == ["query must be a string."]

    def test_too_long_query(self):
        long_query = "x" * 5001
        errors = validate_query(long_query, max_length=5000)
        assert len(errors) == 1
        assert "exceeds maximum length" in errors[0]


class TestDecomposeQuery:
    def test_single_query_no_decomposition(self):
        result = decompose_query("What is revenue?")
        assert len(result) == 1
        assert result[0].source == "original"
        assert result[0].text == "What is revenue?"

    def test_decompose_on_and(self):
        result = decompose_query("What is revenue and what is profit?")
        assert len(result) >= 2
        assert all(sq.source == "decomposed" for sq in result[1:])
        assert all(sq.parent_query == "What is revenue and what is profit?" for sq in result)

    def test_decompose_max_subqueries(self):
        result = decompose_query("A and B and C and D and E", max_subqueries=3)
        assert len(result) <= 3


class TestExpandQuery:
    def test_no_expansion_by_default(self):
        result = expand_query("revenue")
        assert result == []

    def test_expansion_enabled(self):
        result = expand_query("revenue", enable_expansion=True)
        assert "income" in result or "earnings" in result or "sales" in result

    def test_expansion_empty(self):
        assert expand_query("") == []
        assert expand_query("   ", enable_expansion=True) == []


class TestProcessQuery:
    def test_valid_query_processing(self):
        result = process_query("What is revenue?")
        assert result.is_valid
        assert result.original_query == "What is revenue?"
        assert result.normalized_query == "What is revenue?"
        assert len(result.validation_errors) == 0

    def test_invalid_query_processing(self):
        result = process_query("")
        assert not result.is_valid
        assert len(result.validation_errors) > 0

    def test_decomposition_enabled(self):
        config = QueryConfig(enable_decomposition=True)
        result = process_query("What is revenue and what is profit?", config=config)
        assert result.is_valid
        assert len(result.subqueries) >= 1


class TestBuildRetrievalQueries:
    def test_build_from_valid_query(self):
        config = QueryConfig()
        processed = process_query("What is revenue?", config=config)
        queries = build_retrieval_queries(processed)
        assert len(queries) == 1
        assert queries[0][0] == "What is revenue?"
        assert queries[0][1] == config.dense_weight
        assert queries[0][2] == config.sparse_weight

    def test_build_from_invalid_query(self):
        config = QueryConfig()
        processed = process_query("", config=config)
        queries = build_retrieval_queries(processed)
        assert queries == []
