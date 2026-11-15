"""AEGISCORE_PHASE2_E2E_VERIFICATION

Real MCP client-server stdio end-to-end verification.
Tests actual MCP protocol communication between client and server subprocesses.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend/app to path for imports
BACKEND_APP_DIR = Path(__file__).resolve().parents[1] / "backend" / "app"
sys.path.insert(0, str(BACKEND_APP_DIR))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_SCRIPT = str(BACKEND_APP_DIR / "aegiscore" / "mcp_server.py")

# Set PYTHONPATH for the MCP server subprocess
_MCP_ENV = os.environ.copy()
_MCP_ENV["PYTHONPATH"] = str(BACKEND_APP_DIR) + os.pathsep + _MCP_ENV.get("PYTHONPATH", "")


def _make_params():
    return StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT], env=_MCP_ENV)


async def test_mcp_server_starts_and_lists_tools():
    """Test that the MCP server starts and lists all 7 approved tools via stdio."""
    params = _make_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            expected = {
                "search_knowledge",
                "get_document_status",
                "list_documents",
                "analyze_resume",
                "analyze_job_description",
                "generate_email_draft",
                "get_resume_attachment",
            }
            assert tool_names == expected, f"Expected {expected}, got {tool_names}"
            print(f"PASS: MCP server lists {len(tools.tools)} tools: {sorted(tool_names)}")


async def test_mcp_get_document_status():
    """Test get_document_status tool via real MCP stdio call."""
    params = _make_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_document_status", {
                "document_id": "nonexistent-id",
            })
            response_text = None
            for content in result.content:
                if hasattr(content, "text"):
                    response_text = content.text
                    break
            assert response_text is not None
            data = json.loads(response_text)
            # Unknown document should fail gracefully
            assert data["success"] is False
            print("PASS: get_document_status correctly rejects unknown document")


async def test_mcp_generate_email_draft_without_confirm():
    """Test that generate_email_draft without confirm: true is rejected."""
    params = _make_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("generate_email_draft", {
                "candidate_name": "John",
                "recipient_email": "hr@example.com",
                "job_title": "Developer",
                "company_name": "Acme",
                "resume_summary": "Python developer",
                "resume_document_id": "doc-123",
                # No confirm field
            })
            response_text = None
            for content in result.content:
                if hasattr(content, "text"):
                    response_text = content.text
                    break
            assert response_text is not None
            data = json.loads(response_text)
            assert data["success"] is False
            assert "confirmation" in data.get("error", "").lower()
            print("PASS: generate_email_draft without confirm is rejected")


async def test_mcp_generate_email_draft_confirm_alone_insufficient():
    """Test that confirm: true alone is NOT sufficient for email draft."""
    params = _make_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("generate_email_draft", {
                "candidate_name": "John",
                "recipient_email": "hr@example.com",
                "job_title": "Developer",
                "company_name": "Acme",
                "resume_summary": "Python developer",
                "resume_document_id": "doc-123",
                "confirm": True,
                # No attachment_sha256 or attachment_document_id match
            })
            response_text = None
            for content in result.content:
                if hasattr(content, "text"):
                    response_text = content.text
                    break
            assert response_text is not None
            data = json.loads(response_text)
            assert data["success"] is False
            assert "sufficient" in data.get("error", "").lower()
            print("PASS: confirm: true alone is NOT sufficient for email draft")


async def test_mcp_get_resume_attachment_unknown():
    """Test get_resume_attachment with unknown document ID."""
    params = _make_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_resume_attachment", {
                "document_id": "nonexistent-id",
            })
            response_text = None
            for content in result.content:
                if hasattr(content, "text"):
                    response_text = content.text
                    break
            assert response_text is not None
            data = json.loads(response_text)
            assert data["success"] is False
            print("PASS: get_resume_attachment correctly rejects unknown document")


async def test_mcp_tool_output_no_internal_paths():
    """Test that tool outputs don't expose internal storage paths."""
    params = _make_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_documents", {})
            response_text = None
            for content in result.content:
                if hasattr(content, "text"):
                    response_text = content.text
                    break
            assert response_text is not None
            data = json.loads(response_text)
            assert data["success"] is True
            response_str = json.dumps(data)
            # Should not expose internal paths
            assert "/uploads/" not in response_str
            assert "/data/" not in response_str
            assert "storage_key" not in response_str
            assert "aegiscore.db" not in response_str
            print("PASS: Tool outputs don't expose internal storage paths")


async def main():
    print("=" * 60)
    print("AegisCore AI Phase 2 - MCP E2E Verification")
    print("=" * 60)

    await test_mcp_server_starts_and_lists_tools()
    await test_mcp_get_document_status()
    await test_mcp_generate_email_draft_without_confirm()
    await test_mcp_generate_email_draft_confirm_alone_insufficient()
    await test_mcp_get_resume_attachment_unknown()
    await test_mcp_tool_output_no_internal_paths()

    print("=" * 60)
    print("ALL MCP E2E TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
