"""AEGISCORE_PHASE2_MCP_TOOL_REGISTRY

MCP Tool Registry — fixed allowlist of 7 approved tools with permission classification.

No dynamic tool loading. All tools map to existing V1 business logic functions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


logger = logging.getLogger("aegiscore.mcp.tool_registry")


class ToolPermission(str, Enum):
    READ_ONLY = "read_only"
    STATE_CHANGING = "state_changing"


@dataclass(frozen=True)
class ToolDefinition:
    """Immutable definition of an approved MCP tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permission: ToolPermission
    v1_function: str  # dotted path to the V1 function this tool wraps
    timeout_seconds: int = 30
    max_retries: int = 2
    max_output_size: int = 1_048_576  # 1 MB


class MCPToolRegistry:
    """Fixed allowlist registry of approved MCP tools.

    Tools are registered once at module load. No dynamic loading.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the 7 approved MCP tools with strict schemas."""

        # search_knowledge — dense/sparse/hybrid retrieval
        self.register(
            ToolDefinition(
                name="search_knowledge",
                description="Search uploaded documents using dense, sparse, or hybrid retrieval. Returns source-grounded results with citations.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 5000},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
                        "mode": {"type": "string", "enum": ["dense", "sparse", "hybrid"], "default": "hybrid"},
                        "min_similarity": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.45},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "mode": {"type": "string"},
                        "result_count": {"type": "integer"},
                        "results": {"type": "array"},
                    },
                    "required": ["query", "mode", "result_count", "results"],
                    "additionalProperties": False,
                },
                permission=ToolPermission.READ_ONLY,
                v1_function="aegiscore.sparse_search.search_sparse_chunks",
                timeout_seconds=60,
                max_retries=2,
                max_output_size=1_048_576,
            )
        )

        # get_document_status — per-document status
        self.register(
            ToolDefinition(
                name="get_document_status",
                description="Return per-document status: extraction, chunks, and embeddings.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "minLength": 1, "maxLength": 100},
                    },
                    "required": ["document_id"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string"},
                        "filename": {"type": "string"},
                        "extension": {"type": "string"},
                        "status": {"type": "string"},
                        "page_count": {"type": "integer"},
                        "chunk_count": {"type": "integer"},
                        "embedding_count": {"type": "integer"},
                    },
                    "required": ["document_id", "filename", "extension", "status"],
                    "additionalProperties": False,
                },
                permission=ToolPermission.READ_ONLY,
                v1_function="aegiscore.document_service.list_documents",
                timeout_seconds=10,
                max_retries=1,
                max_output_size=65_536,
            )
        )

        # list_documents — list all registered documents
        self.register(
            ToolDefinition(
                name="list_documents",
                description="List all registered documents with metadata.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "documents": {"type": "array"},
                    },
                    "required": ["documents"],
                    "additionalProperties": False,
                },
                permission=ToolPermission.READ_ONLY,
                v1_function="aegiscore.document_service.list_documents",
                timeout_seconds=10,
                max_retries=1,
                max_output_size=65_536,
            )
        )

        # analyze_resume — deterministic skill matching
        self.register(
            ToolDefinition(
                name="analyze_resume",
                description="Compare resume skills with job-description skills deterministically.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "resume_text": {"type": "string", "minLength": 1, "maxLength": 50000},
                        "job_description": {"type": "string", "minLength": 1, "maxLength": 50000},
                    },
                    "required": ["resume_text", "job_description"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "matched_skills": {"type": "array"},
                        "missing_skills": {"type": "array"},
                        "match_percentage": {"type": "integer"},
                    },
                    "required": ["matched_skills", "missing_skills", "match_percentage"],
                    "additionalProperties": False,
                },
                permission=ToolPermission.READ_ONLY,
                v1_function="aegiscore.job_analysis.analyze_resume",
                timeout_seconds=30,
                max_retries=1,
                max_output_size=65_536,
            )
        )

        # analyze_job_description — wrapper around analyze_resume
        self.register(
            ToolDefinition(
                name="analyze_job_description",
                description="Analyze a job description against a resume using deterministic skill matching.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "resume_text": {"type": "string", "minLength": 1, "maxLength": 50000},
                        "job_description": {"type": "string", "minLength": 1, "maxLength": 50000},
                    },
                    "required": ["resume_text", "job_description"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "matched_skills": {"type": "array"},
                        "missing_skills": {"type": "array"},
                        "match_percentage": {"type": "integer"},
                    },
                    "required": ["matched_skills", "missing_skills", "match_percentage"],
                    "additionalProperties": False,
                },
                permission=ToolPermission.READ_ONLY,
                v1_function="aegiscore.job_analysis.analyze_resume",
                timeout_seconds=30,
                max_retries=1,
                max_output_size=65_536,
            )
        )

        # generate_email_draft — state-changing, requires approval
        self.register(
            ToolDefinition(
                name="generate_email_draft",
                description="Generate a professional job-application email draft bound to a verified PDF resume attachment.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "candidate_name": {"type": "string", "minLength": 1, "maxLength": 5000},
                        "recipient_email": {"type": "string", "minLength": 1, "maxLength": 5000},
                        "job_title": {"type": "string", "minLength": 1, "maxLength": 5000},
                        "company_name": {"type": "string", "minLength": 1, "maxLength": 5000},
                        "resume_summary": {"type": "string", "minLength": 1, "maxLength": 5000},
                        "resume_document_id": {"type": "string", "minLength": 1, "maxLength": 100},
                        "confirm": {"type": "boolean", "default": False},
                    },
                    "required": [
                        "candidate_name",
                        "recipient_email",
                        "job_title",
                        "company_name",
                        "resume_summary",
                        "resume_document_id",
                    ],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "draft": {"type": "object"},
                        "attachment_document_id": {"type": "string"},
                        "attachment_filename": {"type": "string"},
                        "attachment_sha256": {"type": "string"},
                        "requires_user_approval": {"type": "boolean"},
                        "sent": {"type": "boolean"},
                    },
                    "required": [
                        "draft",
                        "attachment_document_id",
                        "attachment_filename",
                        "attachment_sha256",
                        "requires_user_approval",
                        "sent",
                    ],
                    "additionalProperties": False,
                },
                permission=ToolPermission.STATE_CHANGING,
                v1_function="aegiscore.job_email.generate_job_email",
                timeout_seconds=30,
                max_retries=1,
                max_output_size=65_536,
            )
        )

        # get_resume_attachment — SHA-256 verified attachment retrieval
        self.register(
            ToolDefinition(
                name="get_resume_attachment",
                description="Retrieve verified resume attachment metadata with SHA-256 integrity verification.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "minLength": 1, "maxLength": 100},
                    },
                    "required": ["document_id"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string"},
                        "filename": {"type": "string"},
                        "extension": {"type": "string"},
                        "content_type": {"type": "string"},
                        "size_bytes": {"type": "integer"},
                        "sha256": {"type": "string"},
                        "uploaded_at": {"type": "string"},
                    },
                    "required": ["document_id", "filename", "extension", "sha256"],
                    "additionalProperties": False,
                },
                permission=ToolPermission.READ_ONLY,
                v1_function="aegiscore.document_service.get_resume_attachment",
                timeout_seconds=10,
                max_retries=1,
                max_output_size=65_536,
            )
        )

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition. Frozen after module load in production."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return sorted(self._tools.values(), key=lambda t: t.name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def read_only_tools(self) -> list[ToolDefinition]:
        """Return all read-only tools."""
        return [t for t in self._tools.values() if t.permission == ToolPermission.READ_ONLY]

    def state_changing_tools(self) -> list[ToolDefinition]:
        """Return all state-changing tools."""
        return [t for t in self._tools.values() if t.permission == ToolPermission.STATE_CHANGING]
