"""AEGISCORE_PHASE2_TESTS_TOOL_REGISTRY

Unit tests for the MCP tool registry — fixed allowlist of 7 approved tools.
"""

import pytest

from aegiscore.mcp_tool_registry import MCPToolRegistry, ToolDefinition, ToolPermission


class TestToolRegistry:
    def test_registry_has_seven_tools(self):
        registry = MCPToolRegistry()
        tools = registry.list_tools()
        assert len(tools) == 7

    def test_tool_names(self):
        registry = MCPToolRegistry()
        names = {t.name for t in registry.list_tools()}
        expected = {
            "search_knowledge",
            "get_document_status",
            "list_documents",
            "analyze_resume",
            "analyze_job_description",
            "generate_email_draft",
            "get_resume_attachment",
        }
        assert names == expected

    def test_read_only_tools(self):
        registry = MCPToolRegistry()
        read_only = registry.read_only_tools()
        read_only_names = {t.name for t in read_only}
        assert "generate_email_draft" not in read_only_names
        assert "search_knowledge" in read_only_names
        assert "list_documents" in read_only_names

    def test_state_changing_tools(self):
        registry = MCPToolRegistry()
        state_changing = registry.state_changing_tools()
        state_changing_names = {t.name for t in state_changing}
        assert state_changing_names == {"generate_email_draft"}

    def test_get_existing_tool(self):
        registry = MCPToolRegistry()
        tool = registry.get("search_knowledge")
        assert tool is not None
        assert tool.name == "search_knowledge"
        assert tool.permission == ToolPermission.READ_ONLY

    def test_get_nonexistent_tool(self):
        registry = MCPToolRegistry()
        assert registry.get("nonexistent_tool") is None

    def test_has_tool(self):
        registry = MCPToolRegistry()
        assert registry.has("search_knowledge") is True
        assert registry.has("nonexistent") is False

    def test_tool_has_strict_schema(self):
        registry = MCPToolRegistry()
        tool = registry.get("generate_email_draft")
        assert tool is not None
        assert "required" in tool.input_schema
        assert "resume_document_id" in tool.input_schema["required"]
        assert "confirm" in tool.input_schema["properties"]
        # confirm should not be required (it's a boolean flag)
        assert "confirm" not in tool.input_schema["required"]

    def test_tool_output_schema_has_no_additional_properties(self):
        registry = MCPToolRegistry()
        for tool in registry.list_tools():
            assert tool.output_schema.get("additionalProperties") is False, (
                f"Tool {tool.name} output schema allows additional properties"
            )

    def test_tool_input_schema_has_no_additional_properties(self):
        registry = MCPToolRegistry()
        for tool in registry.list_tools():
            assert tool.input_schema.get("additionalProperties") is False, (
                f"Tool {tool.name} input schema allows additional properties"
            )

    def test_register_duplicate_raises(self):
        registry = MCPToolRegistry()
        tool = registry.get("search_knowledge")
        assert tool is not None
        with pytest.raises(ValueError):
            registry.register(tool)

    def test_timeout_and_retry_values(self):
        registry = MCPToolRegistry()
        tool = registry.get("search_knowledge")
        assert tool is not None
        assert tool.timeout_seconds > 0
        assert tool.max_retries >= 0
        assert tool.max_output_size > 0

    def test_email_draft_is_state_changing(self):
        registry = MCPToolRegistry()
        tool = registry.get("generate_email_draft")
        assert tool is not None
        assert tool.permission == ToolPermission.STATE_CHANGING

    def test_search_knowledge_is_read_only(self):
        registry = MCPToolRegistry()
        tool = registry.get("search_knowledge")
        assert tool is not None
        assert tool.permission == ToolPermission.READ_ONLY

    def test_analyze_job_description_requires_both_inputs(self):
        registry = MCPToolRegistry()
        tool = registry.get("analyze_job_description")
        assert tool is not None
        required = tool.input_schema.get("required", [])
        assert "resume_text" in required
        assert "job_description" in required
