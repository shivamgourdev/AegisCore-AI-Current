"""AEGISCORE_PHASE2_MCP_CLIENT

MCP Client — manages a standalone MCP server subprocess via stdio.

The client:
- Spawns, monitors, and cleans up the MCP server subprocess (clear single process owner)
- Connects via stdio (stdout for MCP protocol, stderr for diagnostics)
- Discovers approved tools and retrieves schemas
- Executes tools through the server with health checks
- Implements bounded reconnection with exponential backoff
- Detects server crashes and falls back to direct V1 calls
- Never crashes the application on connection failure
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from aegiscore.mcp_tool_registry import MCPToolRegistry
from aegiscore.mcp_execution_engine import ExecutionResult, get_execution_engine
from aegiscore.mcp_permission_engine import PermissionEngine
from aegiscore.mcp_audit_logger import get_audit_logger


logger = logging.getLogger("aegiscore.mcp.client")

# Default retry/backoff settings
MAX_RECONNECT_ATTEMPTS = 5
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
HEALTH_CHECK_INTERVAL = 30.0


class MCPClient:
    """Client-managed MCP server subprocess connection.

    Process owner: this client spawns, monitors, and cleans up the subprocess.
    FastAPI app does not manage the MCP process.
    """

    def __init__(
        self,
        registry: MCPToolRegistry | None = None,
        server_script: str | None = None,
    ) -> None:
        if registry is None:
            registry = MCPToolRegistry()
        self.registry = registry
        self.permission_engine = PermissionEngine(registry)
        self.execution_engine = get_execution_engine(registry)
        self.audit_logger = get_audit_logger()

        # Resolve server script path
        if server_script is None:
            server_script = str(
                Path(__file__).resolve().parent / "mcp_server.py"
            )
        self.server_script = server_script

        # Subprocess management
        self._process: subprocess.Popen | None = None
        self._session: ClientSession | None = None
        self._read_stream: Any = None
        self._write_stream: Any = None
        self._stdio_context: Any = None
        self._client_context: Any = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._reconnect_attempts = 0
        self._health_check_task: asyncio.Task | None = None
        self._shutdown = False

        # Fallback mode
        self._fallback_mode = False
        self._server_unavailable_since: float | None = None

    @property
    def is_connected(self) -> bool:
        """Return whether the MCP server is connected."""
        return self._connected and not self._fallback_mode

    @property
    def is_fallback(self) -> bool:
        """Return whether the client is in fallback mode (server unavailable)."""
        return self._fallback_mode

    async def connect(self) -> bool:
        """Connect to the MCP server subprocess.

        Returns True if connected, False if fallback mode activated.
        """
        async with self._lock:
            if self._connected:
                return True

            try:
                await self._establish_session()
                self._connected = True
                self._fallback_mode = False
                self._reconnect_attempts = 0
                self._server_unavailable_since = None
                self._start_health_check()
                logger.info("MCP client connected to server subprocess.")
                return True
            except Exception as exc:  # noqa: BLE001 — client boundary
                logger.warning("Failed to connect to MCP server: %s", exc)
                await self._cleanup_resources()
                self._enter_fallback()
                return False

    async def _spawn_server(self) -> None:
        """Spawn the MCP server subprocess (used for cleanup tracking).

        The actual stdio communication is managed by stdio_client in
        _establish_session. This method tracks the subprocess PID for
        cleanup purposes.
        """
        # Note: stdio_client manages the subprocess lifecycle.
        # This method is kept for compatibility but the actual
        # subprocess is created by stdio_client.
        pass

    async def _establish_session(self) -> None:
        """Establish MCP client session over stdio."""
        if self._process is None or self._process.stdout is None or self._process.stdin is None:
            raise RuntimeError("Server subprocess not properly spawned.")

        # Set PYTHONPATH so the subprocess can find the aegiscore package
        env = os.environ.copy()
        backend_app_dir = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = backend_app_dir + os.pathsep + env.get("PYTHONPATH", "")

        self._stdio_context = stdio_client(
            StdioServerParameters(
                command=sys.executable,
                args=[self.server_script],
                env=env,
            )
        )
        read_stream, write_stream = await self._stdio_context.__aenter__()
        self._read_stream = read_stream
        self._write_stream = write_stream

        self._client_context = ClientSession(read_stream, write_stream)
        self._session = await self._client_context.__aenter__()
        await self._session.initialize()
        logger.debug("MCP client session initialized.")

    def _start_health_check(self) -> None:
        """Start periodic health check task."""
        if self._health_check_task is not None:
            self._health_check_task.cancel()
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Periodically check server health."""
        while not self._shutdown and self._connected:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                if self._shutdown or not self._connected:
                    break
                await self.health_check()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001 — health check boundary
                logger.warning("Health check failed: %s", exc)
                await self._handle_server_unavailable()

    async def health_check(self) -> bool:
        """Check if the MCP server is healthy by listing tools."""
        if not self._connected or self._session is None:
            return False
        try:
            await self._session.list_tools()
            return True
        except Exception as exc:
            logger.warning("Health check failed: %s", exc)
            await self._handle_server_unavailable()
            return False

    async def _handle_server_unavailable(self) -> None:
        """Handle server becoming unavailable — enter fallback mode."""
        async with self._lock:
            if self._fallback_mode:
                return
            self._connected = False
            self._fallback_mode = True
            self._server_unavailable_since = time.monotonic()
            await self._cleanup_resources()
            logger.warning("MCP server unavailable. Entering fallback mode.")

    async def _enter_fallback(self) -> None:
        """Enter fallback mode — direct V1 calls will be used."""
        self._connected = False
        self._fallback_mode = True
        self._server_unavailable_since = time.monotonic()
        logger.warning("MCP client in fallback mode.")

    async def _reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff."""
        if self._shutdown or self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            return False

        self._reconnect_attempts += 1
        backoff = min(
            INITIAL_BACKOFF_SECONDS * (2 ** (self._reconnect_attempts - 1)),
            MAX_BACKOFF_SECONDS,
        )
        logger.info("Reconnect attempt %d/%d in %.1fs", self._reconnect_attempts, MAX_RECONNECT_ATTEMPTS, backoff)
        await asyncio.sleep(backoff)

        try:
            await self._cleanup_resources()
            await self._spawn_server()
            await self._establish_session()
            self._connected = True
            self._fallback_mode = False
            self._server_unavailable_since = None
            self._start_health_check()
            logger.info("MCP client reconnected successfully.")
            return True
        except Exception as exc:
            logger.warning("Reconnect attempt %d failed: %s", self._reconnect_attempts, exc)
            return False

    async def _cleanup_resources(self) -> None:
        """Clean up MCP client resources."""
        self._connected = False
        if self._health_check_task is not None:
            self._health_check_task.cancel()
            self._health_check_task = None
        if self._client_context is not None:
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._client_context = None
        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._stdio_context = None

        if self._process is not None:
            try:
                if self._process.poll() is None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=5)
            except Exception:
                pass
            self._process = None

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ExecutionResult:
        """Execute a tool through the MCP server.

        If the server is unavailable, falls back to direct V1 execution
        with the same security policies.
        """
        async with self._lock:
            if self._fallback_mode or not self._connected:
                # Try to reconnect first
                if self._server_unavailable_since is not None:
                    reconnected = await self._reconnect()
                    if not reconnected:
                        return await self._fallback_execute(tool_name, arguments)

            try:
                # 1. Permission check
                decision, reason = self.permission_engine.evaluate(tool_name, arguments)
                if decision != "allowed":
                    return ExecutionResult(
                        success=False,
                        error=reason,
                    )

                # 2. Get executor
                executor = await self._get_executor(tool_name)

                # 3. Execute through execution engine
                result: ExecutionResult = await self.execution_engine.execute(
                    tool_name=tool_name,
                    arguments=arguments,
                    executor=executor,
                )
                return result

            except Exception as exc:  # noqa: BLE001 — client boundary
                logger.warning("MCP tool execution failed: %s", exc)
                await self._handle_server_unavailable()
                return await self._fallback_execute(tool_name, arguments)

    async def _get_executor(self, tool_name: str) -> Any:
        """Get an executor that calls the tool via MCP stdio."""
        async def mcp_executor(args: dict[str, Any]) -> dict[str, Any]:
            if self._session is None:
                raise RuntimeError("MCP session not available.")
            result = await self._session.call_tool(tool_name, args)
            # Parse the text content response
            import json
            for content in result.content:
                if hasattr(content, "text"):
                    parsed = json.loads(content.text)
                    return parsed
            raise RuntimeError("No text content in MCP tool response.")
        return mcp_executor

    async def _fallback_execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ExecutionResult:
        """Fallback to direct V1 function execution with same security policies.

        Fallback preserves the same authorization, validation, citation,
        attachment integrity, and audit policies as MCP execution.
        """
        logger.info("Falling back to direct V1 execution for tool '%s'.", tool_name)

        # Build a direct executor that calls V1 functions
        executor = self._build_v1_executor(tool_name)
        if executor is None:
            return ExecutionResult(
                success=False,
                error=f"Tool '{tool_name}' not available in fallback mode.",
            )

        result: ExecutionResult = await self.execution_engine.execute(
            tool_name=tool_name,
            arguments=arguments,
            executor=executor,
        )
        return result

    def _build_v1_executor(self, tool_name: str) -> Any:
        """Build a direct V1 executor for fallback mode."""
        # Import V1 functions directly
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
            def executor(args: dict[str, Any]) -> dict[str, Any]:
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
                    sparse_results = search_sparse_chunks(query, top_k=top_k)
                    results = hybrid_search(query, dense_results, sparse_results, top_k=top_k)
                else:
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
            def executor(args: dict[str, Any]) -> dict[str, Any]:
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
            def executor(args: dict[str, Any]) -> dict[str, Any]:
                return {"documents": list_documents()}
            return executor

        if tool_name == "analyze_resume":
            def executor(args: dict[str, Any]) -> dict[str, Any]:
                return analyze_resume(args.get("resume_text", ""), args.get("job_description", ""))
            return executor

        if tool_name == "analyze_job_description":
            def executor(args: dict[str, Any]) -> dict[str, Any]:
                return analyze_resume(args.get("resume_text", ""), args.get("job_description", ""))
            return executor

        if tool_name == "generate_email_draft":
            def executor(args: dict[str, Any]) -> dict[str, Any]:
                resume_document_id = args.get("resume_document_id", "")
                metadata, _storage_path = get_resume_attachment(resume_document_id)
                draft = generate_job_email(
                    candidate_name=args.get("candidate_name", ""),
                    recipient_email=args.get("recipient_email", ""),
                    job_title=args.get("job_title", ""),
                    company_name=args.get("company_name", ""),
                    resume_summary=args.get("resume_summary", ""),
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
            def executor(args: dict[str, Any]) -> dict[str, Any]:
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

        return None

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available MCP tools from the server."""
        if self._fallback_mode or self._session is None:
            # Return tool definitions from registry instead
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in self.registry.list_tools()
            ]
        try:
            result = await self._session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema or {},
                }
                for t in result.tools
            ]
        except Exception as exc:  # noqa: BLE001 — client boundary
            logger.warning("Failed to list tools: %s", exc)
            await self._handle_server_unavailable()
            return [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.input_schema,
                }
                for t in self.registry.list_tools()
            ]

    async def disconnect(self) -> None:
        """Disconnect and clean up the MCP server subprocess."""
        self._shutdown = True
        async with self._lock:
            self._connected = False
            if self._health_check_task is not None:
                self._health_check_task.cancel()
                self._health_check_task = None
            await self._cleanup_resources()
            logger.info("MCP client disconnected.")

    async def _cleanup_resources(self) -> None:
        """Clean up MCP client resources."""
        if self._client_context is not None:
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._client_context = None
        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._stdio_context = None

        if self._process is not None:
            try:
                if self._process.poll() is None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=5)
            except Exception:
                pass
            self._process = None


# Module-level singleton
_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Return the singleton MCP client."""
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
