"""AEGISCORE_PHASE1_SUPERVISOR
Multi-Agent Orchestration Engine — Supervisor Agent.

Classifies incoming task requests, routes them to the appropriate
specialist agent, validates results, and aggregates final responses.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from aegiscore.agent_base import (
    AgentCapability,
    AgentConfig,
    AgentExecutionContext,
    AgentInput,
    AgentResult,
    AgentStatus,
    BaseAgent,
    AgentOrchestrator,
    AgentRegistry,
)


logger = logging.getLogger("aegiscore.agent.supervisor")


class SupervisorAgent(BaseAgent):
    """Routes tasks to specialist agents and aggregates their results."""

    def __init__(self, registry: AgentRegistry) -> None:
        config = AgentConfig(
            name="supervisor",
            capabilities=[],  # Supervisor is a router, not a specialist agent
            timeout_seconds=60,
            max_retries=1,
            system_prompt=(
                "You are the AegisCore supervisor. Classify user requests "
                "into one of: rag_question_answer, resume_analysis, "
                "job_analysis, email_draft."
            ),
        )
        super().__init__(config)
        self.orchestrator = AgentOrchestrator(registry)

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        payload = context.payload
        task_type = context.task_type or payload.get("task_type", "")

        # Classification: map the requested task type to a capability.
        capability = self._classify(task_type)
        if capability is None:
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error=(
                    f"Unknown task type '{task_type}'. Supported types: "
                    "rag_question_answer, resume_analysis, job_analysis, email_draft."
                ),
                execution_id=context.execution_id,
            )

        # Route to the first available specialist agent for this capability.
        agent_context = AgentExecutionContext(
            execution_id=context.execution_id,
            task_type=task_type,
            payload=payload,
            metadata=context.metadata,
            max_attempts=context.max_attempts,
        )

        result = await self.orchestrator.run_first_available(capability, agent_context)

        # Validate and aggregate.
        if result.status == AgentStatus.FAILED:
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error=result.error or "specialist agent failed",
                execution_id=context.execution_id,
                attempts=result.attempts,
            )

        # Wrap the specialist result under the supervisor for aggregation.
        return AgentResult(
            agent_name=self.config.name,
            status=result.status,
            result={
                "task_type": task_type,
                "routed_to": result.agent_name,
                "agent_result": result.result,
                "skipped": result.skipped,
                "skip_reason": result.skip_reason,
            },
            execution_id=context.execution_id,
            duration_seconds=result.duration_seconds,
            attempts=result.attempts,
        )

    @staticmethod
    def _classify(task_type: str) -> AgentCapability | None:
        mapping = {
            "rag_question_answer": AgentCapability.RAG_QUESTION_ANSWER,
            "rag": AgentCapability.RAG_QUESTION_ANSWER,
            "resume_analysis": AgentCapability.RESUME_ANALYSIS,
            "resume": AgentCapability.RESUME_ANALYSIS,
            "job_analysis": AgentCapability.JOB_ANALYSIS,
            "job": AgentCapability.JOB_ANALYSIS,
            "email_draft": AgentCapability.EMAIL_DRAFT,
            "email": AgentCapability.EMAIL_DRAFT,
        }
        return mapping.get(task_type.strip().lower())

    def route(self, task_type: str) -> str | None:
        """Return the capability value for a task type, or None if unknown."""
        capability = self._classify(task_type)
        return capability.value if capability is not None else None

    def classify_and_route(
        self, task_type: str
    ) -> tuple[AgentCapability | None, str | None]:
        """Classify a task type and return (capability, capability_value)."""
        capability = self._classify(task_type)
        return capability, capability.value if capability is not None else None
