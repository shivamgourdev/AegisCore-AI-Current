import pymupdf
import pytest

from aegiscore.extraction_service import (
    DocumentExtractionError,
    extract_document,
)


def make_pdf(*page_texts: str) -> bytes:
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), text)
    result = document.tobytes()
    document.close()
    return result


def test_extract_txt_preserves_text_and_source_page():
    result = extract_document("notes.txt", b"Important project notes")

    assert result.status == "text_extracted"
    assert result.file_type == "txt"
    assert result.pages[0].page_number == 1
    assert result.full_text == "Important project notes"


def test_extract_markdown():
    result = extract_document("guide.md", b"# Setup\n\nInstall dependencies.")

    assert result.file_type == "md"
    assert "# Setup" in result.full_text


def test_extract_pdf_preserves_page_numbers():
    pdf_bytes = make_pdf("First page evidence", "Second page evidence")

    result = extract_document("report.pdf", pdf_bytes)

    assert [page.page_number for page in result.pages] == [1, 2]
    assert "First page evidence" in result.pages[0].text
    assert "Second page evidence" in result.pages[1].text


def test_reject_corrupt_pdf():
    with pytest.raises(DocumentExtractionError, match="damaged|unreadable|parsed"):
        extract_document("broken.pdf", b"%PDF-not-a-real-pdf")


def test_reject_pdf_without_signature():
    with pytest.raises(DocumentExtractionError, match="signature"):
        extract_document("wrong.pdf", b"not a PDF")


def test_reject_empty_text():
    with pytest.raises(DocumentExtractionError, match="empty"):
        extract_document("empty.txt", b"")


def test_reject_invalid_utf8():
    with pytest.raises(DocumentExtractionError, match="UTF-8"):
        extract_document("bad.txt", b"\xff\xfe\xfa")


def test_reject_unsupported_extension():
    with pytest.raises(DocumentExtractionError, match="Unsupported"):
        extract_document("archive.zip", b"data")


def test_reject_scanned_or_image_only_pdf():
    document = pymupdf.open()
    document.new_page()
    content = document.tobytes()
    document.close()

    with pytest.raises(DocumentExtractionError, match="scanned|image-only"):
        extract_document("scan.pdf", content)


def test_reject_missing_filename():
    with pytest.raises(DocumentExtractionError, match="filename"):
        extract_document("", b"some text")
