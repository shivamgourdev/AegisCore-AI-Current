"""AEGISCORE_PHASE2_MCP_AGENT_INTEGRATION

Agent-to-MCP integration layer for Phase 1 specialist agents.

Integrates MCP tool execution into existing Phase 1 agents while preserving
their existing interfaces. Agents use MCP tools when available and fall back
to direct V1 calls with the same security policies when MCP is unavailable.

Security:
- Agents only use tools they are authorized for
- No recursive tool execution (depth limited to 1)
- Maximum 3 tool calls per agent task
- Tool outputs treated as untrusted data — validated before agent consumption
- Tool results kept separate from trusted system instructions
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aegiscore.agent_base import (
    AgentCapability,
    AgentExecutionContext,
    AgentResult,
    AgentStatus,
    BaseAgent,
)
from aegiscore.mcp_client import get_mcp_client
from aegiscore.mcp_execution_engine import ExecutionResult


logger = logging.getLogger("aegiscore.mcp.agent_integration")


class MCPToolCallError(Exception):
    """Raised when an MCP tool call fails and fallback is not possible."""


class AgentMCPIntegration:
    """Base integration for agents to optionally use MCP tools.

    Wraps an existing Phase 1 agent and adds MCP tool capability.
    When MCP is available, the agent can route through MCP tools.
    When MCP is unavailable, falls back to direct V1 calls.
    """

    def __init__(
        self,
        agent: BaseAgent,
        mcp_client=None,
        max_tool_calls: int = 3,
        max_tool_depth: int = 1,
    ) -> None:
        self.agent = agent
        self.mcp_client = mcp_client or get_mcp_client()
        self.max_tool_calls = max_tool_calls
        self.max_tool_depth = max_tool_depth
        self._tool_call_count = 0
        self._tool_depth = 0
        self.logger = logging.getLogger(f"aegiscore.mcp.agent_integration.{agent.name}")

    async def execute_with_mcp(
        self,
        context: AgentExecutionContext,
        direct_execute: Any,
    ) -> AgentResult:
        """Execute the agent's task, optionally using MCP tools.

        Args:
            context: The agent execution context.
            direct_execute: Callable that performs the direct V1 execution
                (the agent's original execute logic).

        Returns an AgentResult. MCP tool results are treated as untrusted
        data and validated before use.
        """
        self._tool_call_count = 0
        self._tool_depth = 0

        # Check if MCP is available
        if not self.mcp_client.is_connected:
            # MCP unavailable — use direct V1 execution with same security policies
            self.logger.debug("MCP unavailable, using direct V1 execution.")
            return await direct_execute(context)

        # Try MCP execution
        try:
            return await self._execute_via_mcp(context, direct_execute)
        except Exception as exc:  # noqa: BLE001 — integration boundary
            self.logger.warning("MCP execution failed: %s — falling back to direct V1.", exc)
            # Fallback preserves same security policies
            return await direct_execute(context)

    async def _execute_via_mcp(
        self,
        context: AgentExecutionContext,
        direct_execute: Any,
    ) -> AgentResult:
        """Execute via MCP tool with depth and call limits."""
        self._tool_depth += 1
        if self._tool_depth > self.max_tool_depth:
            self.logger.warning("Maximum tool depth (%d) exceeded.", self.max_tool_depth)
            return await direct_execute(context)

        self._tool_call_count += 1
        if self._tool_call_count > self.max_tool_calls:
            self.logger.warning("Maximum tool calls (%d) exceeded.", self.max_tool_calls)
            return await direct_execute(context)

        # Determine which MCP tool to use based on agent capability
        tool_name = self._map_agent_capability_to_tool(context.task_type)
        if tool_name is None:
            # No MCP tool for this task — use direct execution
            return await direct_execute(context)

        # Execute through MCP client
        mcp_result = await self.mcp_client.execute_tool(tool_name, context.payload)

        if not mcp_result.success:
            self.logger.warning(
                "MCP tool '%s' failed: %s — falling back to direct V1.",
                tool_name,
                mcp_result.error,
            )
            return await direct_execute(context)

        # Validate tool output before agent consumption
        validated_output = self._validate_tool_output(tool_name, mcp_result.data)
        if validated_output is None:
            self.logger.warning(
                "MCP tool '%s' output failed validation — falling back to direct V1.",
                tool_name,
            )
            return await direct_execute(context)

        # Build AgentResult from validated MCP output
        self._tool_depth -= 1
        return AgentResult(
            agent_name=self.agent.name,
            status=AgentStatus.COMPLETED,
            result=validated_output,
            execution_id=context.execution_id,
            duration_seconds=mcp_result.duration_seconds,
            attempts=mcp_result.attempts,
        )

    def _map_agent_capability_to_tool(self, task_type: str) -> str | None:
        """Map an agent's task type to an MCP tool name."""
        mapping = {
            AgentCapability.RAG_QUESTION_ANSWER.value: "search_knowledge",
            AgentCapability.RESUME_ANALYSIS.value: "get_resume_attachment",
            AgentCapability.JOB_ANALYSIS.value: "analyze_resume",
            AgentCapability.EMAIL_DRAFT.value: "generate_email_draft",
        }
        return mapping.get(task_type)

    def _validate_tool_output(
        self,
        tool_name: str,
        output: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Validate tool output against expected schema.

        Tool outputs are treated as untrusted data. Returns None if invalid.
        """
        if not isinstance(output, dict):
            return None

        # Basic structural validation per tool
        if tool_name == "search_knowledge":
            if "results" not in output or "query" not in output:
                return None
            if not isinstance(output["results"], list):
                return None
            return output

        if tool_name == "get_resume_attachment":
            if "document_id" not in output or "sha256" not in output:
                return None
            return output

        if tool_name == "analyze_resume":
            if "matched_skills" not in output or "match_percentage" not in output:
                return None
            return output

        if tool_name == "generate_email_draft":
            if "draft" not in output or "sent" not in output:
                return None
            if output.get("sent") is True:
                # Never accept a result claiming email was sent
                return None
            return output

        if tool_name == "get_document_status":
            if "document_id" not in output or "status" not in output:
                return None
            return output

        if tool_name == "list_documents":
            if "documents" not in output or not isinstance(output["documents"], list):
                return None
            return output

        # Unknown tool — reject output for safety
        return None

    def get_stats(self) -> dict[str, Any]:
        """Return integration statistics."""
        return {
            "tool_call_count": self._tool_call_count,
            "max_tool_calls": self.max_tool_calls,
            "max_tool_depth": self.max_tool_depth,
            "mcp_connected": self.mcp_client.is_connected,
            "mcp_fallback": self.mcp_client.is_fallback,
        }


def create_integrated_agent(
    agent: BaseAgent,
    mcp_client=None,
    max_tool_calls: int = 3,
    max_tool_depth: int = 1,
) -> AgentMCPIntegration:
    """Create an MCP-integrated wrapper for a Phase 1 agent.

    The original agent's interface is preserved. Use .execute() for direct
    V1 execution, or .execute_with_mcp() for MCP-routed execution.
    """
    return AgentMCPIntegration(
        agent=agent,
        mcp_client=mcp_client,
        max_tool_calls=max_tool_calls,
        max_tool_depth=max_tool_depth,
    )


# Module-level integration registry
_integrations: dict[str, AgentMCPIntegration] = {}


def register_integration(agent_name: str, integration: AgentMCPIntegration) -> None:
    """Register an agent integration."""
    _integrations[agent_name] = integration


def get_integration(agent_name: str) -> AgentMCPIntegration | None:
    """Get a registered agent integration."""
    return _integrations.get(agent_name)
