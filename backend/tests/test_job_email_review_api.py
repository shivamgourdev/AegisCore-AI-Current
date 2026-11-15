import os
import tempfile

from fastapi.testclient import TestClient

from aegiscore.main import app
from aegiscore.job_email_storage import create_draft


def test_get_saved_draft_endpoint():
    with tempfile.TemporaryDirectory() as temp_dir:
        previous = os.environ.get("AEGISCORE_DATA_DIR")
        os.environ["AEGISCORE_DATA_DIR"] = temp_dir

        try:
            stored = create_draft({
                "recipient_email": "hr@example.com",
                "subject": "Python Developer Application",
                "body": "Dear Hiring Team,\n\nPlease consider my application.",
                "attachment_document_id": "resume-123",
                "attachment_filename": "resume.pdf",
                "attachment_sha256": "a" * 64,
            })

            client = TestClient(app)
            response = client.get(
                f"/jobs/email-drafts/{stored['draft_id']}"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["draft_id"] == stored["draft_id"]
            assert data["status"] == "pending"
            assert data["recipient_email"] == "hr@example.com"
            assert data["subject"] == "Python Developer Application"
            assert data["attachment_filename"] == "resume.pdf"
            assert data["sent"] is False
        finally:
            if previous is None:
                os.environ.pop("AEGISCORE_DATA_DIR", None)
            else:
                os.environ["AEGISCORE_DATA_DIR"] = previous
