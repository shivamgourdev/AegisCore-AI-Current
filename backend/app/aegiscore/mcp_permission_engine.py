"""AEGISCORE_PHASE2_MCP_PERMISSION_ENGINE

Permission and approval policy engine for MCP tool execution.

Distinguishes read-only vs state-changing tools. State-changing tools
require explicit confirmation AND valid draft/attachment verification
(confirm: true alone is NOT sufficient).
"""

from __future__ import annotations

import logging
from typing import Any

from aegiscore.mcp_tool_registry import MCPToolRegistry, ToolPermission


logger = logging.getLogger("aegiscore.mcp.permission")


class PermissionDecision(str):
    """Permission decision outcomes."""
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    CONFIRMATION_INSUFFICIENT = "confirmation_insufficient"


class PermissionEngine:
    """Evaluates permission for MCP tool execution."""

    def __init__(self, registry: MCPToolRegistry) -> None:
        self.registry = registry
        # Track pending drafts: document_id -> {sha256, document_id}
        # This mirrors the V1 draft storage state
        self._verified_drafts: dict[str, dict[str, str]] = {}

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[str, str | None]:
        """Evaluate whether a tool execution is permitted.

        Returns (decision, reason). Decision is one of:
        - ALLOWED: read-only tool, no restrictions
        - REQUIRES_CONFIRMATION: state-changing tool without confirm
        - CONFIRMATION_INSUFFICIENT: state-changing with confirm but invalid attachment
        - DENIED: tool not found or other denial
        - ALLOWED with confirmation_valid: state-changing with confirm AND valid attachment
        """
        tool = self.registry.get(tool_name)
        if tool is None:
            return PermissionDecision.DENIED, f"Tool '{tool_name}' is not in the approved allowlist."

        if tool.permission == ToolPermission.READ_ONLY:
            return PermissionDecision.ALLOWED, "Read-only tool."

        # State-changing tool
        confirm = arguments.get("confirm", False)
        if not confirm:
            return PermissionDecision.REQUIRES_CONFIRMATION, (
                f"State-changing tool '{tool_name}' requires explicit confirmation."
            )

        # confirm: true is necessary but NOT sufficient
        # Must verify draft existence and attachment match
        document_id = arguments.get("resume_document_id", "")
        if not document_id:
            return PermissionDecision.CONFIRMATION_INSUFFICIENT, (
                "State-changing tool requires a valid resume_document_id."
            )

        # Verify against known drafts (mirrors V1 draft storage)
        if document_id not in self._verified_drafts:
            return PermissionDecision.CONFIRMATION_INSUFFICIENT, (
                f"No verified draft found for document_id '{document_id}'. "
                "confirm: true alone is not sufficient."
            )

        stored = self._verified_drafts[document_id]
        provided_sha256 = arguments.get("attachment_sha256", "")
        if provided_sha256 != stored.get("sha256", ""):
            return PermissionDecision.CONFIRMATION_INSUFFICIENT, (
                f"Attachment SHA-256 mismatch for document_id '{document_id}'. "
                "confirm: true alone is not sufficient."
            )

        provided_doc_id = arguments.get("attachment_document_id", "")
        if provided_doc_id != stored.get("document_id", ""):
            return PermissionDecision.CONFIRMATION_INSUFFICIENT, (
                f"Attachment document_id mismatch for '{document_id}'. "
                "confirm: true alone is not sufficient."
            )

        return PermissionDecision.ALLOWED, "State-changing tool confirmed with valid attachment."

    def record_verified_draft(
        self,
        document_id: str,
        sha256: str,
        attachment_document_id: str | None = None,
    ) -> None:
        """Record a verified draft in the permission engine's tracking.

        This mirrors the V1 draft storage state so the permission engine
        can validate that confirm: true corresponds to a real, reviewed draft.
        """
        self._verified_drafts[document_id] = {
            "document_id": attachment_document_id or document_id,
            "sha256": sha256,
        }
        logger.info("Recorded verified draft for document_id: %s", document_id)

    def clear_draft(self, document_id: str) -> None:
        """Remove a draft from tracking (e.g., after approval or revocation)."""
        self._verified_drafts.pop(document_id, None)

    def is_state_changing(self, tool_name: str) -> bool:
        """Check if a tool is state-changing."""
        tool = self.registry.get(tool_name)
        if tool is None:
            return False
        return tool.permission == ToolPermission.STATE_CHANGING
