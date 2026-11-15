"""AEGISCORE_PHASE1_WORKFLOW
Multi-Agent Orchestration Engine — LangGraph Workflow.

Defines the shared workflow state, supervisor and worker nodes,
conditional routing, controlled agent handoffs, maximum execution
limits, infinite-loop prevention, and graceful failure handling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langgraph.graph import StateGraph, END

from aegiscore.agent_base import (
    AgentCapability,
    AgentExecutionContext,
    AgentStatus,
    AgentRegistry,
    AgentOrchestrator,
    BaseAgent,
)
from aegiscore.supervisor import SupervisorAgent


logger = logging.getLogger("aegiscore.agent.workflow")


# Maximum number of workflow steps to prevent infinite loops.
MAX_WORKFLOW_STEPS = 10


def _run_async(coro):
    """Run an async coroutine in a fresh event loop.

    Avoids conflicts with pytest-anyio or other running event loops.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Workflow state is a plain dict with these keys:
#   execution_id, task_type, payload, metadata, current_step, max_steps,
#   supervisor_result, agent_result, final_answer, status, error


def _initial_state(
    execution_id: str,
    task_type: str,
    payload: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "execution_id": execution_id,
        "task_type": task_type,
        "payload": payload,
        "metadata": metadata,
        "current_step": 0,
        "max_steps": MAX_WORKFLOW_STEPS,
        "supervisor_result": None,
        "agent_result": None,
        "final_answer": None,
        "status": "pending",
        "error": None,
    }


