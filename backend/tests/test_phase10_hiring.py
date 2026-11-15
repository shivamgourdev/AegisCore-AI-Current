"""AEGISCORE_PART10_TESTS
Unit tests for Phase 10: AI Hiring & Job Application Workflow.

Tests hiring text processing, document upload with OCR, email draft generation,
and attachment integrity validation.
"""

import io
import json

import pytest
from fastapi.testclient import TestClient

from aegiscore.main import app


class TestHiringTextProcessing:
    """Tests for the hiring text processing endpoint."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_extract_job_information(self):
        """Test that hiring text is parsed into structured job information."""
        response = self.client.post(
            "/jobs/hiring/text",
            json={
                "hiring_text": "We are hiring a Python Developer at TechCorp. "
                "Requirements: Python, FastAPI, SQL, Docker. "
                "Location: New York, NY. "
                "Experience: 3+ years. "
                "Salary: $80,000 - $120,000. "
                "Contact: hr@techcorp.com. "
                "Deadline: 2024-12-31."
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "company_name" in data
        assert "job_title" in data
        assert "required_skills" in data
        assert "missing_skills" in data
        assert "experience_requirements" in data
        assert "location" in data
        assert "work_mode" in data
        assert "salary" in data
        assert "recruiter_name" in data
        assert "recruiter_email" in data
        assert "contact_information" in data
        assert "application_instructions" in data
        assert "deadline" in data
        assert "raw_text" in data

    def test_empty_job_description_rejected(self):
        """Test that empty job description is rejected."""
        response = self.client.post(
            "/jobs/hiring/text",
            json={"hiring_text": ""},
        )
        assert response.status_code == 422  # FastAPI validation error

    def test_non_string_input_rejected(self):
        """Test that non-string input is rejected."""
        response = self.client.post(
            "/jobs/hiring/text",
            json={"hiring_text": 123},
        )
        assert response.status_code == 422


class TestHiringDocumentUpload:
    """Tests for hiring document upload with OCR."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_upload_image_document(self):
        """Test image upload and OCR response using deterministic OCR output."""
        import io
        from PIL import Image
        from unittest.mock import patch

        img = Image.new("RGB", (1, 1), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        mocked_ocr = {
            "text": "We are hiring a Python Developer at TestCorp. Contact hr@testcorp.com",
            "confidence": 95.0,
            "language": "eng",
        }

        with patch(
            "aegiscore.ocr_service.extract_text_from_image_bytes",
            return_value=mocked_ocr,
        ):
            response = self.client.post(
                "/jobs/hiring/upload",
                files={"file": ("test.png", img_bytes, "image/png")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["extracted_text"] == mocked_ocr["text"]
        assert data["ocr_available"] is True
        assert data["ocr_confidence"] == 95.0

    def test_upload_non_image_file(self):
        """Test uploading a non-image file is rejected."""
        response = self.client.post(
            "/jobs/hiring/upload",
            files={"file": ("test.txt", b"not an image", "text/plain")},
        )
        assert response.status_code in (400, 415, 422)

    def test_upload_corrupted_pdf(self):
        """Test uploading a corrupted PDF is rejected."""
        response = self.client.post(
            "/jobs/hiring/upload",
            files={"file": ("broken.pdf", b"not a valid pdf", "application/pdf")},
        )
        assert response.status_code in (400, 415, 422)


class TestEmailDraftFromHiring:
    """Tests for email draft generation from hiring data."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_create_email_draft_from_hiring(self):
        """Test creating an email draft from hiring data."""
        # First upload a resume PDF
        import io
        from PIL import Image

        # Create a minimal PDF-like content for testing
        pdf_content = b"%PDF-1.4\nTest resume content"

        upload_response = self.client.post(
            "/documents/upload",
            files={"file": ("resume.pdf", pdf_content, "application/pdf")},
        )
        assert upload_response.status_code == 200
        doc_id = upload_response.json()["document"]["document_id"]

        # Create email draft
        response = self.client.post(
            "/jobs/email-draft",
            json={
                "candidate_name": "John Doe",
                "recipient_email": "hr@example.com",
                "job_title": "Python Developer",
                "company_name": "TechCorp",
                "resume_summary": "Python developer with FastAPI experience",
                "resume_document_id": doc_id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "draft_id" in data
        assert data["status"] == "pending"
        assert data["sent"] is False
        assert data["attachment_document_id"] == doc_id