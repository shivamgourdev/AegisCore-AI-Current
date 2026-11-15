"""AEGISCORE_PHASE2_TESTS_OUTPUT_SANITIZER

Unit tests for MCP tool output sanitization.
"""

import pytest

from aegiscore.mcp_output_sanitizer import OutputSanitizer, get_output_sanitizer


class TestOutputSanitizer:
    def setup_method(self):
        self.sanitizer = OutputSanitizer()

    def test_sanitize_dict(self):
        output = {"name": "test", "value": 42}
        result = self.sanitizer.sanitize(output)
        assert result == {"name": "test", "value": 42}

    def test_sanitize_removes_script_tags(self):
        output = {"content": "<script>alert('xss')</script>Hello"}
        result = self.sanitizer.sanitize(output)
        assert "<script>" not in result["content"]
        assert "alert" not in result["content"]
        assert "Hello" in result["content"]

    def test_sanitize_removes_html_tags(self):
        output = {"content": "<b>bold</b> text"}
        result = self.sanitizer.sanitize(output)
        assert "<b>" not in result["content"]
        assert "bold" in result["content"]

    def test_sanitize_removes_path_traversal(self):
        output = {"path": "../../../etc/passwd"}
        result = self.sanitizer.sanitize(output)
        assert ".." not in result["path"]

    def test_sanitize_removes_internal_paths(self):
        output = {"storage": "/uploads/doc.txt"}
        result = self.sanitizer.sanitize(output)
        assert "/uploads/" not in result["storage"]
        assert "[REDACTED_PATH]" in result["storage"]

    def test_sanitize_removes_secrets(self):
        output = {"config": "api_key=sk-1234567890"}
        result = self.sanitizer.sanitize(output)
        assert "sk-1234567890" not in result["config"]
        assert "[REDACTED_SECRET]" in result["config"]

    def test_sanitize_preserves_safe_content(self):
        output = {"filename": "report.pdf", "size": 1024}
        result = self.sanitizer.sanitize(output)
        assert result["filename"] == "report.pdf"
        assert result["size"] == 1024

    def test_contains_dangerous_content(self):
        assert self.sanitizer.contains_dangerous_content({"text": "<script>bad</script>"}) is True
        assert self.sanitizer.contains_dangerous_content({"text": "safe content"}) is False
        assert self.sanitizer.contains_dangerous_content(None) is False

    def test_nested_sanitization(self):
        output = {
            "level1": {
                "level2": "<script>bad</script>",
                "safe": "ok",
            }
        }
        result = self.sanitizer.sanitize(output)
        assert "<script>" not in result["level1"]["level2"]
        assert result["level1"]["safe"] == "ok"

    def test_list_sanitization(self):
        output = {"items": ["<script>bad</script>", "safe"]}
        result = self.sanitizer.sanitize(output)
        assert "<script>" not in result["items"][0]
        assert result["items"][1] == "safe"

    def test_singleton(self):
        s1 = get_output_sanitizer()
        s2 = get_output_sanitizer()
        assert s1 is s2
