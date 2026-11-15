"""AEGISCORE_PHASE2_MCP_EXECUTION_ENGINE

MCP Tool Execution Engine — schema validation, timeouts, retries,
output limits, concurrency limits, and shared retry budget.

All tool execution routes through this engine. No tool bypasses it.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any, Callable

from aegiscore.mcp_tool_registry import MCPToolRegistry, ToolDefinition
from aegiscore.mcp_audit_logger import get_audit_logger


logger = logging.getLogger("aegiscore.mcp.execution")


class ExecutionResult:
    """Result of a tool execution."""

    def __init__(
        self,
        success: bool,
        data: dict[str, Any] | None = None,
        error: str | None = None,
        duration_seconds: float = 0.0,
        attempts: int = 1,
        output_size: int = 0,
    ) -> None:
        self.success = success
        self.data = data
        self.error = error
        self.duration_seconds = duration_seconds
        self.attempts = attempts
        self.output_size = output_size


class ExecutionEngine:
    """Executes MCP tools with schema validation, timeouts, retries,
    output limits, concurrency limits, and shared retry budget."""

    def __init__(
        self,
        registry: MCPToolRegistry,
        max_concurrent: int = 5,
        max_output_size: int = 1_048_576,
        global_retry_budget: int = 10,
        global_timeout_seconds: float = 120.0,
    ) -> None:
        self.registry = registry
        self.max_concurrent = max_concurrent
        self.max_output_size = max_output_size
        self.global_retry_budget = global_retry_budget
        self.global_timeout_seconds = global_timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._retry_budget_remaining = global_retry_budget
        self._budget_lock = asyncio.Lock()
        self._audit_logger = get_audit_logger()
        self._execution_count = 0
        self._lock = asyncio.Lock()

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        executor: Callable[[dict[str, Any]], Any],
    ) -> ExecutionResult:
        """Execute a tool through the full pipeline:
        schema validation → permission → execution → output limits → audit.

        The executor is a callable that takes validated arguments and
        returns the raw V1 function result.
        """
        start_time = time.monotonic()
        tool = self.registry.get(tool_name)
        if tool is None:
            return ExecutionResult(
                success=False,
                error=f"Tool '{tool_name}' is not in the approved allowlist.",
            )

        # 1. Schema validation (input)
        validated_args = self._validate_input(tool, arguments)
        if validated_args is None:
            return ExecutionResult(
                success=False,
                error=f"Invalid input for tool '{tool_name}'.",
            )

        # 2. Acquire concurrency slot
        async with self._semaphore:
            # 3. Execute with retries within shared budget
            result = await self._execute_with_retries(tool, validated_args, executor)

        # 4. Output size enforcement
        if result.success and result.data is not None:
            output_json = __import__("json").dumps(result.data, separators=(",", ":"))
            output_size = len(output_json.encode("utf-8"))
            result.output_size = output_size
            effective_limit = min(self.max_output_size, tool.max_output_size)
            if output_size > effective_limit:
                result.success = False
                result.error = (
                    f"Tool output exceeds maximum size of {effective_limit} bytes "
                    f"({output_size} bytes)."
                )
                result.data = None

        result.duration_seconds = time.monotonic() - start_time

        # 5. Audit log
        self._audit_logger.log(
            execution_id=self._next_execution_id(),
            tool_name=tool_name,
            input_data=validated_args,
            output_status="success" if result.success else "failure",
            duration_seconds=result.duration_seconds,
            error=result.error,
        )

        return result

    def _next_execution_id(self) -> str:
        self._execution_count += 1
        return f"exec_{int(time.time() * 1000)}_{self._execution_count}"

    def _validate_input(self, tool: ToolDefinition, arguments: dict[str, Any]) -> dict[str, Any] | None:
        """Validate input against the tool's Pydantic-like JSON schema.

        Returns validated arguments or None if invalid.
        """
        schema = tool.input_schema
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required fields
        for field in required:
            if field not in arguments:
                logger.warning("Missing required field '%s' for tool '%s'", field, tool.name)
                return None

        # Check no additional properties
        if not schema.get("additionalProperties", True):
            for key in arguments:
                if key not in properties:
                    logger.warning("Unexpected property '%s' for tool '%s'", key, tool.name)
                    return None

        # Validate types and constraints
        validated: dict[str, Any] = {}
        for key, value in arguments.items():
            if key not in properties:
                continue
            prop_schema = properties[key]
            expected_type = prop_schema.get("type")

            if expected_type == "string":
                if not isinstance(value, str):
                    logger.warning("Field '%s' must be a string for tool '%s'", key, tool.name)
                    return None
                min_len = prop_schema.get("minLength")
                if min_len is not None and len(value) < min_len:
                    return None
                max_len = prop_schema.get("maxLength")
                if max_len is not None and len(value) > max_len:
                    return None
                enum_vals = prop_schema.get("enum")
                if enum_vals is not None and value not in enum_vals:
                    return None
            elif expected_type == "integer":
                if not isinstance(value, int) or isinstance(value, bool):
                    logger.warning("Field '%s' must be an integer for tool '%s'", key, tool.name)
                    return None
                min_val = prop_schema.get("minimum")
                if min_val is not None and value < min_val:
                    return None
                max_val = prop_schema.get("maximum")
                if max_val is not None and value > max_val:
                    return None
            elif expected_type == "number":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    logger.warning("Field '%s' must be a number for tool '%s'", key, tool.name)
                    return None
                min_val = prop_schema.get("minimum")
                if min_val is not None and value < min_val:
                    return None
                max_val = prop_schema.get("maximum")
                if max_val is not None and value > max_val:
                    return None
            elif expected_type == "boolean":
                if not isinstance(value, bool):
                    logger.warning("Field '%s' must be a boolean for tool '%s'", key, tool.name)
                    return None
            elif expected_type == "array":
                if not isinstance(value, list):
                    logger.warning("Field '%s' must be an array for tool '%s'", key, tool.name)
                    return None
            elif expected_type == "object":
                if not isinstance(value, dict):
                    logger.warning("Field '%s' must be an object for tool '%s'", key, tool.name)
                    return None

            validated[key] = value

        # Apply defaults
        for key, prop_schema in properties.items():
            if key not in validated and "default" in prop_schema:
                validated[key] = prop_schema["default"]

        return validated

    async def _execute_with_retries(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
        executor: Callable[[dict[str, Any]], Any],
    ) -> ExecutionResult:
        """Execute with bounded retries within the shared global budget."""
        max_attempts = tool.max_retries + 1
        last_error: str | None = None

        for attempt in range(1, max_attempts + 1):
            # Check global retry budget
            async with self._budget_lock:
                if self._retry_budget_remaining <= 0 and attempt > 1:
                    return ExecutionResult(
                        success=False,
                        error="Global retry budget exhausted.",
                        attempts=attempt - 1,
                    )
                self._retry_budget_remaining -= 1

            try:
                # Run the executor with per-tool timeout
                result = await asyncio.wait_for(
                    self._run_executor(executor, arguments),
                    timeout=tool.timeout_seconds,
                )
                if isinstance(result, dict) and result.get("success") is False:
                    # Tool returned a structured failure
                    last_error = result.get("error", "Tool execution failed.")
                    if attempt < max_attempts:
                        continue
                    return ExecutionResult(
                        success=False,
                        error=last_error,
                        attempts=attempt,
                    )
                return ExecutionResult(
                    success=True,
                    data=result if isinstance(result, dict) else {"result": result},
                    attempts=attempt,
                )
            except asyncio.TimeoutError:
                last_error = f"Tool '{tool.name}' timed out after {tool.timeout_seconds}s."
                logger.warning("%s", last_error)
                if attempt >= max_attempts:
                    break
                continue
            except Exception as exc:  # noqa: BLE001 — engine boundary catches all
                last_error = str(exc)
                logger.exception("Tool '%s' attempt %d failed: %s", tool.name, attempt, exc)
                if attempt >= max_attempts:
                    break
                continue

        return ExecutionResult(
            success=False,
            error=last_error or f"Tool '{tool.name}' failed after {max_attempts} attempts.",
            attempts=max_attempts,
        )

    async def _run_executor(
        self,
        executor: Callable[[dict[str, Any]], Any],
        arguments: dict[str, Any],
    ) -> Any:
        """Run the executor, handling both sync and async callables."""
        if asyncio.iscoroutinefunction(executor):
            return await executor(arguments)
        # Run sync executor in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, executor, arguments)

    def get_retry_budget_remaining(self) -> int:
        """Return remaining global retry budget."""
        return self._retry_budget_remaining

    def get_execution_count(self) -> int:
        """Return total execution count."""
        return self._execution_count


# Module-level singleton
_execution_engine: ExecutionEngine | None = None


def get_execution_engine(
    registry: MCPToolRegistry | None = None,
) -> ExecutionEngine:
    """Return the singleton execution engine."""
    global _execution_engine
    if _execution_engine is None:
        if registry is None:
            from aegiscore.mcp_tool_registry import MCPToolRegistry as _Registry
            registry = _Registry()
        _execution_engine = ExecutionEngine(registry=registry)
    return _execution_engine
