"""AEGISCORE_PHASE1_JOB_ANALYSIS_AGENT
Multi-Agent Orchestration Engine — Job Analysis Agent.

Compares resume skills with job-description skills using the existing
deterministic V1 skill matcher. This percentage measures detected skill
overlap; it is not a prediction of hiring success.
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
from aegiscore.job_analysis import analyze_resume


logger = logging.getLogger("aegiscore.agent.job_analysis")


class JobAnalysisAgent(BaseAgent):
    """Analyzes resume/job-description skill overlap deterministically."""

    def __init__(self) -> None:
        config = AgentConfig(
            name="job_analysis",
            capabilities=[AgentCapability.JOB_ANALYSIS],
            timeout_seconds=30,
            max_retries=1,
            system_prompt=(
                "You are the AegisCore Job Analysis Agent. Compare resume "
                "skills with job-description skills deterministically."
            ),
        )
        super().__init__(config)

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        payload = context.payload
        resume_text = payload.get("resume_text", "")
        job_description = payload.get("job_description", "")

        if not isinstance(resume_text, str) or not resume_text.strip():
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error="resume_text must be non-empty text.",
                execution_id=context.execution_id,
            )
        if not isinstance(job_description, str) or not job_description.strip():
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error="job_description must be non-empty text.",
                execution_id=context.execution_id,
            )

        try:
            analysis = analyze_resume(resume_text, job_description)
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
            result=analysis,
            execution_id=context.execution_id,
        )
