"""AEGISCORE_PHASE3_TESTS_CONTEXT_SELECTOR
Unit tests for the context selection and budget management module.
"""

import pytest

from aegiscore.context_selector import (
    ContextConfig,
    select_context,
    build_context_text,
    SelectedChunk,
)


class TestContextSelection:
    def test_select_all_when_small(self):
        chunks = [
            {"source_id": "S1", "filename": "doc1.txt", "page_number": 1,
             "chunk_index": 0, "text": "Revenue was 42 million.", "similarity": 0.9},
            {"source_id": "S2", "filename": "doc2.txt", "page_number": 1,
             "chunk_index": 0, "text": "Hiring six engineers.", "similarity": 0.8},
        ]
        result = select_context(chunks)
        assert len(selected_chunks := result.selected_chunks) == 2
        assert result.total_chunks == 2
        assert not result.truncated

    def test_filter_low_similarity(self):
        chunks = [
            {"source_id": "S1", "filename": "doc1.txt", "page_number": 1,
             "chunk_index": 0, "text": "High similarity text.", "similarity": 0.9},
            {"source_id": "S2", "filename": "doc2.txt", "page_number": 1,
             "chunk_index": 0, "text": "Low similarity text.", "similarity": 0.1},
        ]
        config = ContextConfig(min_similarity=0.5)
        result = select_context(chunks, config=config)
        assert len(result.selected_chunks) == 1
        assert result.dropped_low_similarity == 1

    def test_remove_near_duplicates(self):
        chunks = [
            {"source_id": "S1", "filename": "doc1.txt", "page_number": 1,
             "chunk_index": 0, "text": "Revenue was 42 million dollars in Q3.", "similarity": 0.9},
            {"source_id": "S2", "filename": "doc1.txt", "page_number": 1,
             "chunk_index": 1, "text": "Revenue was 42 million dollars in Q3.", "similarity": 0.85},
        ]
        result = select_context(chunks)
        assert len(result.selected_chunks) == 1
        # Identical text is caught as exact duplicate (dropped in step 2),
        # not as near-duplicate (step 3). Either way, only 1 chunk remains.
        assert result.total_chunks == 1

    def test_remove_near_duplicates_different_text(self):
        chunks = [
            {"source_id": "S1", "filename": "doc1.txt", "page_number": 1,
             "chunk_index": 0, "text": "The quick brown fox jumps over the lazy dog.", "similarity": 0.9},
            {"source_id": "S2", "filename": "doc1.txt", "page_number": 1,
             "chunk_index": 1, "text": "The quick brown fox jumps over a lazy dog.", "similarity": 0.85},
        ]
        result = select_context(chunks)
        assert len(result.selected_chunks) == 1
        assert result.dropped_duplicates == 1

    def test_source_diversity_limit(self):
        chunks = [
            {"source_id": f"S{i}", "filename": "doc1.txt", "page_number": 1,
             "chunk_index": i, "text": f"Text {i}.", "similarity": 0.9 - i * 0.01}
            for i in range(5)
        ]
        config = ContextConfig(max_chunks_per_document=2)
        result = select_context(chunks, config=config)
        assert len(result.selected_chunks) == 2

    def test_character_budget_truncation(self):
        chunks = [
            {"source_id": f"S{i}", "filename": f"doc{i}.txt", "page_number": 1,
             "chunk_index": i, "text": f"Document {i} content: " + "x" * 400, "similarity": 0.9 - i * 0.01}
            for i in range(5)
        ]
        config = ContextConfig(max_context_chars=1000)
        result = select_context(chunks, config=config)
        assert result.total_chars <= 1000
        assert result.truncated
        assert result.dropped_due_to_budget > 0

    def test_empty_chunks(self):
        result = select_context([])
        assert len(result.selected_chunks) == 0
        assert result.total_chunks == 0


class TestBuildContextText:
    def test_build_context(self):
        chunks = [
            SelectedChunk(
                source_id="S1", filename="doc1.txt", page_number=1,
                chunk_index=0, text="Revenue was 42 million.", similarity=0.9,
            ),
            SelectedChunk(
                source_id="S2", filename="doc2.txt", page_number=2,
                chunk_index=1, text="Hiring engineers.", similarity=0.8,
            ),
        ]
        text = build_context_text(chunks)
        assert "S1" in text
        assert "S2" in text
        assert "Revenue was 42 million" in text
        assert "Hiring engineers" in text

    def test_truncate_long_chunk(self):
        chunks = [
            SelectedChunk(
                source_id="S1", filename="doc1.txt", page_number=1,
                chunk_index=0, text="x" * 2000, similarity=0.9,
            ),
        ]
        text = build_context_text(chunks, max_chars_per_chunk=100)
        assert len(text.split("Evidence:")[1]) <= 100 + 10  # Some overhead
