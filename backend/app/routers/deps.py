"""Shared FastAPI dependencies: admin auth and rate limiting.

These implement the proposal's security controls (authentication for
protected functions, rate limiting) without extra third-party packages.
"""

import logging
import time
from collections import OrderedDict

from fastapi import Depends, HTTPException, Request

from app.config import settings
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


def client_key(request: Request) -> str:
    """Stable per-caller key for quotas (IP address, proxy-aware)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def resolve_plan(request: Request) -> dict:
    """Plan from the X-Plan header (unknown values fall back to Free)."""
    return plans_service.get_plan(request.headers.get("X-Plan"))


def enforce_quota(request: Request) -> None:
    """Daily per-plan query quota. Exceeding callers get HTTP 429."""
    plan = resolve_plan(request)
    allowed, _remaining, limit = usage_service.check_and_consume(
        client_key(request), plan["id"]
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily query quota exceeded for the {plan['name']} plan "
                f"({limit}/day). Upgrade your plan for higher limits."
            ),
        )


QuotaLimit = Depends(enforce_quota)
