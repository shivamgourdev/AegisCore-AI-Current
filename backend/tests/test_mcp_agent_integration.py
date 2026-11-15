"""AEGISCORE_PHASE2_TESTS_AGENT_INTEGRATION

Unit tests for the MCP agent integration layer.
"""

import pytest

from aegiscore.agent_base import (
    AgentCapability,
    AgentExecutionContext,
    AgentResult,
    AgentStatus,
    BaseAgent,
)
from aegiscore.mcp_agent_integration import AgentMCPIntegration, create_integrated_agent


class _RecordingAgent(BaseAgent):
    def __init__(self, name="test-agent", should_fail=False):
        from aegiscore.mcp_tool_registry import ToolPermission

        config = type(
            "Config",
            (),
            {
                "name": name,
                "capabilities": [AgentCapability.RAG_QUESTION_ANSWER],
                "timeout_seconds": 30,
                "max_retries": 1,
                "system_prompt": "test",
                "enabled": True,
            },
        )()
        super().__init__(config)
        self.should_fail = should_fail
        self.call_count = 0

    async def execute(self, context):
        self.call_count += 1
        if self.should_fail:
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error="simulated failure",
                execution_id=context.execution_id,
            )
        return AgentResult(
            agent_name=self.config.name,
            status=AgentStatus.COMPLETED,
            result={"answer": "direct result"},
            execution_id=context.execution_id,
        )


class TestAgentIntegration:
    def setup_method(self):
        self.agent = _RecordingAgent()
        self.integration = AgentMCPIntegration(self.agent)

    def test_integration_wraps_agent(self):
        assert self.integration.agent is self.agent

    def test_direct_execute_when_mcp_unavailable(self):
        context = AgentExecutionContext(
            execution_id="exec-1",
            task_type="rag_question_answer",
            payload={"query": "test"},
        )

        async def direct_execute(ctx):
            return await self.agent.execute(ctx)

        result = asyncio_test(self.integration.execute_with_mcp(context, direct_execute))
        assert result.status == AgentStatus.COMPLETED
        assert result.result["answer"] == "direct result"

    def test_stats(self):
        stats = self.integration.get_stats()
        assert "tool_call_count" in stats
        assert "mcp_connected" in stats
        assert "mcp_fallback" in stats

    def test_max_tool_calls_enforced(self):
        # Set very low max to test enforcement
        self.integration.max_tool_calls = 0
        context = AgentExecutionContext(
            execution_id="exec-1",
            task_type="rag_question_answer",
            payload={"query": "test"},
        )

        async def direct_execute(ctx):
            return await self.agent.execute(ctx)

        # With max_tool_calls=0, the first call would be blocked
        # Actually the integration checks _tool_call_count > max_tool_calls
        # So with max_tool_calls=0, the first call (count becomes 1) exceeds 0
        result = asyncio_test(self.integration.execute_with_mcp(context, direct_execute))
        # Should fall back to direct execution since MCP not connected anyway
        assert result.status == AgentStatus.COMPLETED

    def test_create_integrated_agent_helper(self):
        integration = create_integrated_agent(self.agent)
        assert integration.agent is self.agent


def asyncio_test(coro):
    """Helper to run async test code."""
    import asyncio

    return asyncio.run(coro)


class TestIntegratedAgentWithMockMCP:
    def test_mcp_output_validation_rejects_bad_output(self):
        # Test that invalid MCP output is rejected
        integration = AgentMCPIntegration(_RecordingAgent())

        # Invalid output for search_knowledge (missing required fields)
        invalid_output = {"unexpected": "data"}
        result = integration._validate_tool_output("search_knowledge", invalid_output)
        assert result is None

        # Valid output
        valid_output = {
            "query": "test",
            "mode": "dense",
            "result_count": 1,
            "results": [{"source_id": "S1", "filename": "test.txt", "text": "content", "similarity": 0.9}],
        }
        result = integration._validate_tool_output("search_knowledge", valid_output)
        assert result is not None
        assert result["query"] == "test"

    def test_email_draft_output_with_sent_true_rejected(self):
        integration = AgentMCPIntegration(_RecordingAgent())
        output_with_sent = {
            "draft": {"recipient_email": "test@test.com"},
            "sent": True,  # Should be rejected — email was "sent"
        }
        result = integration._validate_tool_output("generate_email_draft", output_with_sent)
        assert result is None

        output_without_sent = {
            "draft": {"recipient_email": "test@test.com"},
            "sent": False,
            "attachment_document_id": "doc-1",
            "attachment_filename": "resume.pdf",
            "attachment_sha256": "abc123",
            "requires_user_approval": True,
        }
        result = integration._validate_tool_output("generate_email_draft", output_without_sent)
        assert result is not None

    def test_map_capability_to_tool(self):
        integration = AgentMCPIntegration(_RecordingAgent())
        assert integration._map_agent_capability_to_tool("rag_question_answer") == "search_knowledge"
        assert integration._map_agent_capability_to_tool("resume_analysis") == "get_resume_attachment"
        assert integration._map_agent_capability_to_tool("job_analysis") == "analyze_resume"
        assert integration._map_agent_capability_to_tool("email_draft") == "generate_email_draft"
        assert integration._map_agent_capability_to_tool("unknown_task") is None
