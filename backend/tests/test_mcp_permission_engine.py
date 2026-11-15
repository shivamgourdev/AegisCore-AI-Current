"""AEGISCORE_PHASE2_TESTS_PERMISSION_ENGINE

Unit tests for the MCP permission engine — read-only vs state-changing,
confirm: true is NOT sufficient for state-changing tools.
"""

import pytest

from aegiscore.mcp_permission_engine import PermissionEngine
from aegiscore.mcp_tool_registry import MCPToolRegistry


class TestPermissionEngine:
    def setup_method(self):
        self.registry = MCPToolRegistry()
        self.engine = PermissionEngine(self.registry)

    def test_read_only_tool_allowed_without_confirm(self):
        decision, reason = self.engine.evaluate("search_knowledge", {"query": "test"})
        assert decision == "allowed"

    def test_read_only_tool_allowed_with_extra_fields(self):
        decision, reason = self.engine.evaluate(
            "list_documents", {"extra_field": "ignored"}
        )
        assert decision == "allowed"

    def test_state_changing_requires_confirm(self):
        decision, reason = self.engine.evaluate(
            "generate_email_draft",
            {
                "candidate_name": "John",
                "recipient_email": "hr@example.com",
                "job_title": "Developer",
                "company_name": "Acme",
                "resume_summary": "Python developer",
                "resume_document_id": "doc-123",
                # no confirm field
            },
        )
        assert decision == "requires_confirmation"
        assert "confirmation" in reason.lower()

    def test_confirm_alone_is_not_sufficient(self):
        """confirm: true alone does NOT authorize email draft."""
        decision, reason = self.engine.evaluate(
            "generate_email_draft",
            {
                "candidate_name": "John",
                "recipient_email": "hr@example.com",
                "job_title": "Developer",
                "company_name": "Acme",
                "resume_summary": "Python developer",
                "resume_document_id": "doc-123",
                "confirm": True,
                # No attachment_sha256 or attachment_document_id match
            },
        )
        assert decision == "confirmation_insufficient"
        assert "sufficient" in reason.lower()

    def test_confirm_with_valid_attachment_is_allowed(self):
        # First record a verified draft
        self.engine.record_verified_draft(
            document_id="doc-123",
            sha256="abc123",
            attachment_document_id="doc-123",
        )
        decision, reason = self.engine.evaluate(
            "generate_email_draft",
            {
                "candidate_name": "John",
                "recipient_email": "hr@example.com",
                "job_title": "Developer",
                "company_name": "Acme",
                "resume_summary": "Python developer",
                "resume_document_id": "doc-123",
                "confirm": True,
                "attachment_document_id": "doc-123",
                "attachment_sha256": "abc123",
            },
        )
        assert decision == "allowed"

    def test_confirm_with_wrong_sha256_denied(self):
        self.engine.record_verified_draft(
            document_id="doc-123",
            sha256="abc123",
            attachment_document_id="doc-123",
        )
        decision, reason = self.engine.evaluate(
            "generate_email_draft",
            {
                "candidate_name": "John",
                "recipient_email": "hr@example.com",
                "job_title": "Developer",
                "company_name": "Acme",
                "resume_summary": "Python developer",
                "resume_document_id": "doc-123",
                "confirm": True,
                "attachment_document_id": "doc-123",
                "attachment_sha256": "wrong_hash",
            },
        )
        assert decision == "confirmation_insufficient"

    def test_confirm_with_wrong_document_id_denied(self):
        self.engine.record_verified_draft(
            document_id="doc-123",
            sha256="abc123",
            attachment_document_id="doc-123",
        )
        decision, reason = self.engine.evaluate(
            "generate_email_draft",
            {
                "candidate_name": "John",
                "recipient_email": "hr@example.com",
                "job_title": "Developer",
                "company_name": "Acme",
                "resume_summary": "Python developer",
                "resume_document_id": "doc-123",
                "confirm": True,
                "attachment_document_id": "other-doc",
                "attachment_sha256": "abc123",
            },
        )
        assert decision == "confirmation_insufficient"

    def test_unknown_tool_denied(self):
        decision, reason = self.engine.evaluate("nonexistent_tool", {})
        assert decision == "denied"

    def test_record_verified_draft(self):
        self.engine.record_verified_draft(
            document_id="doc-456",
            sha256="def456",
            attachment_document_id="doc-456",
        )
        decision, reason = self.engine.evaluate(
            "generate_email_draft",
            {
                "candidate_name": "Jane",
                "recipient_email": "hr@example.com",
                "job_title": "Engineer",
                "company_name": "Tech",
                "resume_summary": "Engineer",
                "resume_document_id": "doc-456",
                "confirm": True,
                "attachment_document_id": "doc-456",
                "attachment_sha256": "def456",
            },
        )
        assert decision == "allowed"

    def test_clear_draft_denies_subsequent(self):
        self.engine.record_verified_draft(
            document_id="doc-789",
            sha256="ghi789",
            attachment_document_id="doc-789",
        )
        self.engine.clear_draft("doc-789")
        decision, reason = self.engine.evaluate(
            "generate_email_draft",
            {
                "candidate_name": "John",
                "recipient_email": "hr@example.com",
                "job_title": "Developer",
                "company_name": "Acme",
                "resume_summary": "Python",
                "resume_document_id": "doc-789",
                "confirm": True,
                "attachment_document_id": "doc-789",
                "attachment_sha256": "ghi789",
            },
        )
        assert decision == "confirmation_insufficient"

    def test_is_state_changing(self):
        assert self.engine.is_state_changing("generate_email_draft") is True
        assert self.engine.is_state_changing("search_knowledge") is False
        assert self.engine.is_state_changing("nonexistent") is False
