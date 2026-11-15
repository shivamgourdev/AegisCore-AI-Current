"""AEGISCORE_PHASE1_TESTS
Multi-Agent Orchestration Engine — Phase 1 unit tests.

Covers:
1. Agent registration and lookup
2. Invalid agent input
3. Supervisor routing
4. Correct specialist selection
5. Agent execution success
6. Agent execution failure
7. Timeout and retry behavior
8. Invalid LLM responses
9. Infinite-loop prevention
10. Workflow state validation
11. FastAPI orchestration endpoints
12. Existing V1 functionality (regression)
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from aegiscore.agent_base import (
    AgentCapability,
    AgentConfig,
    AgentExecutionContext,
    AgentResult,
    AgentStatus,
    AgentRegistry,
    AgentOrchestrator,
    BaseAgent,
)
from aegiscore.agent_registry import get_registry, reset_registry
from aegiscore.rag_agent import RAGKnowledgeAgent
from aegiscore.resume_agent import ResumeAnalysisAgent
from aegiscore.job_analysis_agent import JobAnalysisAgent
from aegiscore.email_agent import JobApplicationEmailDraftAgent
from aegiscore.supervisor import SupervisorAgent
from aegiscore.workflow import OrchestrationWorkflow, MAX_WORKFLOW_STEPS
from aegiscore.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RecordingAgent(BaseAgent):
    """A test agent that records calls and can be configured to fail or timeout."""

    def __init__(self, name: str, should_fail: bool = False, should_timeout: bool = False):
        config = AgentConfig(
            name=name,
            capabilities=[AgentCapability.RAG_QUESTION_ANSWER],
            timeout_seconds=5,
            max_retries=2,
        )
        super().__init__(config)
        self.should_fail = should_fail
        self.should_timeout = should_timeout
        self.call_count = 0
        self.last_context: AgentExecutionContext | None = None

    async def execute(self, context: AgentExecutionContext) -> AgentResult:
        self.call_count += 1
        self.last_context = context
        if self.should_timeout:
            raise asyncio.TimeoutError("simulated timeout")
        if self.should_fail:
            return AgentResult(
                agent_name=self.config.name,
                status=AgentStatus.FAILED,
                error="simulated agent failure",
                execution_id=context.execution_id,
            )
        return AgentResult(
            agent_name=self.config.name,
            status=AgentStatus.COMPLETED,
            result={"answer": f"response from {self.config.name}"},
            execution_id=context.execution_id,
        )


def _make_context(execution_id: str = "test-exec-1") -> AgentExecutionContext:
    return AgentExecutionContext(
        execution_id=execution_id,
        task_type="rag_question_answer",
        payload={"query": "test question"},
    )


# ---------------------------------------------------------------------------
# 1. Agent registration and lookup
# ---------------------------------------------------------------------------

class TestAgentRegistration:
    def test_register_and_lookup_agent(self):
        registry = AgentRegistry()
        agent = _RecordingAgent("test-agent")
        registry.register(agent)
        assert registry.get("test-agent") is agent
        assert "test-agent" in registry.list_agents()

    def test_unregister_agent(self):
        registry = AgentRegistry()
        agent = _RecordingAgent("temp-agent")
        registry.register(agent)
        registry.unregister("temp-agent")
        assert registry.get("temp-agent") is None
        assert "temp-agent" not in registry.list_agents()

    def test_find_by_capability(self):
        registry = AgentRegistry()
        agent = _RecordingAgent("cap-agent")
        registry.register(agent)
        found = registry.find_by_capability(AgentCapability.RAG_QUESTION_ANSWER)
        assert len(found) == 1
        assert found[0].name == "cap-agent"

    def test_disabled_agent_not_found_by_capability(self):
        registry = AgentRegistry()
        agent = _RecordingAgent("disabled-agent")
        agent.config.enabled = False
        registry.register(agent)
        found = registry.find_by_capability(AgentCapability.RAG_QUESTION_ANSWER)
        assert found == []


# ---------------------------------------------------------------------------
# 2. Invalid agent input
# ---------------------------------------------------------------------------

class TestInvalidAgentInput:
    def test_superplier_rejects_unknown_task_type(self):
        registry = AgentRegistry()
        supervisor = SupervisorAgent(registry)
        context = _make_context()
        context.task_type = "nonexistent_task"
        context.payload = {"task_type": "nonexistent_task"}
        result = asyncio.run(supervisor.execute(context))
        assert result.status == AgentStatus.FAILED
        assert "Unknown task type" in (result.error or "")

    def test_rag_agent_rejects_empty_query(self):
        registry = AgentRegistry()
        registry.register(RAGKnowledgeAgent())
        orchestrator = AgentOrchestrator(registry)
        context = _make_context()
        context.payload = {"query": ""}
        result = asyncio.run(orchestrator.run_first_available(
            AgentCapability.RAG_QUESTION_ANSWER, context
        ))
        assert result.status == AgentStatus.FAILED
        assert "non-empty query" in (result.error or "")

    def test_job_analysis_agent_rejects_empty_fields(self):
        registry = AgentRegistry()
        registry.register(JobAnalysisAgent())
        orchestrator = AgentOrchestrator(registry)

        # Empty resume_text
        context = _make_context()
        context.task_type = "job_analysis"
        context.payload = {"resume_text": "", "job_description": "Python developer"}
        result = asyncio.run(orchestrator.run_first_available(
            AgentCapability.JOB_ANALYSIS, context
        ))
        assert result.status == AgentStatus.FAILED

        # Empty job_description
        context2 = _make_context()
        context2.task_type = "job_analysis"
        context2.payload = {"resume_text": "Python developer", "job_description": ""}
        result2 = asyncio.run(orchestrator.run_first_available(
            AgentCapability.JOB_ANALYSIS, context2
        ))
        assert result2.status == AgentStatus.FAILED


# ---------------------------------------------------------------------------
# 3 & 4. Supervisor routing and correct specialist selection
# ---------------------------------------------------------------------------

class TestSupervisorRouting:
    def test_classify_and_route_maps_task_types(self):
        registry = AgentRegistry()
        supervisor = SupervisorAgent(registry)

        cap, val = supervisor.classify_and_route("rag_question_answer")
        assert cap == AgentCapability.RAG_QUESTION_ANSWER
        assert val == "rag_question_answer"

        cap, val = supervisor.classify_and_route("resume_analysis")
        assert cap == AgentCapability.RESUME_ANALYSIS

        cap, val = supervisor.classify_and_route("job_analysis")
        assert cap == AgentCapability.JOB_ANALYSIS

        cap, val = supervisor.classify_and_route("email_draft")
        assert cap == AgentCapability.EMAIL_DRAFT

        # Aliases
        cap, val = supervisor.classify_and_route("rag")
        assert cap == AgentCapability.RAG_QUESTION_ANSWER

        # Unknown
        cap, val = supervisor.classify_and_route("mystery_task")
        assert cap is None
        assert val is None

    def test_route_returns_capability_value(self):
        registry = AgentRegistry()
        supervisor = SupervisorAgent(registry)
        assert supervisor.route("job_analysis") == "job_analysis"
        assert supervisor.route("unknown") is None

    def test_registry_has_all_four_specialists(self):
        reset_registry()
        registry = get_registry()
        names = registry.list_agents()
        assert "supervisor" in names
        assert "rag_knowledge" in names
        assert "resume_analysis" in names
        assert "job_analysis" in names
        assert "job_application_email" in names


# ---------------------------------------------------------------------------
# 5 & 6. Agent execution success and failure
# ---------------------------------------------------------------------------

class TestAgentExecution:
    def test_successful_agent_returns_completed(self):
        registry = AgentRegistry()
        agent = _RecordingAgent("success-agent")
        registry.register(agent)
        orchestrator = AgentOrchestrator(registry)
        context = _make_context()
        result = asyncio.run(orchestrator.run_agent("success-agent", context))
        assert result.status == AgentStatus.COMPLETED
        assert result.result["answer"] == "response from success-agent"
        assert agent.call_count == 1

    def test_failed_agent_returns_failed(self):
        registry = AgentRegistry()
        agent = _RecordingAgent("fail-agent", should_fail=True)
        registry.register(agent)
        orchestrator = AgentOrchestrator(registry)
        context = _make_context()
        result = asyncio.run(orchestrator.run_agent("fail-agent", context))
        assert result.status == AgentStatus.FAILED
        assert "simulated agent failure" in (result.error or "")
        assert agent.call_count == 3  # max_retries=2 -> 3 attempts total

    def test_unknown_agent_returns_failed(self):
        registry = AgentRegistry()
        orchestrator = AgentOrchestrator(registry)
        context = _make_context()
        result = asyncio.run(orchestrator.run_agent("nonexistent", context))
        assert result.status == AgentStatus.FAILED
        assert "not registered" in (result.error or "")


# ---------------------------------------------------------------------------
# 7. Timeout and retry behavior
# ---------------------------------------------------------------------------

class TestTimeoutAndRetry:
    def test_timeout_agent_returns_timeout_status(self):
        registry = AgentRegistry()
        agent = _RecordingAgent("timeout-agent", should_timeout=True)
        registry.register(agent)
        orchestrator = AgentOrchestrator(registry)
        context = _make_context()
        result = asyncio.run(orchestrator.run_agent("timeout-agent", context))
        assert result.status == AgentStatus.FAILED
        assert "timed out" in (result.error or "")
        assert agent.call_count == 3  # max_retries=2 -> 3 attempts

    def test_retry_eventually_succeeds(self):
        calls = {"n": 0}

        class FlakyAgent(BaseAgent):
            def __init__(self):
                config = AgentConfig(
                    name="flaky",
                    capabilities=[AgentCapability.RAG_QUESTION_ANSWER],
                    timeout_seconds=5,
                    max_retries=3,
                )
                super().__init__(config)

            async def execute(self, context):
                calls["n"] += 1
                if calls["n"] < 3:
                    return AgentResult(
                        agent_name=self.config.name,
                        status=AgentStatus.FAILED,
                        error="transient failure",
                        execution_id=context.execution_id,
                    )
                return AgentResult(
                    agent_name=self.config.name,
                    status=AgentStatus.COMPLETED,
                    result={"answer": "success on retry"},
                    execution_id=context.execution_id,
                )

        registry = AgentRegistry()
        registry.register(FlakyAgent())
        orchestrator = AgentOrchestrator(registry)
        context = _make_context()
        result = asyncio.run(orchestrator.run_agent("flaky", context))
        assert result.status == AgentStatus.COMPLETED
        assert result.result["answer"] == "success on retry"
        assert calls["n"] == 3


# ---------------------------------------------------------------------------
# 8. Invalid LLM responses (via supervisor fail-closed)
# ---------------------------------------------------------------------------

class TestInvalidLLMResponse:
    def test_supervisor_propagates_agent_failure(self):
        registry = AgentRegistry()
        registry.register(_RecordingAgent("broken-agent", should_fail=True))
        supervisor = SupervisorAgent(registry)
        context = _make_context()
        context.task_type = "rag_question_answer"
        context.payload = {"query": "test", "task_type": "rag_question_answer"}
        result = asyncio.run(supervisor.execute(context))
        assert result.status == AgentStatus.FAILED


# ---------------------------------------------------------------------------
# 9. Infinite-loop prevention
# ---------------------------------------------------------------------------

class TestInfiniteLoopPrevention:
    def test_max_steps_enforced(self):
        reset_registry()
        registry = get_registry()
        workflow = OrchestrationWorkflow(registry)

        # Use job_analysis which is deterministic and doesn't need Ollama.
        result = workflow.run(
            execution_id="loop-test-1",
            task_type="job_analysis",
            payload={
                "resume_text": "Python developer.",
                "job_description": "We need Python.",
            },
        )
        # Should complete without looping
        assert result["status"] in ("completed", "failed", "abstained")
        assert result["steps_executed"] <= MAX_WORKFLOW_STEPS


# ---------------------------------------------------------------------------
# 10. Workflow state validation
# ---------------------------------------------------------------------------

class TestWorkflowStateValidation:
    def test_workflow_returns_expected_fields(self):
        reset_registry()
        registry = get_registry()
        workflow = OrchestrationWorkflow(registry)
        result = workflow.run(
            execution_id="state-test-1",
            task_type="job_analysis",
            payload={
                "resume_text": "Python developer with SQL and Docker experience.",
                "job_description": "We need Python, SQL, and Kubernetes.",
            },
        )
        assert "execution_id" in result
        assert "task_type" in result
        assert "status" in result
        assert "final_answer" in result
        assert "steps_executed" in result
        assert result["execution_id"] == "state-test-1"

    def test_workflow_handles_unknown_task_type(self):
        reset_registry()
        registry = get_registry()
        workflow = OrchestrationWorkflow(registry)
        result = workflow.run(
            execution_id="state-test-2",
            task_type="mystery_task",
            payload={"query": "x"},
        )
        assert result["status"] == "failed"
        assert "Unknown task type" in (result.get("error") or "")


# ---------------------------------------------------------------------------
# 11. FastAPI orchestration endpoints
# ---------------------------------------------------------------------------

class TestOrchestrationEndpoints:
    def setup_method(self):
        reset_registry()
        self.client = TestClient(app)

    def test_list_agents_endpoint(self):
        response = self.client.get("/orchestrate/agents")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "agents" in data
        assert "count" in data
        agent_names = {a["name"] for a in data["agents"]}
        assert "supervisor" in agent_names
        assert "rag_knowledge" in agent_names
        assert "resume_analysis" in agent_names
        assert "job_analysis" in agent_names
        assert "job_application_email" in agent_names

    def test_get_agent_endpoint(self):
        response = self.client.get("/orchestrate/agents/rag_knowledge")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["name"] == "rag_knowledge"
        assert "rag_question_answer" in data["capabilities"]
        assert data["enabled"] is True

    def test_get_nonexistent_agent_returns_404(self):
        response = self.client.get("/orchestrate/agents/nonexistent")
        assert response.status_code == 404, response.text

    def test_orchestrate_unknown_task_type(self):
        response = self.client.post("/orchestrate", json={
            "task_type": "mystery_task",
            "payload": {"query": "x"},
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "failed"

    def test_orchestrate_missing_task_type(self):
        response = self.client.post("/orchestrate", json={
            "payload": {"query": "x"},
        })
        assert response.status_code == 422, response.text

    def test_orchestrate_empty_task_type(self):
        response = self.client.post("/orchestrate", json={
            "task_type": "",
            "payload": {"query": "x"},
        })
        assert response.status_code == 422, response.text

    def test_orchestrate_job_analysis_end_to_end(self):
        response = self.client.post("/orchestrate", json={
            "task_type": "job_analysis",
            "payload": {
                "resume_text": "Python developer with SQL and Docker experience.",
                "job_description": "We need Python, SQL, and Kubernetes.",
            },
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] in ("completed", "abstained")
        assert data["final_answer"] is not None
        fa = data["final_answer"]
        assert "matched_skills" in fa
        assert "missing_skills" in fa
        assert "match_percentage" in fa


# ---------------------------------------------------------------------------
# 12. Existing V1 functionality regression (smoke)
# ---------------------------------------------------------------------------

class TestV1RegressionSmoke:
    def test_existing_routes_still_work(self):
        client = TestClient(app)
        health = client.get("/health")
        assert health.status_code == 200
        root = client.get("/")
        assert root.status_code == 200

    def test_document_upload_and_status_route(self):
        client = TestClient(app)
        upload = client.post(
            "/documents/upload",
            files={"file": ("test.txt", b"Hello world test content.", "text/plain")},
        )
        assert upload.status_code == 200, upload.text
        doc_id = upload.json()["document"]["document_id"]

        status = client.get(f"/documents/{doc_id}/status")
        assert status.status_code == 200, status.text

        chunks = client.get(f"/documents/{doc_id}/chunks")
        assert chunks.status_code == 200, chunks.text

        delete = client.delete(f"/documents/{doc_id}")
        assert delete.status_code == 200, delete.text

    def test_job_analysis_api_route(self):
        client = TestClient(app)
        response = client.post("/jobs/analyze", json={
            "resume_text": "Python developer with FastAPI experience.",
            "job_description": "We need Python and Docker.",
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert "matched_skills" in data
        assert "match_percentage" in data
