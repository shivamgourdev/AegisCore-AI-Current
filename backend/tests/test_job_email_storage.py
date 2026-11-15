import pytest

from aegiscore.job_email_storage import create_draft, get_draft


def sample_draft():
    return {
        "recipient_email": "hr@example.com",
        "subject": "Application for Python Developer",
        "body": "Dear Hiring Team,\n\nPlease find my application attached.",
        "attachment_document_id": "resume-test-123",
        "attachment_filename": "resume.pdf",
        "attachment_sha256": "a" * 64,
    }


def test_create_draft_starts_pending():
    draft = create_draft(sample_draft())

    assert draft["status"] == "pending"
    assert draft["recipient_email"] == "hr@example.com"
    assert draft["attachment_filename"] == "resume.pdf"


def test_created_draft_can_be_retrieved():
    created = create_draft(sample_draft())

    retrieved = get_draft(created["draft_id"])

    assert retrieved is not None
    assert retrieved["draft_id"] == created["draft_id"]
    assert retrieved["subject"] == created["subject"]
    assert retrieved["status"] == "pending"


def test_unknown_draft_returns_none():
    assert get_draft("draft-that-does-not-exist") is None
