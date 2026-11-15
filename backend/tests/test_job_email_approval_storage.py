import os
import tempfile

import pytest

from aegiscore.job_email_storage import (
    approve_draft,
    create_draft,
    get_draft,
)


def sample_draft():
    return {
        "recipient_email": "hr@example.com",
        "subject": "Python Developer Application",
        "body": "Dear Hiring Team,\n\nPlease consider my application.",
        "attachment_document_id": "resume-test-123",
        "attachment_filename": "resume.pdf",
        "attachment_sha256": "a" * 64,
    }


@pytest.fixture
def isolated_database(monkeypatch):
    with tempfile.TemporaryDirectory() as temp_dir:
        monkeypatch.setenv("AEGISCORE_DATA_DIR", temp_dir)
        yield


def test_exact_reviewed_draft_can_be_approved(isolated_database):
    draft = create_draft(sample_draft())

    reviewed = {
        key: draft[key]
        for key in (
            "recipient_email",
            "subject",
            "body",
            "attachment_document_id",
            "attachment_sha256",
        )
    }

    result = approve_draft(draft["draft_id"], reviewed)

    assert result["status"] == "approved"
    assert result["approved_at"] is not None
    assert result["sent_at"] is None


def test_modified_email_body_is_rejected(isolated_database):
    draft = create_draft(sample_draft())
    reviewed = {
        key: draft[key]
        for key in (
            "recipient_email",
            "subject",
            "body",
            "attachment_document_id",
            "attachment_sha256",
        )
    }
    reviewed["body"] += "\nChanged after review."

    with pytest.raises(ValueError, match="body"):
        approve_draft(draft["draft_id"], reviewed)

    assert get_draft(draft["draft_id"])["status"] == "pending"


def test_unknown_draft_returns_none(isolated_database):
    reviewed = sample_draft()
    reviewed.pop("attachment_filename")

    assert approve_draft("unknown-draft-id", reviewed) is None


def test_already_approved_draft_cannot_be_approved_again(isolated_database):
    draft = create_draft(sample_draft())
    reviewed = {
        key: draft[key]
        for key in (
            "recipient_email",
            "subject",
            "body",
            "attachment_document_id",
            "attachment_sha256",
        )
    }

    approve_draft(draft["draft_id"], reviewed)

    with pytest.raises(ValueError, match="Only pending drafts"):
        approve_draft(draft["draft_id"], reviewed)
