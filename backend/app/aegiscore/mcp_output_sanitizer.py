"""AEGISCORE_PHASE2_MCP_OUTPUT_SANITIZER

Tool output sanitization before agent consumption.

Removes executable content, script tags, and other potentially dangerous
content from tool outputs while preserving the structural data agents need.
"""

from __future__ import annotations

import logging
import re
from typing import Any


logger = logging.getLogger("aegiscore.mcp.output_sanitizer")


class OutputSanitizer:
    """Sanitizes MCP tool outputs before agent consumption.

    Removes:
    - HTML/script tags
    - JavaScript event handlers
    - SQL injection patterns
    - Path traversal sequences
    - Internal file paths
    - Sensitive data patterns
    """

    # HTML/script tags that could execute code
    SCRIPT_TAG_PATTERN = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
    HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
    JS_EVENT_PATTERN = re.compile(r"\bon\w+\s*=", re.IGNORECASE)
    # Path traversal
    PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.[/\\]")
    # Internal path patterns
    INTERNAL_PATH_PATTERN = re.compile(r"(/uploads/|/data/|storage_key|aegiscore\.db)")
    # Secret-like patterns
    SECRET_PATTERN = re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*\S+", re.IGNORECASE)

    def __init__(self) -> None:
        pass

    def sanitize(self, output: Any) -> Any:
        """Sanitize a tool output before agent consumption.

        Returns a sanitized copy of the output. Does not modify the original.
        """
        if output is None:
            return None
        if isinstance(output, dict):
            return self._sanitize_dict(output)
        if isinstance(output, list):
            return self._sanitize_list(output)
        if isinstance(output, str):
            return self._sanitize_string(output)
        return output

    def _sanitize_dict(self, obj: dict) -> dict:
        sanitized = {}
        for key, value in obj.items():
            # Sanitize the key too
            safe_key = self._sanitize_string(key) if isinstance(key, str) else key
            sanitized[safe_key] = self.sanitize(value)
        return sanitized

    def _sanitize_list(self, obj: list) -> list:
        return [self.sanitize(item) for item in obj]

    def _sanitize_string(self, text: str) -> str:
        if not isinstance(text, str):
            return text

        # Remove script tags
        text = self.SCRIPT_TAG_PATTERN.sub("", text)
        # Remove remaining HTML tags
        text = self.HTML_TAG_PATTERN.sub("", text)
        # Remove JS event handlers
        text = self.JS_EVENT_PATTERN.sub("", text)
        # Remove path traversal
        text = self.PATH_TRAVERSAL_PATTERN.sub("", text)
        # Remove internal path references
        text = self.INTERNAL_PATH_PATTERN.sub("[REDACTED_PATH]", text)
        # Remove secret patterns
        text = self.SECRET_PATTERN.sub("[REDACTED_SECRET]", text)

        return text

    def contains_dangerous_content(self, output: Any) -> bool:
        """Check if output contains potentially dangerous content."""
        if output is None:
            return False
        if isinstance(output, str):
            return self._string_has_danger(text=output)
        if isinstance(output, dict):
            for key, value in output.items():
                if self.contains_dangerous_content(key) or self.contains_dangerous_content(value):
                    return True
            return False
        if isinstance(output, list):
            for item in output:
                if self.contains_dangerous_content(item):
                    return True
            return False
        return False

    def _string_has_danger(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        return bool(
            self.SCRIPT_TAG_PATTERN.search(text)
            or self.HTML_TAG_PATTERN.search(text)
            or self.JS_EVENT_PATTERN.search(text)
            or self.PATH_TRAVERSAL_PATTERN.search(text)
            or self.INTERNAL_PATH_PATTERN.search(text)
            or self.SECRET_PATTERN.search(text)
        )


# Module-level singleton
_sanitizer: OutputSanitizer | None = None


def get_output_sanitizer() -> OutputSanitizer:
    """Return the singleton output sanitizer."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = OutputSanitizer()
    return _sanitizer
