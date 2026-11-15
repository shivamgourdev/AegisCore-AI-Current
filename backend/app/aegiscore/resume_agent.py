"""AEGISCORE_PHASE1_RESUME_AGENT
Multi-Agent Orchestration Engine — Resume Analysis Agent.

Extracts text from a stored PDF resume and prepares it for reuse in job
analysis. Reuses the existing V1 extraction pipeline; does not duplicate
business logic.
"""

from __future__ import annotations

import logging
from typing import Any

from aegiscore.agent_base import (
    AgentCapability,
    AgentConfig,
    AgentExecutionContext,
    AgentResult,
    AgentStatus,
    BaseAgent,
)
from aegiscore.document_service import get_resume_attachment
from aegiscore.extraction_service import extract_document


logger = logging.getLogger("aegiscore.agent.resume")


class ResumeAnalysisAgent(BaseAgent):
    """Extracts and validates resume text from a stored PDF document."""

    def __init__(self) -> None:
        config = AgentConfig(
            name="resume_analysis",
            capabilities=[AgentCapability.RESUME_ANALYSIS],
            timeout_seconds=60,
            max_retries=2,
            system_prompt=(
                "You are the AegisCore Resume Analysis Agent. Extract and "
                "validate resume text from a stored PDF document."
            ),
        )
        super().__init__(config)

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        payload = context.payload
        document_id = payload.get("document_id", "")

        if not isinstance(document_id, str) or not document_id.strip():
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error="A valid document_id is required.",
                execution_id=context.execution_id,
            )

        try:
            metadata, storage_path = get_resume_attachment(document_id.strip())
        except Exception as exc:  # noqa: BLE001 — agent boundary
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error=f"Resume attachment not found or invalid: {exc}",
                execution_id=context.execution_id,
            )

        try:
            content = storage_path.read_bytes()
        except OSError as exc:
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error=f"Could not read stored resume file: {exc}",
                execution_id=context.execution_id,
            )

        try:
            extraction = extract_document(metadata["filename"], content)
        except Exception as exc:  # noqa: BLE001 — agent boundary
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error=f"Resume text extraction failed: {exc}",
                execution_id=context.execution_id,
            )

        if extraction.status != "text_extracted" or not extraction.full_text.strip():
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error=(
                    "No readable text found in the resume. This may be a "
                    "scanned or image-only PDF; OCR is not available."
                ),
                execution_id=context.execution_id,
            )

        return AgentResult(
            agent_name=self.config.name,
            status=AgentStatus.COMPLETED,
            result={
                "document_id": document_id,
                "filename": metadata["filename"],
                "sha256": metadata["sha256"],
                "size_bytes": metadata["size_bytes"],
                "uploaded_at": metadata["uploaded_at"],
                "resume_text": extraction.full_text,
                "pages": [
                    {"page_number": p.page_number, "text": p.text}
                    for p in extraction.pages
                ],
                "page_count": len(extraction.pages),
                "character_count": len(extraction.full_text),
            },
            execution_id=context.execution_id,
        )
