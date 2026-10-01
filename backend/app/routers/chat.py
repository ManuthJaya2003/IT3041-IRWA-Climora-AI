"""Chat API endpoints - main user interaction route."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.models.schemas import ChatRequest, ChatResponse
from app.agents.orchestrator.shared import get_orchestrator
from app.routers.deps import QuotaLimit, RateLimit

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=ChatResponse, dependencies=[RateLimit, QuotaLimit])
async def process_query(request: ChatRequest):
    """
    Process a user's climate-related query through the multi-agent pipeline.

    The orchestrator receives the query, coordinates the specialized agents
    (NLP, IR, Analysis, Verification, Recommendation), and returns a
    comprehensive response with evidence and recommendations.
    """
    try:
        response = await get_orchestrator().process_user_query(request)
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Chat query failed")
        raise HTTPException(
            status_code=500,
            detail="Error processing query. Please try again."
        )


@router.get("/history")
async def get_chat_history(session_id: Optional[str] = None):
    """Retrieve stored chat history for a session."""
    if not session_id:
        return {
            "session_id": None,
            "messages": [],
            "message": "Pass ?session_id=<id> to retrieve that session's history.",
        }
    return {
        "session_id": session_id,
        "messages": get_orchestrator().get_session_history(session_id),
    }
