"""AEGISCORE_PART4A_GENERATED
Deterministic page-aware text chunking with source metadata.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping, Iterable
from typing import Any


def _field(page: Any, name: str) -> Any:
    if isinstance(page, Mapping):
        return page.get(name)
    return getattr(page, name, None)


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text or not text.strip():
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        if end < length:
            minimum_break = start + int(chunk_size * 0.6)
            candidates = [
                text.rfind("\n", minimum_break, end),
                text.rfind(" ", minimum_break, end),
                text.rfind("\t", minimum_break, end),
            ]
            boundary = max(candidates)
            if boundary > start:
                end = boundary

        piece = text[start:end]
        if piece.strip():
            chunks.append(piece)

        if end >= length:
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def chunk_document(
    document_id: str,
    filename: str,
    pages: Iterable[Any],
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[dict[str, Any]]:
    """Chunk extracted pages while preserving source metadata.

    Each page must expose ``page_number`` and ``text`` fields, either
    as mapping keys or object attributes. Page numbers are one-based.
    Overlap is applied within a page and never crosses page boundaries.
    """
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("document_id must be a non-empty string")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty string")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer")
    if isinstance(chunk_overlap, bool) or not isinstance(chunk_overlap, int):
        raise ValueError("chunk_overlap must be an integer")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    output: list[dict[str, Any]] = []

    for page in pages:
        page_number = _field(page, "page_number")
        text = _field(page, "text")

        if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
            raise ValueError("Each page must have a positive one-based page_number")
        if not isinstance(text, str):
            raise ValueError("Each page must have text as a string")

        pieces = _split_text(text, chunk_size, chunk_overlap)

        for chunk_index, piece in enumerate(pieces):
            text_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()
            stable_key = (
                f"aegiscore:{document_id}:{filename}:{page_number}:"
                f"{chunk_index}:{text_hash}"
            )
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key))

            output.append({
                "chunk_id": chunk_id,
                "document_id": document_id,
                "filename": filename,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "text": piece,
                "char_count": len(piece),
                "text_sha256": text_hash,
            })

    return output
