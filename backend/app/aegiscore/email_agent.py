"""AEGISCORE_PHASE1_EMAIL_AGENT
Multi-Agent Orchestration Engine — Job Application Email Draft Agent.

Generates a professional job-application email draft bound to a verified
PDF resume attachment. Never sends email; approval is explicit and
review-only.
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
from aegiscore.job_email import generate_job_email


logger = logging.getLogger("aegiscore.agent.email")


class JobApplicationEmailDraftAgent(BaseAgent):
    """Generates a reviewable email draft with a verified resume attachment."""

    def __init__(self) -> None:
        config = AgentConfig(
            name="job_application_email",
            capabilities=[AgentCapability.EMAIL_DRAFT],
            timeout_seconds=30,
            max_retries=1,
            system_prompt=(
                "You are the AegisCore Job Application Email Draft Agent. "
                "Generate a professional email draft bound to a verified "
                "resume attachment. Never send email."
            ),
        )
        super().__init__(config)

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        payload = context.payload

        required = (
            "candidate_name",
            "recipient_email",
            "job_title",
            "company_name",
            "resume_summary",
            "resume_document_id",
        )
        for field in required:
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                return AgentResult(
                    agent_name=self.config.name,
                    status=AgentStatus.FAILED,
                    error=f"Missing or invalid draft field: {field}",
                    execution_id=context.execution_id,
                )

        resume_document_id = payload["resume_document_id"].strip()

        # Verify the resume attachment exists and passes SHA-256 integrity.
        try:
            metadata, _storage_path = get_resume_attachment(resume_document_id)
        except Exception as exc:  # noqa: BLE001 — agent boundary
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error=f"Resume attachment integrity check failed: {exc}",
                execution_id=context.execution_id,
            )

        try:
            draft = generate_job_email(
                candidate_name=payload["candidate_name"].strip(),
                recipient_email=payload["recipient_email"].strip(),
                job_title=payload["job_title"].strip(),
                company_name=payload["company_name"].strip(),
                resume_summary=payload["resume_summary"].strip(),
            )
        except ValueError as exc:
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error=str(exc),
                execution_id=context.execution_id,
            )

        return AgentResult(
            agent_name=self.config.name,
            status=AgentStatus.COMPLETED,
            result={
                "draft": draft,
                "attachment_document_id": metadata["document_id"],
                "attachment_filename": metadata["filename"],
                "attachment_sha256": metadata["sha256"],
                "requires_user_approval": True,
                "sent": False,
            },
            execution_id=context.execution_id,
        )