class OrchestrationWorkflow:
    """LangGraph-based multi-agent orchestration workflow.

    Nodes:
        supervisor: classifies and routes the task
        worker: executes the selected specialist agent
        aggregate: validates and aggregates results into a final answer

    Conditional routing sends the workflow from supervisor to worker,
    then from worker to aggregate (or back to supervisor on retry,
    bounded by max_steps).
    """

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self.orchestrator = AgentOrchestrator(registry)
        self.supervisor = SupervisorAgent(registry)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        builder = StateGraph(dict)

        builder.add_node("supervisor", self._supervisor_node)
        builder.add_node("worker", self._worker_node)
        builder.add_node("aggregate", self._aggregate_node)

        builder.set_entry_point("supervisor")

        builder.add_conditional_edges(
            "supervisor",
            self._route_after_supervisor,
            {
                "worker": "worker",
                "end": END,
            },
        )

        builder.add_conditional_edges(
            "worker",
            self._route_after_worker,
            {
                "aggregate": "aggregate",
                "retry": "supervisor",
                "end": END,
            },
        )

        builder.add_edge("aggregate", END)

        return builder.compile()

    def _supervisor_node(self, state: dict[str, Any]) -> dict[str, Any]:
        state["current_step"] = state.get("current_step", 0) + 1
        if state["current_step"] > state.get("max_steps", MAX_WORKFLOW_STEPS):
            state["status"] = "failed"
            state["error"] = (
                "Workflow exceeded maximum step limit "
                f"({state.get('max_steps', MAX_WORKFLOW_STEPS)}); "
                "possible infinite loop."
            )
            return state

        task_type = state.get("task_type", "")
        payload = state.get("payload", {})

        execution_context = AgentExecutionContext(
            execution_id=state.get("execution_id", ""),
            task_type=task_type,
            payload=payload,
            metadata=state.get("metadata", {}),
        )

        try:
            result = _run_async(
                self.supervisor.execute(execution_context)
            )
        except Exception as exc:  # noqa: BLE001 — workflow boundary
            logger.exception("Supervisor node failed")
            state["status"] = "failed"
            state["error"] = f"Supervisor agent failed: {exc}"
            return state

        state["supervisor_result"] = {
            "agent_name": result.agent_name,
            "status": result.status,
            "result": result.result,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
            "attempts": result.attempts,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
        }

        if result.status == AgentStatus.FAILED:
            state["status"] = "failed"
            state["error"] = result.error or "Supervisor routing failed."
        elif result.status == AgentStatus.ABSTAINED:
            state["status"] = "abstained"
            state["final_answer"] = result.result
        else:
            state["status"] = "routed"

        return state

    def _worker_node(self, state: dict[str, Any]) -> dict[str, Any]:
        state["current_step"] = state.get("current_step", 0) + 1
        if state["current_step"] > state.get("max_steps", MAX_WORKFLOW_STEPS):
            state["status"] = "failed"
            state["error"] = (
                "Workflow exceeded maximum step limit "
                f"({state.get('max_steps', MAX_WORKFLOW_STEPS)}); "
                "possible infinite loop."
            )
            return state

        supervisor_result = state.get("supervisor_result") or {}
        task_type = state.get("task_type", "")

        capability_map = {
            "rag_question_answer": AgentCapability.RAG_QUESTION_ANSWER,
            "resume_analysis": AgentCapability.RESUME_ANALYSIS,
            "job_analysis": AgentCapability.JOB_ANALYSIS,
            "email_draft": AgentCapability.EMAIL_DRAFT,
        }
        capability = capability_map.get(task_type)

        execution_context = AgentExecutionContext(
            execution_id=state.get("execution_id", ""),
            task_type=task_type,
            payload=state.get("payload", {}),
            metadata=state.get("metadata", {}),
        )

        if capability is None:
            state["status"] = "failed"
            state["error"] = f"No capability mapping for task type '{task_type}'."
            return state

        try:
            result = _run_async(
                self.orchestrator.run_first_available(capability, execution_context)
            )
        except Exception as exc:  # noqa: BLE001 — workflow boundary
            logger.exception("Worker node failed")
            state["status"] = "failed"
            state["error"] = f"Worker agent failed: {exc}"
            return state

        state["agent_result"] = {
            "agent_name": result.agent_name,
            "status": result.status,
            "result": result.result,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
            "attempts": result.attempts,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
        }

        if result.status in (AgentStatus.COMPLETED, AgentStatus.ABSTAINED):
            state["status"] = "completed"
            state["final_answer"] = result.result
        elif result.status == AgentStatus.FAILED:
            state["status"] = "retry"
            state["error"] = result.error or "Specialist agent failed."
        else:
            state["status"] = "failed"
            state["error"] = (
                f"Unexpected agent status '{result.status}'."
            )

        return state

    def _aggregate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Validate and aggregate results into the final answer."""
        agent_result = state.get("agent_result") or {}
        final_answer = agent_result.get("result")

        if final_answer is None:
            state["status"] = "failed"
            state["error"] = "No agent result to aggregate."
            return state

        if not isinstance(final_answer, dict):
            final_answer = {"answer": str(final_answer), "abstained": False}

        state["final_answer"] = final_answer
        state["status"] = "completed"
        return state

    def _route_after_supervisor(self, state: dict[str, Any]) -> str:
        status = state.get("status", "")
        if status == "routed":
            return "worker"
        return "end"

    def _route_after_worker(self, state: dict[str, Any]) -> str:
        status = state.get("status", "")
        if status == "completed":
            return "aggregate"
        if status == "retry":
            if state.get("current_step", 0) < state.get(
                "max_steps", MAX_WORKFLOW_STEPS
            ):
                return "retry"
            return "end"
        return "end"

    def run(
        self,
        execution_id: str,
        task_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the orchestration workflow synchronously."""
        initial_state = _initial_state(
            execution_id=execution_id,
            task_type=task_type,
            payload=payload,
            metadata=metadata or {},
        )

        try:
            final_state = self.graph.invoke(initial_state)
        except Exception as exc:  # noqa: BLE001 — workflow boundary
            logger.exception("Workflow execution failed")
            return {
                "execution_id": execution_id,
                "task_type": task_type,
                "status": "failed",
                "error": f"Workflow execution failed: {exc}",
                "final_answer": None,
                "supervisor_result": None,
                "agent_result": None,
                "steps_executed": initial_state.get("current_step", 0),
            }

        if final_state is None:
            return {
                "execution_id": execution_id,
                "task_type": task_type,
                "status": "failed",
                "error": "Workflow returned no final state.",
                "final_answer": None,
                "supervisor_result": None,
                "agent_result": None,
                "steps_executed": initial_state.get("current_step", 0),
            }

        return {
            "execution_id": final_state.get("execution_id", execution_id),
            "task_type": final_state.get("task_type", task_type),
            "status": final_state.get("status", "failed"),
            "error": final_state.get("error"),
            "final_answer": final_state.get("final_answer"),
            "supervisor_result": final_state.get("supervisor_result"),
            "agent_result": final_state.get("agent_result"),
            "steps_executed": final_state.get("current_step", 0),
        }
