"""Chat API endpoints - main user interaction route."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.models.schemas import ChatRequest, ChatResponse
from app.agents.orchestrator.orchestrator_agent import OrchestratorAgent

router = APIRouter()

# Orchestrator instance
orchestrator = OrchestratorAgent()


@router.post("/query", response_model=ChatResponse)
async def process_query(request: ChatRequest):
    """
    Process a user's climate-related query through the multi-agent pipeline.

    The orchestrator receives the query, coordinates the specialized agents
    (NLP, IR, Analysis, Verification, Recommendation), and returns a
    comprehensive response with evidence and recommendations.
    """
    try:
        response = await orchestrator.process_user_query(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@router.get("/history")
async def get_chat_history(session_id: Optional[str] = None):
    """Retrieve chat history for a session."""
    # Placeholder - will be implemented with database
    return {
        "session_id": session_id,
        "messages": [],
        "message": "Chat history will be available once database is connected."
    }
