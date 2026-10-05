"""Plans, usage, subscriptions & Stripe payments."""

import hashlib
import hmac
import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.routers.deps import client_key, get_current_user_optional, get_current_user_required, resolve_plan
from app.services import auth_service
from app.services import plans_service
from app.services import usage_service

router = APIRouter()
logger = logging.getLogger(__name__)


class SubscribeRequest(BaseModel):
    plan_id: str
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|annual)$")


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
    """Demo activation: record a plan on the account without real payment.

    Used when Stripe is not configured (local evaluation). Card data never
    reaches this endpoint. When Stripe IS configured the frontend uses
    Checkout Sessions instead; this endpoint stays for free downgrades.
    Enterprise cannot be self-activated here.
    """
    user = get_current_user_required(request)
    if body.plan_id == "free":
        pass  # downgrade always allowed
    elif settings.stripe_secret_key and body.plan_id in ("premium", "business"):
        raise HTTPException(
            status_code=400,
            detail="Paid plans require Stripe checkout while payments are configured.",
        )
    try:
        updated = auth_service.set_plan(user["id"], body.plan_id, body.billing_cycle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    plan = plans_service.get_plan(updated.get("plan_id"))
    state = usage_service.get_usage(f"user:{updated['id']}", plan["id"])
    return {"user": auth_service._public_user(updated), "usage": state}


@router.get("/payment-config")
async def payment_config():
    """Whether real Stripe payments are configured (no secrets leaked)."""
    return {"stripe_enabled": bool(settings.stripe_secret_key)}


@router.post("/checkout-session")
async def create_checkout_session(payload: CheckoutSessionRequest, request: Request):
    """Create a Stripe-hosted Checkout Session for a paid plan.

    Bound to the signed-in account (client_reference_id = user id) so the
    entitlement can only ever activate its owner.
    """
    user = get_current_user_required(request)
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
        "client_reference_id": user["id"],
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "lkr",
        "line_items[0][price_data][unit_amount]": str(int(amount) * 100),
        "line_items[0][price_data][recurring][interval]": "year" if payload.annual else "month",
        "line_items[0][price_data][product_data][name]": f"Climora AI {plan['name']}",
        "line_items[0][price_data][product_data][description]": plan["tagline"],
        "metadata[plan_id]": plan["id"],
        "metadata[billing_cycle]": "annual" if payload.annual else "monthly",
    }

    import httpx
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
    except Exception:
        logger.exception("Stripe Checkout session request failed")
        raise HTTPException(status_code=502, detail="Unable to create payment session.")


@router.get("/checkout-session/{session_id}")
async def verify_checkout_session(session_id: str, request: Request):
    """Verify a completed Checkout Session and activate its plan on the account."""
    user = get_current_user_required(request)
    if not settings.stripe_secret_key:
        # Demo mode (no Stripe keys): nothing to verify server-side; the plan
        # was already recorded via POST /subscribe.
        plan = plans_service.get_plan(user.get("plan_id"))
        return {
            "plan_id": plan["id"],
            "billing_cycle": user.get("billing_cycle", "monthly"),
            "session_id": session_id,
        }
    if not session_id.startswith("cs_") or len(session_id) > 255:
        raise HTTPException(status_code=400, detail="Invalid checkout session.")

    import httpx
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
        if data.get("client_reference_id") != user["id"]:
            raise HTTPException(status_code=403, detail="Checkout session does not belong to this account.")
        if data.get("status") != "complete" or data.get("payment_status") not in {"paid", "no_payment_required"}:
            raise HTTPException(status_code=409, detail="Payment has not been completed.")

        cycle = "annual" if metadata.get("billing_cycle") == "annual" else "monthly"
        updated = auth_service.set_plan(user["id"], plan["id"], cycle)
        state = usage_service.get_usage(f"user:{user['id']}", plan["id"])
        return {
            "plan_id": plan["id"],
            "billing_cycle": cycle,
            "session_id": data["id"],
            "user": auth_service._public_user(updated),
            "usage": state,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Stripe Checkout session verification failed")
        raise HTTPException(status_code=502, detail="Unable to verify payment session.")


def _verify_webhook_signature(payload: bytes, header: str, secret: str) -> bool:
    """Validate a Stripe-Signature header (t=...,v1=...) with a constant-time compare."""
    try:
        parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
        timestamp = parts.get("t", "")
        signatures = [v for k, v in (p.split("=", 1) for p in header.split(",") if "=" in p) if k.strip() == "v1"]
        if not timestamp or not signatures:
            return False
        if abs(time.time() - int(timestamp)) > 300:
            return False  # replay protection: 5-minute tolerance
        expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, s) for s in signatures)
    except Exception:
        return False


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe event webhook: activates plans after verified real payments.

    Configure `checkout.session.completed` to this URL in the Stripe
    dashboard. Signature-verified with STRIPE_WEBHOOK_SECRET; no SDK needed.
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhooks are not configured.")
    payload = await request.body()
    if not _verify_webhook_signature(
        payload, request.headers.get("Stripe-Signature", ""), settings.stripe_webhook_secret
    ):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")
    try:
        event = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")
    if event.get("type") == "checkout.session.completed":
        session = event.get("data", {}).get("object", {}) or {}
        user_id = session.get("client_reference_id") or ""
        metadata = session.get("metadata") or {}
        plan = plans_service.get_plan(metadata.get("plan_id"))
        user = auth_service.get_user_by_id(user_id) if user_id else None
        if user is not None and plan["id"] in {"premium", "business"}:
            cycle = "annual" if metadata.get("billing_cycle") == "annual" else "monthly"
            auth_service.set_plan(user["id"], plan["id"], cycle)
            logger.info("Webhook activated %s for user %s", plan["id"], user["id"])
    return {"received": True}
