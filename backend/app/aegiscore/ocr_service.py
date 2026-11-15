"""AEGISCORE_PHASE10_OCR
Phase 10: OCR Service for Hiring Document Intelligence.

Provides OCR (Optical Character Recognition) for hiring-related images
such as resumes, job postings, and application documents.

Uses Tesseract OCR via pytesseract. No paid cloud OCR services are used.
All processing is local.

OCR is specifically for hiring-related images only. Not for general document
processing or image Q&A.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

try:
    import pytesseract

    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

# Configure Tesseract OCR binary path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def is_ocr_available() -> bool:
    """Check if OCR is available (tesseract installed and pytesseract importable)."""
    return _OCR_AVAILABLE


def extract_text_from_image(image_bytes: bytes) -> dict:
    """Extract text from image bytes using local Tesseract OCR."""
    if not _OCR_AVAILABLE:
        raise ValueError(
            "OCR is unavailable. Install pytesseract and Tesseract OCR."
        )

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as exc:
        raise ValueError(f"Unable to process image: {exc}") from exc

    try:
        text = pytesseract.image_to_string(image)
    except Exception as exc:
        raise ValueError(f"OCR processing failed: {exc}") from exc

    # Confidence is optional; failure to obtain it must not discard text.
    try:
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT
        )
        confidences = [
            int(conf)
            for conf in data["conf"]
            if conf != "-1" and int(conf) > 0
        ]
        avg_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )
    except Exception:
        avg_confidence = 0.0

    return {
        "text": text.strip(),
        "confidence": round(avg_confidence, 2),
        "language": "eng",
    }


def extract_text_from_image_file(file_path: str) -> dict:
    """Extract text from an image file using OCR.

    Args:
        file_path: Path to the image file.

    Returns:
        Dictionary with extracted text and confidence.
    """
    from PIL import Image

    try:
        image = Image.open(file_path)
    except Exception as exc:
        raise ValueError(f"Unable to open image file: {exc}") from exc

    return extract_text_from_image_bytes(image.tobytes())


def extract_text_from_image_bytes(image_bytes: bytes) -> dict:
    """Extract text from image bytes using OCR.

    Args:
        image_bytes: Raw image bytes.

    Returns:
        Dictionary with extracted text, confidence, and language.
    """
    return extract_text_from_image(image_bytes)


def validate_image_file(file_bytes: bytes, max_size_mb: int = 10) -> None:
    """Validate an uploaded image file.

    Args:
        file_bytes: Raw image file bytes.
        max_size_mb: Maximum file size in megabytes.

    Raises:
        ValueError: If the file is invalid or too large.
    """
    if not file_bytes:
        raise ValueError("Image file is empty.")

    if len(file_bytes) > max_size_mb * 1024 * 1024:
        raise ValueError(f"Image exceeds maximum size of {max_size_mb} MB.")

    try:
        from PIL import Image

        image = Image.open(io.BytesIO(file_bytes))
        image.verify()
    except Exception as exc:
        raise ValueError(f"Invalid image file: {exc}") from exc


def get_supported_formats() -> list[str]:
    """Return list of supported image formats."""
    return ["image/png", "image/jpeg", "image/jpg", "image/gif", "image/bmp", "image/tiff"]


def is_supported_format(content_type: str) -> bool:
    """Check if a content type is a supported image format."""
    return content_type.lower() in get_supported_formats()