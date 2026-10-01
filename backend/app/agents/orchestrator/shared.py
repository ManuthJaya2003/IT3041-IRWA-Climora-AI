"""Shared orchestrator singleton for API routers.

chat, speech and agents routers must share ONE OrchestratorAgent so that
session/conversation state (follow-up context, chat history) is consistent
no matter which endpoint served the request.
"""

from functools import lru_cache

from app.agents.orchestrator.orchestrator_agent import OrchestratorAgent


@lru_cache(maxsize=1)
def get_orchestrator() -> OrchestratorAgent:
    return OrchestratorAgent()
