"""AEGISCORE_PHASE1_AGENT_REGISTRY
Multi-Agent Orchestration Engine — Global Agent Registry.

Creates and registers all specialist agents with the supervisor agent.
Provides a singleton registry for use by the workflow and API layer.
"""

from __future__ import annotations

from aegiscore.agent_base import AgentRegistry
from aegiscore.email_agent import JobApplicationEmailDraftAgent
from aegiscore.job_analysis_agent import JobAnalysisAgent
from aegiscore.rag_agent import RAGKnowledgeAgent
from aegiscore.resume_agent import ResumeAnalysisAgent
from aegiscore.supervisor import SupervisorAgent


# Module-level singleton registry.
_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """Return the singleton agent registry, creating it on first use."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()

        # Register the supervisor agent first.
        supervisor = SupervisorAgent(_registry)
        _registry.register(supervisor)

        # Register specialist agents.
        _registry.register(RAGKnowledgeAgent())
        _registry.register(ResumeAnalysisAgent())
        _registry.register(JobAnalysisAgent())
        _registry.register(JobApplicationEmailDraftAgent())

    return _registry


def reset_registry() -> AgentRegistry:
    """Clear and rebuild the singleton registry (mainly for testing)."""
    global _registry
    _registry = AgentRegistry()
    supervisor = SupervisorAgent(_registry)
    _registry.register(supervisor)
    _registry.register(RAGKnowledgeAgent())
    _registry.register(ResumeAnalysisAgent())
    _registry.register(JobAnalysisAgent())
    _registry.register(JobApplicationEmailDraftAgent())
    return _registry
