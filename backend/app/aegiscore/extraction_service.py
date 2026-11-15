"""Extract searchable text and source locations from uploaded documents."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    filename: str
    file_type: str
    pages: tuple[ExtractedPage, ...]
    status: str

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())


class DocumentExtractionError(ValueError):
    """Raised when a document cannot be safely processed."""


def extract_document(filename: str, content: bytes) -> ExtractionResult:
    if not filename or not filename.strip():
        raise DocumentExtractionError("A filename is required.")

    if not content:
        raise DocumentExtractionError("The document is empty.")

    extension = Path(filename).suffix.lower()

    if extension in {".txt", ".md"}:
        try:
            text = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError(
                "Text document must use valid UTF-8 encoding."
            ) from exc

        if "\x00" in text:
            raise DocumentExtractionError("Text contains invalid NUL characters.")

        if not text.strip():
            raise DocumentExtractionError("No readable text was found.")

        return ExtractionResult(
            filename=Path(filename).name,
            file_type=extension[1:],
            pages=(ExtractedPage(page_number=1, text=text.strip()),),
            status="text_extracted",
        )

    if extension != ".pdf":
        raise DocumentExtractionError(
            "Unsupported file type. Supported formats: PDF, TXT and Markdown."
        )

    if not content.startswith(b"%PDF-"):
        raise DocumentExtractionError("The file does not have a valid PDF signature.")

    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise DocumentExtractionError(
                    "Password-protected PDFs are not supported."
                )

            extracted_pages = []
            for index, page in enumerate(pdf, start=1):
                page_text = page.get_text("text").strip()
                if page_text:
                    extracted_pages.append(
                        ExtractedPage(page_number=index, text=page_text)
                    )

            if not extracted_pages:
                raise DocumentExtractionError(
                    "No selectable text found. This may be a scanned or image-only PDF; OCR is not available in this phase."
                )

            return ExtractionResult(
                filename=Path(filename).name,
                file_type="pdf",
                pages=tuple(extracted_pages),
                status="text_extracted",
            )

    except DocumentExtractionError:
        raise
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise DocumentExtractionError(
            "The PDF is damaged, unreadable, or could not be parsed."
        ) from exc
