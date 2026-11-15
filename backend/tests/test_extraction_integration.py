import pymupdf
from fastapi.testclient import TestClient

from aegiscore.main import app
from aegiscore.extraction_storage import get_extraction


def make_pdf(*texts: str) -> bytes:
    pdf = pymupdf.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    content = pdf.tobytes()
    pdf.close()
    return content


def test_upload_txt_triggers_extraction_and_persists_text(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/documents/upload",
        files={"file": ("facts.txt", b"Evidence from document one", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["extraction"]["status"] == "text_extracted"
    assert payload["extraction"]["page_count"] == 1

    document_id = payload["document"]["document_id"]
    stored = get_extraction(document_id)
    assert stored is not None
    assert "Evidence from document one" in stored["text"]
    assert stored["pages"][0]["page_number"] == 1


def test_upload_pdf_persists_page_citations(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "report.pdf",
                make_pdf("Page one proof", "Page two proof"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    document_id = payload["document"]["document_id"]
    stored = get_extraction(document_id)

    assert payload["extraction"]["status"] == "text_extracted"
    assert [page["page_number"] for page in stored["pages"]] == [1, 2]
    assert "Page one proof" in stored["pages"][0]["text"]
    assert "Page two proof" in stored["pages"][1]["text"]


def test_extraction_endpoint_returns_404_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    response = TestClient(app).get(
        "/documents/does-not-exist/extraction"
    )
    assert response.status_code == 404


def test_upload_corrupt_pdf_reports_extraction_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    response = TestClient(app).post(
        "/documents/upload",
        files={
            "file": (
                "bad.pdf",
                b"%PDF-not-a-valid-document",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["extraction"]["status"] == "extraction_failed"
    assert response.json()["extraction"]["error"]
