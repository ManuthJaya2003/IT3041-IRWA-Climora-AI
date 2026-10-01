"""Daily query-quota tracking per plan (in-memory, dependency-free).

Each chat/voice query consumes one unit of the caller's daily quota for
their plan (see plans_service). When the quota is exhausted the API
returns 429 with an upgrade hint instead of processing the query.
"""

from collections import OrderedDict
from datetime import datetime, timezone

from app.services import plans_service

# {(client_key, plan_id, day): count} — bounded, pruned on every access.
_counters: "OrderedDict[tuple[str, str, str], int]" = OrderedDict()
_MAX_KEYS = 20_000


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _prune(today: str) -> None:
    stale = [k for k in _counters if k[2] != today]
    for k in stale:
        del _counters[k]
    while len(_counters) > _MAX_KEYS:
        _counters.popitem(last=False)


def check_and_consume(client_key: str, plan_id: str) -> tuple[bool, int, int]:
    """Consume one query unit. Returns (allowed, remaining, limit).

    A plan limit of 0 means unlimited.
    """
    plan = plans_service.get_plan(plan_id)
    limit = int(plan.get("queries_per_day", 0))
    today = _today()
    _prune(today)
    key = (client_key, plan["id"], today)
    used = _counters.get(key, 0)
    if limit > 0 and used >= limit:
        return False, 0, limit
    _counters[key] = used + 1
    remaining = (limit - used - 1) if limit > 0 else -1
    return True, remaining, limit


def get_usage(client_key: str, plan_id: str) -> dict:
    """Current quota state without consuming."""
    plan = plans_service.get_plan(plan_id)
    limit = int(plan.get("queries_per_day", 0))
    today = _today()
    _prune(today)
    used = _counters.get((client_key, plan["id"], today), 0)
    remaining = (max(0, limit - used)) if limit > 0 else -1
    return {
        "plan": plan["id"],
        "plan_name": plan["name"],
        "used_today": used,
        "remaining_today": remaining,  # -1 = unlimited
        "daily_limit": limit,  # 0 = unlimited
        "day": today,
    }


def reset_usage_state() -> None:
    """Clear all counters (used by tests)."""
    _counters.clear()
