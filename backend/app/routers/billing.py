"""Plans, usage, and Stripe Checkout endpoints."""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.routers.deps import client_key, resolve_plan
from app.services import plans_service
from app.services import usage_service

router = APIRouter()
logger = logging.getLogger(__name__)


class CheckoutSessionRequest(BaseModel):
    plan_id: str = Field(..., pattern=r"^(premium|business)$")
    annual: bool = False
    success_url: str = Field(..., min_length=10, max_length=2048)
    cancel_url: str = Field(..., min_length=10, max_length=2048)


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


@router.post("/checkout-session")
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    request: Request,
):
    """Create a Stripe-hosted Checkout Session for a paid plan."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe payments are not configured.")

    plan = plans_service.get_plan(payload.plan_id)
    amount = plan["annual_lkr"] if payload.annual else plan["monthly_lkr"]
    if not amount:
        raise HTTPException(status_code=400, detail="Selected plan is not payable.")

    form = {
        "mode": "subscription",
        "success_url": payload.success_url,
        "cancel_url": payload.cancel_url,
        "client_reference_id": client_key(request),
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "lkr",
        "line_items[0][price_data][unit_amount]": str(int(amount) * 100),
        "line_items[0][price_data][recurring][interval]": "year" if payload.annual else "month",
        "line_items[0][price_data][product_data][name]": f"Climora AI {plan['name']}",
        "line_items[0][price_data][product_data][description]": plan["tagline"],
        "metadata[plan_id]": plan["id"],
        "metadata[billing_cycle]": "annual" if payload.annual else "monthly",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=form,
                auth=(settings.stripe_secret_key, ""),
            )
        if response.status_code >= 400:
            logger.error("Stripe Checkout session failed with status %s", response.status_code)
            raise HTTPException(status_code=502, detail="Unable to create payment session.")
        data = response.json()
        return {"session_id": data["id"], "checkout_url": data["url"]}
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("Stripe Checkout session request failed")
        raise HTTPException(status_code=502, detail="Unable to create payment session.")


@router.get("/checkout-session/{session_id}")
async def verify_checkout_session(session_id: str, request: Request):
    """Verify a completed Checkout Session before activating its plan locally."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe payments are not configured.")
    if not session_id.startswith("cs_") or len(session_id) > 255:
        raise HTTPException(status_code=400, detail="Invalid checkout session.")

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
                auth=(settings.stripe_secret_key, ""),
            )
        if response.status_code >= 400:
            logger.warning("Stripe Checkout session lookup failed with status %s", response.status_code)
            raise HTTPException(status_code=404, detail="Checkout session was not found.")

        data = response.json()
        metadata = data.get("metadata") or {}
        plan_id = metadata.get("plan_id")
        plan = plans_service.get_plan(plan_id)
        if plan["id"] not in {"premium", "business"}:
            raise HTTPException(status_code=400, detail="Checkout session has no valid paid plan.")
        if data.get("client_reference_id") != client_key(request):
            raise HTTPException(status_code=403, detail="Checkout session does not belong to this client.")
        if data.get("status") != "complete" or data.get("payment_status") not in {"paid", "no_payment_required"}:
            raise HTTPException(status_code=409, detail="Payment has not been completed.")

        cycle = "annual" if metadata.get("billing_cycle") == "annual" else "monthly"
        return {
            "plan_id": plan["id"],
            "billing_cycle": cycle,
            "session_id": data["id"],
        }
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("Stripe Checkout session verification failed")
        raise HTTPException(status_code=502, detail="Unable to verify payment session.")
