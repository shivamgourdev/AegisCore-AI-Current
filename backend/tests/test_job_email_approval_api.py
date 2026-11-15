import hashlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from aegiscore.main import app
from aegiscore.document_service import save_document
from aegiscore.job_email_storage import create_draft


@pytest.fixture
def approval_context(monkeypatch):
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("AEGISCORE_DATA_DIR", temp_dir)
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF"
        )
        metadata, _duplicate = save_document("resume.pdf", pdf_bytes)
        draft = create_draft({
            "recipient_email": "hr@example.com",
            "subject": "Python Developer Application",
            "body": "Dear Hiring Team,\n\nPlease consider my application.",
            "attachment_document_id": metadata["document_id"],
            "attachment_filename": metadata["filename"],
            "attachment_sha256": metadata["sha256"],
        })
        yield TestClient(app), draft, metadata


def approval_payload(draft):
    return {
        "recipient_email": draft["recipient_email"],
        "subject": draft["subject"],
        "body": draft["body"],
        "attachment_document_id": draft["attachment_document_id"],
        "attachment_sha256": draft["attachment_sha256"],
        "confirm": True,
    }


def test_exact_reviewed_draft_can_be_approved(approval_context):
    client, draft, _ = approval_context

    response = client.post(
        f"/jobs/email-drafts/{draft['draft_id']}/approve",
        json=approval_payload(draft),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "approved"
    assert data["sent"] is False
    assert data["message"] == "Draft approved. No email has been sent."


def test_modified_body_is_rejected(approval_context):
    client, draft, _ = approval_context
    payload = approval_payload(draft)
    payload["body"] += "\nChanged after review."

    response = client.post(
        f"/jobs/email-drafts/{draft['draft_id']}/approve",
        json=payload,
    )

    assert response.status_code == 409
    assert "body" in response.json()["detail"]


def test_approval_requires_explicit_confirmation(approval_context):
    client, draft, _ = approval_context
    payload = approval_payload(draft)
    payload["confirm"] = False

    response = client.post(
        f"/jobs/email-drafts/{draft['draft_id']}/approve",
        json=payload,
    )

    assert response.status_code == 400


def test_unknown_resume_is_rejected(approval_context):
    client, draft, _ = approval_context
    payload = approval_payload(draft)
    payload["attachment_document_id"] = "missing-resume-id"

    response = client.post(
        f"/jobs/email-drafts/{draft['draft_id']}/approve",
        json=payload,
    )

    assert response.status_code == 404
