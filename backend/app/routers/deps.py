"""Shared FastAPI dependencies: admin auth and rate limiting.

These implement the proposal's security controls (authentication for
protected functions, rate limiting) without extra third-party packages.
"""

import logging
import time
from collections import OrderedDict

from fastapi import Depends, HTTPException, Request

from app.config import settings
from app.services import auth_service
from app.services import plans_service
from app.services import usage_service

logger = logging.getLogger(__name__)

# In-memory sliding-window buckets: {client_key: [monotonic timestamps]}.
# Bounded so a flood of unique IPs cannot grow memory without limit.
_rate_buckets: "OrderedDict[str, list[float]]" = OrderedDict()
_MAX_BUCKETS = 10_000


def require_admin(request: Request) -> None:
    """Authentication for protected (mutating) functions.

    If ADMIN_TOKEN is configured, callers must send a matching
    ``X-Admin-Token`` header. If it is not configured (local development),
    access is allowed but a warning is logged so this never silently
    reaches production unprotected.
    """
    token = settings.admin_token
    if not token:
        logger.warning(
            "Protected endpoint %s accessed with no ADMIN_TOKEN configured "
            "(dev mode: allowed). Set ADMIN_TOKEN in production.",
            request.url.path,
        )
        return
    if request.headers.get("X-Admin-Token") != token:
        raise HTTPException(status_code=401, detail="Admin token required.")


def reset_rate_limit_state() -> None:
    """Clear all rate-limit buckets (used by tests)."""
    _rate_buckets.clear()


def rate_limit(request: Request) -> None:
    """Sliding-window rate limit per client IP.

    Limits come from settings (RATE_LIMIT_REQUESTS per
    RATE_LIMIT_WINDOW_SECONDS). Exceeding callers get HTTP 429.
    """
    limit = settings.rate_limit_requests
    window = settings.rate_limit_window_seconds
    if limit <= 0:
        return  # rate limiting disabled

    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    cutoff = now - window

    bucket = _rate_buckets.get(client)
    if bucket is None:
        bucket = []
        _rate_buckets[client] = bucket

    # Drop expired entries.
    while bucket and bucket[0] <= cutoff:
        bucket.pop(0)

    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
        )
    bucket.append(now)

    # Bound memory: evict oldest client buckets first.
    while len(_rate_buckets) > _MAX_BUCKETS:
        _rate_buckets.popitem(last=False)


# Re-export Depends-friendly alias for route decorators.
AdminAuth = Depends(require_admin)
RateLimit = Depends(rate_limit)


def get_current_user_optional(request: Request) -> dict | None:
    """Authenticated user when a valid Bearer token is present, else None.

    Anonymous callers are allowed (Free tier, IP-based quota). Never raises.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    user_id = auth_service.decode_user_id(auth[7:].strip())
    if not user_id:
        return None
    try:
        return auth_service.get_user_by_id(user_id)
    except Exception:
        return None


def get_current_user_required(request: Request) -> dict:
    """Authenticated user or HTTP 401."""
    user = get_current_user_optional(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return user


def client_key(request: Request) -> str:
    """Stable per-caller key for quotas: user id when signed in, IP otherwise."""
    user = get_current_user_optional(request)
    if user is not None:
        return f"user:{user['id']}"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def resolve_plan(request: Request) -> dict:
    """Server-side plan: authenticated user's plan wins.

    Enterprise is inherited: membership in any enterprise org unlocks it.
    ``X-Plan`` is only honoured for anonymous callers (and unknown values
    fall back to Free), so a signed-in user can never spoof a higher tier.
    """
    user = get_current_user_optional(request)
    if user is None:
        return plans_service.get_plan(request.headers.get("X-Plan"))
    try:
        from app.services import org_service
        if org_service.user_has_enterprise(user["id"]):
            return plans_service.get_plan("enterprise")
    except Exception:
        pass
    return plans_service.get_plan(user.get("plan_id"))


async def enforce_quota(request: Request) -> None:
    """Daily query quota. Exceeding callers get HTTP 429.

    Signed-out callers get a 2-query/day guest trial (per IP), not the full
    Free plan — signing in unlocks 100 free queries/day on the account.

    Consumed units are recorded on ``request.state`` so a failing pipeline
    can refund them (failed requests must not burn quota).
    """
    try:
        payload = await request.json()
    except ValueError:
        payload = {}
    query = payload.get("query", "") if isinstance(payload, dict) else ""
    if usage_service.is_free_greeting(query):
        return
    key = client_key(request)
    user = get_current_user_optional(request)
    if user is None:
        allowed, _remaining, limit = usage_service.check_and_consume_anonymous(key)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Guest trial exhausted ({limit} queries/day). "
                    "Sign in for 100 free queries/day."
                ),
            )
        request.state.quota_consumed = (key, "guest")
        return
    plan = resolve_plan(request)
    allowed, _remaining, limit = usage_service.check_and_consume(key, plan["id"])
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily query quota exceeded for the {plan['name']} plan "
                f"({limit}/day). Upgrade your plan for higher limits."
            ),
        )
    request.state.quota_consumed = (key, plan["id"])


def refund_quota(request: Request) -> None:
    """Give back the unit this request consumed (call when the pipeline fails)."""
    consumed = getattr(request.state, "quota_consumed", None)
    if not consumed:
        return
    request.state.quota_consumed = None
    try:
        client, plan_id = consumed
        usage_service.refund(client, plan_id)
    except Exception:
        logger.exception("Failed to refund quota")


QuotaLimit = Depends(enforce_quota)
