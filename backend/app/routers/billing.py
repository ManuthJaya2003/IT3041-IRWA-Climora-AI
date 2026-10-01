"""Plans & usage endpoints — serves the commercial tier model."""

from fastapi import APIRouter, Request

from app.routers.deps import client_key, resolve_plan
from app.services import plans_service
from app.services import usage_service

router = APIRouter()


@router.get("/plans")
async def get_plans():
    """List all commercial plans with pricing, quotas and features."""
    return {"plans": plans_service.list_plans()}


@router.get("/usage")
async def get_usage(request: Request):
    """Caller's current plan and daily quota state (does not consume)."""
    plan = resolve_plan(request)
    state = usage_service.get_usage(client_key(request), plan["id"])
    return state
