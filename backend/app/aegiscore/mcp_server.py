"""AEGISCORE_PHASE2_MCP_SERVER

MCP Server — standalone subprocess exposing 7 approved tools via stdio transport.

The server:
- Runs as a standalone subprocess managed by the MCP client
- Communicates exclusively via stdin/stdout (MCP protocol on stdout, diagnostics on stderr)
- Registers only the 7 approved tools from the fixed allowlist
- Routes all tool calls through the execution engine with schema validation,
  permission checks, timeouts, retries, output limits, and audit logging
- Never exposes internal storage paths or sensitive document content

Uses MCP 2.x low-level server API with on_list_tools and on_call_tool handlers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.lowlevel.server import ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from aegiscore.mcp_audit_logger import get_audit_logger
from aegiscore.mcp_execution_engine import ExecutionResult, get_execution_engine
from aegiscore.mcp_permission_engine import PermissionEngine
from aegiscore.mcp_tool_registry import MCPToolRegistry


logger = logging.getLogger("aegiscore.mcp.server")

# MCP server name and version
SERVER_NAME = "aegiscore-mcp"
SERVER_VERSION = "1.0.0"

# Module-level singleton
_server: "MCPServer" | None = None


class MCPServer:
    """MCP server exposing approved tools via stdio."""

    def __init__(self) -> None:
        self.registry = MCPToolRegistry()
        self.permission_engine = PermissionEngine(self.registry)
        self.execution_engine = get_execution_engine(self.registry)
        self.audit_logger = get_audit_logger()
        self._executors: dict[str, Any] = {}
        self._executor_lock = asyncio.Lock()

        # Create the MCP 2.x server with on_list_tools and on_call_tool handlers
        self.server = Server(
            SERVER_NAME,
            version=SERVER_VERSION,
            on_list_tools=self._handle_list_tools,
            on_call_tool=self._handle_call_tool,
        )

    async def _handle_list_tools(
        self,
        context: ServerRequestContext,
        params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        """Handle tools/list request — return all approved tools."""
        tools = []
        for tool_def in self.registry.list_tools():
            tools.append(
                Tool(
                    name=tool_def.name,
                    description=tool_def.description,
                    inputSchema=tool_def.input_schema,
                )
            )
        return ListToolsResult(tools=tools)

    async def _handle_call_tool(
        self,
        context: ServerRequestContext,
        params: CallToolRequestParams,
    ) -> Any:
        """Handle tools/call request — execute a tool through the full pipeline."""
        import json

        name = params.name
        arguments = params.arguments or {}

        # 1. Permission check
        decision, reason = self.permission_engine.evaluate(name, arguments)
        if decision == "denied":
            logger.warning("Tool call denied: %s — %s", name, reason)
            return self._error_response(reason, "denied")
        if decision == "requires_confirmation":
            logger.warning("Tool call requires confirmation: %s — %s", name, reason)
            return self._error_response(reason, "requires_confirmation")
        if decision == "confirmation_insufficient":
            logger.warning("Tool call confirmation insufficient: %s — %s", name, reason)
            return self._error_response(reason, "confirmation_insufficient")

        # 2. Get or create executor for this tool
        executor = await self._get_executor(name)

        # 3. Execute through execution engine
        result: ExecutionResult = await self.execution_engine.execute(
            tool_name=name,
            arguments=arguments,
            executor=executor,
        )

        # 4. Format response
        if result.success:
            response = {
                "success": True,
                "data": result.data,
                "duration_seconds": result.duration_seconds,
                "attempts": result.attempts,
                "output_size": result.output_size,
            }
        else:
            response = {
                "success": False,
                "error": result.error,
                "duration_seconds": result.duration_seconds,
                "attempts": result.attempts,
            }

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(response, separators=(",", ":")))]
        )

    def _error_response(self, message: str, decision: str) -> CallToolResult:
        """Return an error response as CallToolResult."""
        import json

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({
                "success": False,
                "error": message,
                "permission_decision": decision,
            }))]
        )

    async def _get_executor(self, tool_name: str) -> Any:
        """Get or create the executor callable for a tool."""
        async with self._executor_lock:
            if tool_name in self._executors:
                return self._executors[tool_name]

            executor = self._build_executor(tool_name)
            self._executors[tool_name] = executor
            return executor

    def _build_executor(self, tool_name: str) -> Any:
        """Build an executor callable for the given tool.

        Each executor maps to the corresponding V1 business logic function.
        No business logic is duplicated here.
        """
        from aegiscore.document_service import get_resume_attachment, list_documents
        from aegiscore.extraction_storage import get_extraction
        from aegiscore.chunk_storage import get_document_chunks
        from aegiscore.vector_storage import get_document_embeddings, search_similar_chunks
        from aegiscore.job_email import generate_job_email
        from aegiscore.job_analysis import analyze_resume
        from aegiscore.sparse_search import (
            hybrid_search,
            search_sparse_chunks,
        )
        from aegiscore.embedding_service import embed_chunks
        from aegiscore.ollama_embedding import OllamaEmbeddingEncoder

        OLLAMA_MODEL = "nomic-embed-text:latest"
        _encoder = OllamaEmbeddingEncoder()

        if tool_name == "search_knowledge":
            async def executor(args: dict[str, Any]) -> dict[str, Any]:
                query = args.get("query", "")
                top_k = args.get("top_k", 5)
                mode = args.get("mode", "hybrid")
                min_similarity = args.get("min_similarity", 0.45)

                if mode == "sparse":
                    results = search_sparse_chunks(query, top_k=top_k)
                elif mode == "hybrid":
                    query_result = embed_chunks(
                        [{"text": query}],
                        encoder=_encoder,
                        model_name=OLLAMA_MODEL,
                    )
                    dense_results = search_similar_chunks(
                        query_result[0]["embedding"],
                        top_k=top_k,
                        model_name=OLLAMA_MODEL,
                    )
                    for item in dense_results:
                        item["retrieval_strategy"] = "dense"
                    sparse_results = search_sparse_chunks(query, top_k=top_k)
                    for item in sparse_results:
                        item["retrieval_strategy"] = "sparse"
                    results = hybrid_search(query, dense_results, sparse_results, top_k=top_k)
                else:  # dense
                    query_result = embed_chunks(
                        [{"text": query}],
                        encoder=_encoder,
                        model_name=OLLAMA_MODEL,
                    )
                    results = search_similar_chunks(
                        query_result[0]["embedding"],
                        top_k=top_k,
                        model_name=OLLAMA_MODEL,
                    )
                    for item in results:
                        item["retrieval_strategy"] = "dense"

                qualified = [
                    item
                    for item in results
                    if isinstance(item, dict)
                    and isinstance(item.get("text"), str)
                    and item["text"].strip()
                    and float(item.get("similarity", 0.0)) >= min_similarity
                ][:top_k]

                sources = []
                for index, item in enumerate(qualified, start=1):
                    sources.append({
                        "source_id": f"S{index}",
                        "filename": str(item.get("filename", "unknown")),
                        "page_number": item.get("page_number"),
                        "text": str(item.get("text", ""))[:3000],
                        "similarity": float(item.get("similarity", 0.0)),
                    })

                return {
                    "query": query,
                    "mode": mode,
                    "result_count": len(sources),
                    "results": sources,
                }
            return executor

        if tool_name == "get_document_status":
            async def executor(args: dict[str, Any]) -> dict[str, Any]:
                document_id = args.get("document_id", "")

                docs = list_documents()
                doc = None
                for d in docs:
                    if d.get("document_id") == document_id:
                        doc = d
                        break
                if doc is None:
                    return {"success": False, "error": "Document not found."}

                extraction = get_extraction(document_id)
                chunks = get_document_chunks(document_id)
                embeddings = get_document_embeddings(document_id)

                return {
                    "document_id": doc["document_id"],
                    "filename": doc["filename"],
                    "extension": doc.get("extension", ""),
                    "status": extraction.get("status", "not_extracted") if extraction else "not_extracted",
                    "page_count": len(extraction.get("pages", [])) if extraction else 0,
                    "chunk_count": len(chunks) if chunks else 0,
                    "embedding_count": len(embeddings) if embeddings else 0,
                }
            return executor

        if tool_name == "list_documents":
            async def executor(args: dict[str, Any]) -> dict[str, Any]:
                docs = list_documents()
                return {"documents": docs}
            return executor

        if tool_name == "analyze_resume":
            async def executor(args: dict[str, Any]) -> dict[str, Any]:
                resume_text = args.get("resume_text", "")
                job_description = args.get("job_description", "")
                result = analyze_resume(resume_text, job_description)
                return result
            return executor

        if tool_name == "analyze_job_description":
            async def executor(args: dict[str, Any]) -> dict[str, Any]:
                # No separate V1 function exists — wrapper around analyze_resume
                resume_text = args.get("resume_text", "")
                job_description = args.get("job_description", "")
                result = analyze_resume(resume_text, job_description)
                return result
            return executor

        if tool_name == "generate_email_draft":
            async def executor(args: dict[str, Any]) -> dict[str, Any]:
                candidate_name = args.get("candidate_name", "")
                recipient_email = args.get("recipient_email", "")
                job_title = args.get("job_title", "")
                company_name = args.get("company_name", "")
                resume_summary = args.get("resume_summary", "")
                resume_document_id = args.get("resume_document_id", "")
                confirm = args.get("confirm", False)

                if not confirm:
                    return {"success": False, "error": "Explicit confirmation required."}

                # Verify resume attachment (SHA-256)
                try:
                    metadata, _storage_path = get_resume_attachment(resume_document_id)
                except Exception as exc:
                    return {"success": False, "error": f"Resume attachment verification failed: {exc}"}

                draft = generate_job_email(
                    candidate_name=candidate_name,
                    recipient_email=recipient_email,
                    job_title=job_title,
                    company_name=company_name,
                    resume_summary=resume_summary,
                )

                return {
                    "draft": draft,
                    "attachment_document_id": metadata["document_id"],
                    "attachment_filename": metadata["filename"],
                    "attachment_sha256": metadata["sha256"],
                    "requires_user_approval": True,
                    "sent": False,
                }
            return executor

        if tool_name == "get_resume_attachment":
            async def executor(args: dict[str, Any]) -> dict[str, Any]:
                document_id = args.get("document_id", "")

                metadata, _storage_path = get_resume_attachment(document_id)

                return {
                    "document_id": metadata["document_id"],
                    "filename": metadata["filename"],
                    "extension": metadata["extension"],
                    "content_type": metadata.get("content_type", ""),
                    "size_bytes": metadata["size_bytes"],
                    "sha256": metadata["sha256"],
                    "uploaded_at": metadata["uploaded_at"],
                }
            return executor

        raise ValueError(f"No executor for tool '{tool_name}'")

    async def run(self) -> None:
        """Run the MCP server over stdio."""
        logger.info("MCP server starting: %s v%s", SERVER_NAME, SERVER_VERSION)
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def main() -> None:
    """Entry point for the MCP server subprocess."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    server = MCPServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("MCP server shutting down.")
    except Exception as exc:  # noqa: BLE001 — server boundary
        logger.error("MCP server fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()


def get_server() -> MCPServer:
    """Return the singleton MCP server instance."""
    global _server
    if _server is None:
        _server = MCPServer()
    return _server
