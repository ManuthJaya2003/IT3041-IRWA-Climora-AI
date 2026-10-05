"""Plans, usage & server-side subscription endpoints."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.routers.deps import client_key, get_current_user_optional, get_current_user_required, resolve_plan
from app.services import auth_service
from app.services import plans_service
from app.services import usage_service

router = APIRouter()


class SubscribeRequest(BaseModel):
    plan_id: str
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|annual)$")


@router.get("/plans")
async def get_plans():
    """List all commercial plans with pricing, quotas and features."""
    return {"plans": plans_service.list_plans()}


@router.get("/usage")
async def get_usage(request: Request):
    """Caller's current plan and daily quota state (does not consume).

    Signed-out callers see the 2-query guest trial, not the Free plan quota.
    """
    user = get_current_user_optional(request)
    if user is None:
        state = usage_service.get_anonymous_usage(client_key(request))
        state["authenticated"] = False
        return state
    plan = resolve_plan(request)
    state = usage_service.get_usage(client_key(request), plan["id"])
    state["authenticated"] = True
    state["user"] = auth_service._public_user(user)
    return state


@router.post("/subscribe")
async def subscribe(body: SubscribeRequest, request: Request):
    """Activate a plan on the signed-in user's account (server-side record).

    The demo card form runs in the browser and never sends card data here —
    this endpoint only records the entitlement after the (demo) payment step.
    A real Stripe webhook should call ``auth_service.set_plan`` the same way.
    Downgrading to Free is always allowed; Enterprise goes via sales.
    """
    user = get_current_user_required(request)
    try:
        updated = auth_service.set_plan(user["id"], body.plan_id, body.billing_cycle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    plan = plans_service.get_plan(updated.get("plan_id"))
    state = usage_service.get_usage(f"user:{updated['id']}", plan["id"])
    return {"user": auth_service._public_user(updated), "usage": state}


# --- Back-compat shims: older frontends call these Stripe-style routes. ---
# They now require sign-in and simply record the plan server-side.

@router.post("/checkout-session")
async def create_checkout_session_compat(body: dict, request: Request):
    user = get_current_user_required(request)
    plan_id = str(body.get("plan_id", "free"))
    annual = bool(body.get("annual", False))
    try:
        updated = auth_service.set_plan(user["id"], plan_id, "annual" if annual else "monthly")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "session_id": f"demo-{updated['id']}-{plan_id}",
        "checkout_url": "/plans?checkout=success",
        "plan_id": updated["plan_id"],
    }


@router.get("/checkout-session/{session_id}")
async def verify_checkout_session_compat(session_id: str, request: Request):
    user = get_current_user_required(request)
    plan = plans_service.get_plan(user.get("plan_id"))
    return {
        "plan_id": plan["id"],
        "billing_cycle": user.get("billing_cycle", "monthly"),
        "session_id": session_id,
    }
