"""Opt-in Web Push alert subscription endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.alert_service import alert_service

router = APIRouter()


class PushSubscription(BaseModel):
    endpoint: str = Field(..., min_length=20, max_length=2048)
    keys: dict[str, str]


class SubscriptionRequest(BaseModel):
    subscription: PushSubscription
    location: str = Field(default="", max_length=120)


@router.get("/config")
async def alert_config():
    return {
        "enabled": bool(settings.vapid_public_key and settings.vapid_private_key),
        "public_key": settings.vapid_public_key,
    }


@router.post("/subscribe", status_code=204)
async def subscribe(payload: SubscriptionRequest):
    if not settings.vapid_public_key:
        raise HTTPException(status_code=503, detail="Web Push alerts are not configured.")
    alert_service.save_subscription(payload.subscription.model_dump(), payload.location.strip())


@router.delete("/subscribe", status_code=204)
async def unsubscribe(payload: PushSubscription):
    alert_service.remove_subscription(payload.model_dump())


@router.post("/test")
async def test_alert(payload: PushSubscription):
    if not settings.vapid_private_key:
        raise HTTPException(status_code=503, detail="Web Push alerts are not configured.")
    try:
        alert_service.send_test(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to deliver test notification.") from exc
    return {"sent": True, "delivery": "accepted_by_push_service"}
