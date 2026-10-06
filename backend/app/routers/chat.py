"""Chat API endpoints - main user interaction route."""

import json
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.models.schemas import ChatRequest, ChatResponse
from app.agents.orchestrator.orchestrator_agent import OrchestratorAgent
from app.agents.orchestrator.shared import get_orchestrator
from app.routers.deps import QuotaLimit, RateLimit, refund_quota

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=ChatResponse, dependencies=[RateLimit, QuotaLimit])
async def process_query(request: ChatRequest, http_request: Request):
    """
    Process a user's climate-related query through the multi-agent pipeline.

    The orchestrator receives the query, coordinates the specialized agents
    (NLP, IR, Analysis, Verification, Recommendation), and returns a
    comprehensive response with evidence and recommendations.

    A failed pipeline refunds the consumed quota unit — errors never burn quota.
    """
    try:
        response = await get_orchestrator().process_user_query(request)
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Chat query failed")
        refund_quota(http_request)
        raise HTTPException(
            status_code=500,
            detail="Error processing query. Please try again."
        )


@router.post("/query/stream", dependencies=[RateLimit, QuotaLimit])
async def process_query_stream(request: ChatRequest, http_request: Request):
    """
    Process a query and stream real-time agent-communication events via SSE.

    Emits Server-Sent Events as each agent is actually invoked and returns, so
    the frontend Agent Mesh can visualise the exact live communication flow.
    The final event (`done`) carries the full ChatResponse. When the pipeline
    finishes the stream closes, telling the mesh that communication has stopped.

    A fresh orchestrator instance is used per request so the per-request event
    callback never cross-wires with other concurrent streams. A failed pipeline
    refunds the consumed quota unit.
    """
    stream_orchestrator = OrchestratorAgent()

    async def event_generator():
        try:
            async for event in stream_orchestrator.process_user_query_stream(request):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            refund_quota(http_request)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
        },
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
