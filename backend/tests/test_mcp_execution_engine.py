"""AEGISCORE_PHASE2_TESTS_EXECUTION_ENGINE

Unit tests for the MCP execution engine — schema validation, timeouts,
retries, output limits, concurrency limits, and shared retry budget.
"""

import asyncio

import pytest

from aegiscore.mcp_execution_engine import ExecutionEngine, ExecutionResult
from aegiscore.mcp_tool_registry import MCPToolRegistry, ToolPermission


class TestExecutionEngine:
    def setup_method(self):
        self.registry = MCPToolRegistry()
        self.engine = ExecutionEngine(
            registry=self.registry,
            max_concurrent=5,
            max_output_size=1024,
            global_retry_budget=5,
            global_timeout_seconds=30.0,
        )

    def test_successful_execution(self):
        async def executor(args):
            return {"result": "success", "query": args.get("query")}

        result = asyncio.run(
            self.engine.execute("search_knowledge", {"query": "test"}, executor)
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["query"] == "test"

    def test_invalid_input_rejected(self):
        async def executor(args):
            return {"result": "success"}

        # Missing required field 'query'
        result = asyncio.run(
            self.engine.execute("search_knowledge", {}, executor)
        )
        assert result.success is False
        assert result.error is not None

    def test_additional_property_rejected(self):
        async def executor(args):
            return {"result": "success"}

        result = asyncio.run(
            self.engine.execute(
                "search_knowledge",
                {"query": "test", "unexpected_field": "value"},
                executor,
            )
        )
        assert result.success is False

    def test_tool_not_in_registry(self):
        async def executor(args):
            return {"result": "success"}

        result = asyncio.run(
            self.engine.execute("nonexistent_tool", {}, executor)
        )
        assert result.success is False
        assert "not in the approved allowlist" in result.error

    def test_executor_raises_exception(self):
        async def executor(args):
            raise ValueError("Something went wrong")

        result = asyncio.run(
            self.engine.execute("search_knowledge", {"query": "test"}, executor)
        )
        assert result.success is False
        assert result.error is not None
        assert result.attempts >= 1

    def test_output_size_limit(self):
        async def executor(args):
            return {"result": "x" * 2000}  # Exceeds 1024 byte limit

        result = asyncio.run(
            self.engine.execute("search_knowledge", {"query": "test"}, executor)
        )
        assert result.success is False
        assert "exceeds maximum size" in result.error

    def test_output_size_under_limit(self):
        async def executor(args):
            return {"result": "small"}

        result = asyncio.run(
            self.engine.execute("search_knowledge", {"query": "test"}, executor)
        )
        assert result.success is True

    def test_retry_on_failure(self):
        attempts = {"count": 0}

        async def executor(args):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ValueError("Transient failure")
            return {"result": "success"}

        result = asyncio.run(
            self.engine.execute(
                "search_knowledge",
                {"query": "test"},
                executor,
            )
        )
        assert result.success is True
        assert attempts["count"] == 3

    def test_retry_exhausted(self):
        async def executor(args):
            raise ValueError("Always fails")

        result = asyncio.run(
            self.engine.execute(
                "search_knowledge",
                {"query": "test"},
                executor,
            )
        )
        assert result.success is False
        assert result.attempts >= 1

    def test_global_retry_budget(self):
        # Create engine with small budget
        engine = ExecutionEngine(
            registry=self.registry,
            max_concurrent=5,
            max_output_size=1024,
            global_retry_budget=1,
            global_timeout_seconds=30.0,
        )

        async def failing_executor(args):
            raise ValueError("Always fails")

        # First execution should consume budget and fail
        result1 = asyncio.run(
            engine.execute(
                "search_knowledge",
                {"query": "test1"},
                failing_executor,
            )
        )
        assert result1.success is False

        # Second execution should fail immediately due to budget exhausted
        result2 = asyncio.run(
            engine.execute(
                "search_knowledge",
                {"query": "test2"},
                failing_executor,
            )
        )
        assert result2.success is False
        assert "budget" in result2.error.lower()

    def test_retry_budget_remaining(self):
        remaining = self.engine.get_retry_budget_remaining()
        assert remaining == 5

    def test_execution_count(self):
        count_before = self.engine.get_execution_count()

        async def executor(args):
            return {"result": "ok"}

        asyncio.run(
            self.engine.execute("list_documents", {}, executor)
        )
        count_after = self.engine.get_execution_count()
        assert count_after == count_before + 1

    def test_timeout(self):
        async def slow_executor(args):
            await asyncio.sleep(10)  # Exceeds 30s... actually let's use a shorter timeout
            return {"result": "slow"}

        engine = ExecutionEngine(
            registry=self.registry,
            max_concurrent=5,
            max_output_size=1024,
            global_retry_budget=5,
            global_timeout_seconds=30.0,
        )
        # Use a tool with short timeout
        from aegiscore.mcp_tool_registry import ToolDefinition

        short_tool = ToolDefinition(
            name="short_timeout_tool",
            description="Short timeout",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {}, "additionalProperties": False},
            permission=ToolPermission.READ_ONLY,
            v1_function="test.short_timeout",
            timeout_seconds=1,
            max_retries=0,
            max_output_size=1024,
        )
        # Temporarily register
        self.registry.register(short_tool)

        async def executor(args):
            await asyncio.sleep(10)
            return {"result": "slow"}

        result = asyncio.run(
            engine.execute("short_timeout_tool", {}, executor)
        )
        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_concurrent_execution(self):
        async def executor(args):
            await asyncio.sleep(0.1)
            return {"result": args.get("query")}

        async def run_concurrent():
            tasks = [
                self.engine.execute("search_knowledge", {"query": f"q{i}"}, executor)
                for i in range(10)
            ]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_concurrent())
        assert len(results) == 10
        assert all(r.success for r in results)

    def test_execution_result_attributes(self):
        async def executor(args):
            return {"result": "ok"}

        result = asyncio.run(
            self.engine.execute("search_knowledge", {"query": "test"}, executor)
        )
        assert hasattr(result, "success")
        assert hasattr(result, "data")
        assert hasattr(result, "error")
        assert hasattr(result, "duration_seconds")
        assert hasattr(result, "attempts")
        assert hasattr(result, "output_size")
