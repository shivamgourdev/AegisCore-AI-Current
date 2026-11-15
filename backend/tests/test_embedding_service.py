"""AEGISCORE_PART4C_GENERATED
Tests for embedding generation and vector validation.
"""

import math
import sys
import types

import pytest

from aegiscore.embedding_service import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingGenerationError,
    embed_chunks,
)


class FakeEncoder:
    def __init__(self, vectors):
        self.vectors = vectors
        self.received_texts = None
        self.received_kwargs = None

    def encode(self, texts, **kwargs):
        self.received_texts = texts
        self.received_kwargs = kwargs
        return self.vectors


def sample_chunk(**overrides):
    chunk = {
        "chunk_id": "chunk-001",
        "document_id": "doc-001",
        "filename": "report.pdf",
        "page_number": 2,
        "chunk_index": 0,
        "text": "Revenue increased during the quarter.",
        "text_sha256": "abc123",
    }
    chunk.update(overrides)
    return chunk


def test_embedding_is_normalized_and_source_metadata_is_preserved():
    encoder = FakeEncoder([[3.0, 4.0]])
    original = sample_chunk()

    result = embed_chunks([original], encoder=encoder)

    assert len(result) == 1
    item = result[0]
    assert item["embedding"] == pytest.approx([0.6, 0.8])
    assert item["embedding_dimension"] == 2
    assert item["embedding_normalized"] is True
    assert item["embedding_model"] == DEFAULT_EMBEDDING_MODEL
    assert item["chunk_id"] == original["chunk_id"]
    assert item["filename"] == original["filename"]
    assert item["page_number"] == 2
    assert item["text"] == original["text"]
    assert math.sqrt(sum(x * x for x in item["embedding"])) == pytest.approx(1.0)
    assert "embedding" not in original


def test_multiple_chunks_keep_their_own_vectors_and_order():
    encoder = FakeEncoder([[1.0, 0.0], [0.0, 2.0]])
    chunks = [
        sample_chunk(chunk_id="chunk-a", text="Alpha"),
        sample_chunk(chunk_id="chunk-b", text="Beta", page_number=3),
    ]

    results = embed_chunks(chunks, encoder=encoder)

    assert [item["chunk_id"] for item in results] == ["chunk-a", "chunk-b"]
    assert results[0]["embedding"] == pytest.approx([1.0, 0.0])
    assert results[1]["embedding"] == pytest.approx([0.0, 1.0])
    assert encoder.received_texts == ["Alpha", "Beta"]
    assert encoder.received_kwargs["batch_size"] == 32


def test_empty_input_returns_without_loading_a_model():
    assert embed_chunks([], encoder=None) == []


@pytest.mark.parametrize("bad_chunk", [
    {},
    {"text": ""},
    {"text": "   "},
    {"text": None},
])
def test_missing_or_blank_chunk_text_is_rejected(bad_chunk):
    with pytest.raises(EmbeddingGenerationError):
        embed_chunks([bad_chunk], encoder=FakeEncoder([[1.0, 0.0]]))


@pytest.mark.parametrize("bad_batch_size", [0, -1, True])
def test_invalid_batch_size_is_rejected(bad_batch_size):
    with pytest.raises(EmbeddingGenerationError, match="batch_size"):
        embed_chunks(
            [sample_chunk()],
            encoder=FakeEncoder([[1.0, 0.0]]),
            batch_size=bad_batch_size,
        )


def test_encoder_must_return_one_vector_per_chunk():
    encoder = FakeEncoder([[1.0, 0.0]])

    with pytest.raises(EmbeddingGenerationError, match="one vector"):
        embed_chunks(
            [sample_chunk(), sample_chunk(chunk_id="chunk-002")],
            encoder=encoder,
        )


def test_zero_vector_is_rejected():
    with pytest.raises(EmbeddingGenerationError, match="zero vector"):
        embed_chunks([sample_chunk()], encoder=FakeEncoder([[0.0, 0.0]]))


@pytest.mark.parametrize("bad_vector", [
    [float("nan"), 1.0],
    [float("inf"), 1.0],
])
def test_non_finite_vector_values_are_rejected(bad_vector):
    with pytest.raises(EmbeddingGenerationError, match="NaN or infinite"):
        embed_chunks([sample_chunk()], encoder=FakeEncoder([bad_vector]))


def test_inconsistent_embedding_dimensions_are_rejected():
    encoder = FakeEncoder([[1.0, 0.0], [1.0, 0.0, 0.0]])

    with pytest.raises(EmbeddingGenerationError, match="dimensions"):
        embed_chunks(
            [
                sample_chunk(chunk_id="chunk-a"),
                sample_chunk(chunk_id="chunk-b"),
            ],
            encoder=encoder,
        )


def test_default_encoder_loads_configured_model_lazily(monkeypatch):
    class FakeSentenceTransformer:
        def __init__(self, model_name):
            assert model_name == "local-test-model"

        def encode(self, texts, **kwargs):
            assert texts == ["Test text"]
            return [[5.0, 12.0]]

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    result = embed_chunks(
        [sample_chunk(text="Test text")],
        model_name="local-test-model",
    )

    assert result[0]["embedding"] == pytest.approx([5 / 13, 12 / 13])
    assert result[0]["embedding_model"] == "local-test-model"
