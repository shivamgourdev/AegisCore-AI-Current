"""AEGISCORE_PHASE2_TESTS_AUDIT_LOGGER

Unit tests for the MCP audit logger — tamper-evident hash chain.
"""

import os
import tempfile

import pytest

from aegiscore.mcp_audit_logger import AuditLogger, get_audit_logger


class TestAuditLogger:
    def test_log_and_verify_chain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_path)

            rec1 = logger.log(
                execution_id="exec-1",
                tool_name="search_knowledge",
                input_data={"query": "test"},
                output_status="success",
                duration_seconds=0.5,
            )
            rec2 = logger.log(
                execution_id="exec-2",
                tool_name="list_documents",
                input_data={},
                output_status="success",
                duration_seconds=0.3,
            )

            assert rec1["chain_hash"] is not None
            assert rec2["chain_hash"] is not None
            assert rec2["previous_hash"] == rec1["chain_hash"]

            result = logger.verify_chain()
            assert result["valid"] is True
            assert result["record_count"] == 2

    def test_tampering_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_path)

            logger.log(
                execution_id="exec-1",
                tool_name="search_knowledge",
                input_data={"query": "test"},
                output_status="success",
                duration_seconds=0.5,
            )
            logger.log(
                execution_id="exec-2",
                tool_name="list_documents",
                input_data={},
                output_status="success",
                duration_seconds=0.3,
            )

            # Tamper with the first record
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            import json

            rec1 = json.loads(lines[0])
            rec1["output_status"] = "tampered"
            lines[0] = json.dumps(rec1, sort_keys=True, separators=(",", ":"))

            with open(log_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            # Create new logger to recover chain
            logger2 = AuditLogger(log_path)
            result = logger2.verify_chain()
            assert result["valid"] is False
            assert result["broken_at"] is not None
            assert len(result["details"]) > 0

    def test_reordering_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_path)

            logger.log(
                execution_id="exec-1",
                tool_name="search_knowledge",
                input_data={"query": "test"},
                output_status="success",
                duration_seconds=0.5,
            )
            logger.log(
                execution_id="exec-2",
                tool_name="list_documents",
                input_data={},
                output_status="success",
                duration_seconds=0.3,
            )

            # Reorder lines
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            lines.reverse()

            with open(log_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            logger2 = AuditLogger(log_path)
            result = logger2.verify_chain()
            assert result["valid"] is False

    def test_empty_log_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_path)
            result = logger.verify_chain()
            assert result["valid"] is True
            assert result["record_count"] == 0

    def test_sensitive_input_not_logged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_path)

            rec = logger.log(
                execution_id="exec-1",
                tool_name="generate_email_draft",
                input_data={
                    "candidate_name": "John",
                    "resume_text": "Very sensitive resume content here.",
                    "job_description": "Sensitive job description.",
                },
                output_status="success",
                duration_seconds=0.5,
            )

            # The input_hash should be present but the actual text should not be in the log
            assert "input_hash" in rec
            assert rec["input_hash"] is not None

            # Read the raw log and verify sensitive text is not present
            with open(log_path, "r", encoding="utf-8") as f:
                log_content = f.read()
            assert "Very sensitive resume content" not in log_content
            assert "Sensitive job description" not in log_content

    def test_singleton_getter(self):
        # Just verify the getter works without interfering with other tests
        logger = get_audit_logger()
        assert logger is not None


class TestAuditLoggerImport:
    def test_imports(self):
        from aegiscore.mcp_audit_logger import AuditLogger
        assert AuditLogger is not None
