"""AEGISCORE_PART4A_GENERATED
Tests for deterministic, page-aware document chunking.
"""

import hashlib
import pytest

from aegiscore.chunking_service import chunk_document


def test_short_page_preserves_text_and_source_metadata():
    chunks = chunk_document(
        "doc-1", "guide.txt",
        [{"page_number": 1, "text": "A short source passage."}],
        chunk_size=100, chunk_overlap=10,
    )
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["text"] == "A short source passage."
    assert chunk["document_id"] == "doc-1"
    assert chunk["filename"] == "guide.txt"
    assert chunk["page_number"] == 1
    assert chunk["chunk_index"] == 0
    assert chunk["char_count"] == len(chunk["text"])
    assert chunk["text_sha256"] == hashlib.sha256(
        chunk["text"].encode("utf-8")
    ).hexdigest()


def test_long_text_is_split_with_configured_maximum_size():
    text = ("alpha beta gamma delta epsilon " * 12).strip()
    chunks = chunk_document(
        "doc-2", "long.txt",
        [{"page_number": 1, "text": text}],
        chunk_size=40, chunk_overlap=8,
    )
    assert len(chunks) > 1
    assert all(0 < chunk["char_count"] <= 40 for chunk in chunks)
    assert all(chunk["text"] for chunk in chunks)


def test_adjacent_chunks_preserve_configured_overlap():
    text = "0123456789" * 10
    chunks = chunk_document(
        "doc-3", "numbers.txt",
        [{"page_number": 1, "text": text}],
        chunk_size=20, chunk_overlap=5,
    )
    assert len(chunks) > 1
    for left, right in zip(chunks, chunks[1:]):
        assert left["text"][-5:] == right["text"][:5]


def test_pages_keep_independent_source_numbers():
    chunks = chunk_document(
        "doc-4", "report.pdf",
        [
            {"page_number": 1, "text": "First page source."},
            {"page_number": 2, "text": "Second page source."},
        ],
        chunk_size=100, chunk_overlap=10,
    )
    assert [chunk["page_number"] for chunk in chunks] == [1, 2]
    assert "First page" in chunks[0]["text"]
    assert "Second page" in chunks[1]["text"]


def test_blank_pages_are_skipped_without_empty_chunks():
    chunks = chunk_document(
        "doc-5", "blank.txt",
        [
            {"page_number": 1, "text": "   \n "},
            {"page_number": 2, "text": "Actual content"},
        ],
        chunk_size=100, chunk_overlap=10,
    )
    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 2
    assert chunks[0]["text"] == "Actual content"


def test_chunk_ids_are_stable_and_unique_for_distinct_chunks():
    pages = [{"page_number": 1, "text": "abcdefghij" * 10}]
    first = chunk_document("doc-6", "stable.txt", pages, 20, 4)
    second = chunk_document("doc-6", "stable.txt", pages, 20, 4)
    ids = [item["chunk_id"] for item in first]
    assert ids == [item["chunk_id"] for item in second]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "size,overlap",
    [(0, 0), (-1, 0), (10, 10), (10, 11), (10, -1)],
)
def test_invalid_chunk_settings_are_rejected(size, overlap):
    with pytest.raises(ValueError):
        chunk_document(
            "doc-7", "bad.txt",
            [{"page_number": 1, "text": "some content"}],
            chunk_size=size, chunk_overlap=overlap,
        )


@pytest.mark.parametrize(
    "document_id,filename,pages",
    [
        ("", "a.txt", []),
        ("doc", "", []),
        ("doc", "a.txt", [{"page_number": 0, "text": "bad"}]),
        ("doc", "a.txt", [{"page_number": 1, "text": None}]),
    ],
)
def test_invalid_source_metadata_is_rejected(document_id, filename, pages):
    with pytest.raises(ValueError):
        chunk_document(document_id, filename, pages)
