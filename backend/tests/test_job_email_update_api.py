import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from aegiscore.main import app
from aegiscore.document_service import save_document
from aegiscore.job_email_storage import create_draft


@pytest.fixture
def update_context(monkeypatch):
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("AEGISCORE_DATA_DIR", temp_dir)
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF"
        )
        metadata, _ = save_document("resume.pdf", pdf_bytes)
        draft = create_draft({
            "recipient_email": "hr@example.com",
            "subject": "Python Developer Application",
            "body": "Dear Hiring Team.",
            "attachment_document_id": metadata["document_id"],
            "attachment_filename": metadata["filename"],
            "attachment_sha256": metadata["sha256"],
        })
        yield TestClient(app), draft, metadata


def update_payload():
    return {
        "recipient_email": "recruiter@example.com",
        "subject": "Updated Python Developer Application",
        "body": "Dear Recruiter, please find my application attached.",
    }


def test_pending_draft_can_be_updated_without_changing_attachment(update_context):
    client, draft, metadata = update_context

    response = client.put(
        f"/jobs/email-drafts/{draft['draft_id']}",
        json=update_payload(),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "pending"
    assert data["recipient_email"] == "recruiter@example.com"
    assert data["subject"] == update_payload()["subject"]
    assert data["body"] == update_payload()["body"]
    assert data["attachment_document_id"] == metadata["document_id"]
    assert data["attachment_sha256"] == metadata["sha256"]
    assert data["sent"] is False
    assert data["requires_user_approval"] is True


def test_approved_draft_cannot_be_updated(update_context):
    client, draft, _ = update_context

    approved = client.post(
        f"/jobs/email-drafts/{draft['draft_id']}/approve",
        json={
            "recipient_email": draft["recipient_email"],
            "subject": draft["subject"],
            "body": draft["body"],
            "attachment_document_id": draft["attachment_document_id"],
            "attachment_sha256": draft["attachment_sha256"],
            "confirm": True,
        },
    )
    assert approved.status_code == 200, approved.text

    response = client.put(
        f"/jobs/email-drafts/{draft['draft_id']}",
        json=update_payload(),
    )
    assert response.status_code == 409


def test_invalid_recipient_email_is_rejected(update_context):
    client, draft, _ = update_context
    payload = update_payload()
    payload["recipient_email"] = "not-an-email"

    response = client.put(
        f"/jobs/email-drafts/{draft['draft_id']}",
        json=payload,
    )
    assert response.status_code == 422
