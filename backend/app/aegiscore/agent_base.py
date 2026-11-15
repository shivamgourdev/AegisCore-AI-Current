"""AEGISCORE_PHASE1_AGENT_BASE
Multi-Agent Orchestration Engine — Agent Foundation.

Defines the agent base interface, registry, configuration, input/output
schemas, execution context, and structured result types used by all
specialist agents and the supervisor agent.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


logger = logging.getLogger("aegiscore.agent")


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ABSTAINED = "abstained"


class AgentCapability(str, Enum):
    RAG_QUESTION_ANSWER = "rag_question_answer"
    RESUME_ANALYSIS = "resume_analysis"
    JOB_ANALYSIS = "job_analysis"
    EMAIL_DRAFT = "email_draft"


@dataclass
class AgentConfig:
    name: str
    capabilities: list[AgentCapability]
    timeout_seconds: int = 120
    max_retries: int = 2
    enabled: bool = True
    system_prompt: str | None = None


@dataclass
class AgentInput:
    task_type: str
    payload: dict[str, Any]
    execution_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    agent_name: str
    status: AgentStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    execution_id: str = ""
    duration_seconds: float = 0.0
    attempts: int = 1
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class AgentExecutionContext:
    execution_id: str
    task_type: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    attempts: int = 0
    max_attempts: int = 3


class AgentRegistry:
    """Thread-safe registry of available agents keyed by name."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._lock = asyncio.Lock()

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.config.name] = agent

    def unregister(self, name: str) -> None:
        self._agents.pop(name, None)

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        return sorted(self._agents.keys())

    def find_by_capability(self, capability: AgentCapability) -> list[BaseAgent]:
        return [
            agent
            for agent in self._agents.values()
            if agent.config.enabled and capability in agent.config.capabilities
        ]

    def clear(self) -> None:
        self._agents.clear()


class BaseAgent(ABC):
    """Abstract base class for all AegisCore agents.

    Agents must implement ``execute``. They receive an
    ``AgentExecutionContext`` and return an ``AgentResult``.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(f"aegiscore.agent.{config.name}")

    @abstractmethod
    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        """Execute the agent's task and return a structured result."""
        raise NotImplementedError

    async def run_with_retries(self, context: AgentExecutionContext) -> AgentResult:
        """Execute with bounded retries and timeout enforcement."""
        attempts = 0
        max_attempts = self.config.max_retries + 1
        last_error: str | None = None

        while attempts < max_attempts:
            attempts += 1
            context.attempts = attempts

            try:
                result = await asyncio.wait_for(
                    self.execute(context),
                    timeout=self.config.timeout_seconds,
                )
                result.attempts = attempts
                if result.status in (AgentStatus.COMPLETED, AgentStatus.ABSTAINED):
                    return result
                # Treat non-completion as retryable unless explicitly abstained.
                if result.status == AgentStatus.FAILED and result.error:
                    last_error = result.error
                    continue
                return result
            except asyncio.TimeoutError:
                last_error = f"agent timed out after {self.config.timeout_seconds}s"
                self.logger.warning(
                    "Agent %s attempt %d timed out", self.config.name, attempts
                )
                continue
            except Exception as exc:  # noqa: BLE001 — agent boundary catches all
                last_error = str(exc)
                self.logger.exception(
                    "Agent %s attempt %d failed: %s", self.config.name, attempts, exc
                )
                continue

        return AgentResult(
            agent_name=self.config.name,
            status=AgentStatus.FAILED,
            error=last_error or "agent execution failed",
            execution_id=context.execution_id,
            duration_seconds=time.time() - context.start_time,
            attempts=attempts,
        )

    @property
    def name(self) -> str:
        return self.config.name


class AgentOrchestrator:
    """Coordinates agent execution through the registry."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    async def run_agent(
        self, name: str, context: AgentExecutionContext
    ) -> AgentResult:
        agent = self.registry.get(name)
        if agent is None:
            return AgentResult(
                agent_name=name,
                status=AgentStatus.FAILED,
                error=f"Agent '{name}' is not registered.",
                execution_id=context.execution_id,
            )
        if not agent.config.enabled:
            return AgentResult(
                agent_name=name,
                status=AgentStatus.FAILED,
                error=f"Agent '{name}' is disabled.",
                execution_id=context.execution_id,
                skipped=True,
                skip_reason="agent disabled",
            )
        return await agent.run_with_retries(context)

    async def run_first_available(
        self, capability: AgentCapability, context: AgentExecutionContext
    ) -> AgentResult:
        candidates = self.registry.find_by_capability(capability)
        if not candidates:
            return AgentResult(
                agent_name="orchestrator",
                status=AgentStatus.FAILED,
                error=f"No agent registered for capability '{capability.value}'.",
                execution_id=context.execution_id,
            )
        # Try each candidate in order; return the first successful result.
        last_error: str | None = None
        for agent in candidates:
            result = await agent.run_with_retries(context)
            if result.status in (AgentStatus.COMPLETED, AgentStatus.ABSTAINED):
                return result
            last_error = result.error
        return AgentResult(
            agent_name="orchestrator",
            status=AgentStatus.FAILED,
            error=last_error or "all agents failed for capability "
            f"'{capability.value}'.",
            execution_id=context.execution_id,
        )
