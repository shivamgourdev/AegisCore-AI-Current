"""AEGISCORE_PART4C_GENERATED
Local embedding generation and validation for AegisCore document chunks.
"""

import math
from typing import Any, Iterable, Mapping

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingGenerationError(ValueError):
    """Raised when chunk embeddings cannot be safely generated."""


def embed_chunks(
    chunks: Iterable[Mapping[str, Any]],
    encoder: Any = None,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    batch_size: int = 32,
) -> list[dict[str, Any]]:
    """Generate L2-normalized vectors and retain each chunk's source metadata.

    Pass an encoder with an ``encode`` method for testing or custom models.
    When no encoder is supplied, SentenceTransformers loads the configured
    model locally or from its normal model cache/download mechanism.
    """
    items = list(chunks)

    if not items:
        return []

    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
        raise EmbeddingGenerationError("batch_size must be a positive integer.")

    if not isinstance(model_name, str) or not model_name.strip():
        raise EmbeddingGenerationError("model_name must be a non-empty string.")

    texts: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise EmbeddingGenerationError(f"Chunk {index} must be a mapping.")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingGenerationError(f"Chunk {index} has missing or blank text.")
        texts.append(text)

    if encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingGenerationError(
                "sentence-transformers is not installed in this environment. "
                "Install it before running real local embedding inference."
            ) from exc
        try:
            encoder = SentenceTransformer(model_name)
        except Exception as exc:
            raise EmbeddingGenerationError(
                f"Could not load embedding model '{model_name}': {exc}"
            ) from exc

    try:
        raw_vectors = encoder.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )
    except Exception as exc:
        raise EmbeddingGenerationError(f"Embedding model inference failed: {exc}") from exc

    if hasattr(raw_vectors, "tolist"):
        raw_vectors = raw_vectors.tolist()

    if not isinstance(raw_vectors, (list, tuple)) or len(raw_vectors) != len(items):
        raise EmbeddingGenerationError(
            "Encoder must return exactly one vector per input chunk."
        )

    results: list[dict[str, Any]] = []
    expected_dimension: int | None = None

    for index, raw_vector in enumerate(raw_vectors):
        if hasattr(raw_vector, "tolist"):
            raw_vector = raw_vector.tolist()

        if not isinstance(raw_vector, (list, tuple)) or not raw_vector:
            raise EmbeddingGenerationError(f"Chunk {index} has an empty or invalid vector.")

        try:
            vector = [float(value) for value in raw_vector]
        except (TypeError, ValueError) as exc:
            raise EmbeddingGenerationError(
                f"Chunk {index} contains non-numeric embedding values."
            ) from exc

        if not all(math.isfinite(value) for value in vector):
            raise EmbeddingGenerationError(
                f"Chunk {index} contains NaN or infinite embedding values."
            )

        if expected_dimension is None:
            expected_dimension = len(vector)
        elif len(vector) != expected_dimension:
            raise EmbeddingGenerationError("Embedding dimensions are inconsistent.")

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            raise EmbeddingGenerationError(
                f"Chunk {index} produced a zero vector that cannot be normalized."
            )

        normalized = [value / norm for value in vector]
        result = dict(items[index])
        result["embedding"] = normalized
        result["embedding_dimension"] = len(normalized)
        result["embedding_model"] = model_name
        result["embedding_normalized"] = True
        results.append(result)

    return results
