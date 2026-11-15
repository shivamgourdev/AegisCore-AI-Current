import pytest
from fastapi.testclient import TestClient

from aegiscore.document_service import save_document
from aegiscore.main import app


client = TestClient(app)


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGISCORE_DATA_DIR", str(tmp_path))
    return tmp_path


def make_payload(document_id):
    return {
        "candidate_name": "Shivam Gour",
        "recipient_email": "hr@example.com",
        "job_title": "AI/ML Intern",
        "company_name": "Example Technologies",
        "resume_summary": "Python, FastAPI and RAG projects",
        "resume_document_id": document_id,
    }


def test_email_draft_binds_verified_pdf(isolated_storage):
    metadata, duplicate = save_document(
        "shivam_resume.pdf",
        b"%PDF-1.4\nTest resume content",
    )
    assert duplicate is False

    response = client.post(
        "/jobs/email-draft",
        json=make_payload(metadata["document_id"]),
    )

    assert response.status_code == 200
    draft = response.json()
    assert draft["attachment_document_id"] == metadata["document_id"]
    assert draft["attachment_filename"] == "shivam_resume.pdf"
    assert draft["attachment_sha256"] == metadata["sha256"]
    assert draft["requires_user_approval"] is True
    assert draft["sent"] is False


def test_email_draft_rejects_unknown_resume(isolated_storage):
    response = client.post(
        "/jobs/email-draft",
        json=make_payload("unknown-resume-id"),
    )

    assert response.status_code == 404


def test_email_draft_rejects_non_pdf_resume(isolated_storage):
    metadata, _ = save_document(
        "resume.txt",
        b"Python developer resume",
    )

    response = client.post(
        "/jobs/email-draft",
        json=make_payload(metadata["document_id"]),
    )

    assert response.status_code == 415
