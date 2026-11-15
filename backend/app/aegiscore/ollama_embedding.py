"""AEGISCORE_PART4D_GENERATED
Ollama-backed embedding encoder. Uses the standard library HTTP client.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OLLAMA_EMBEDDING_MODEL = os.getenv(
    "AEGISCORE_EMBEDDING_MODEL", "nomic-embed-text:latest"
)
OLLAMA_BASE_URL = os.getenv("AEGISCORE_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


class OllamaEmbeddingEncoder:
    """Adapter implementing the encode interface used by embedding_service."""

    def __init__(self, base_url=None, timeout=120):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout

    def encode(self, texts, **kwargs):
        from aegiscore.embedding_service import EmbeddingGenerationError

        if isinstance(texts, str):
            texts = [texts]
        texts = list(texts)
        if not texts:
            return []

        payload = json.dumps({
            "model": OLLAMA_EMBEDDING_MODEL,
            "input": texts,
        }).encode("utf-8")
        request = Request(
            self.base_url + "/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise EmbeddingGenerationError(
                f"Ollama embedding request failed at {self.base_url}: {exc}"
            ) from exc

        vectors = result.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbeddingGenerationError(
                "Ollama did not return exactly one embedding per input text."
            )
        return vectors
