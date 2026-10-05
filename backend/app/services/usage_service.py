"""Daily query-quota tracking with PostgreSQL persistence and memory fallback.

Each chat/voice query consumes one unit of the caller's daily quota for
their plan (see plans_service). When the quota is exhausted the API
returns 429 with an upgrade hint instead of processing the query.
"""

from collections import OrderedDict
from datetime import datetime, timezone

from app.services import plans_service
from app.config import settings
import logging

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import Column, Date, Integer, MetaData, String, Table, create_engine, select
except ImportError:  # pragma: no cover
    Column = Date = Integer = MetaData = String = Table = create_engine = select = None

# {(client_key, plan_id, day): count} — bounded, pruned on every access.
_counters: "OrderedDict[tuple[str, str, str], int]" = OrderedDict()
_MAX_KEYS = 20_000
_engine = None
_table = None
_FREE_GREETINGS = {
    "hi",
    "hello",
    "hey",
    "hi there",
    "hello there",
    "good morning",
    "good afternoon",
    "good evening",
    "ආයුබෝවන්",
    "வணக்கம்",
}


def is_free_greeting(query: str) -> bool:
    """Return whether a conversational greeting should bypass daily quota."""
    return " ".join(query.strip().lower().split()) in _FREE_GREETINGS


async def initialize(database_url: str | None = None) -> None:
    """Initialize persistent usage storage when the database is available."""
    global _engine, _table
    url = database_url if database_url is not None else settings.database_url
    if not url or create_engine is None:
        return
    try:
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        _engine = create_engine(url, pool_pre_ping=True)
        metadata = MetaData()
        _table = Table(
            "daily_usage", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("client_key", String(255), nullable=False),
            Column("plan_id", String(32), nullable=False),
            Column("usage_day", Date, nullable=False),
            Column("used", Integer, nullable=False, default=0),
        )
        metadata.create_all(_engine)
        logger.info("Daily usage persistence initialized")
    except Exception:
        logger.exception("Daily usage persistence unavailable; using memory")
        _engine = None
        _table = None


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
    used = _get_used(client_key, plan["id"], today)
    if limit > 0 and used >= limit:
        return False, 0, limit
    _set_used(client_key, plan["id"], today, used + 1)
    remaining = (limit - used - 1) if limit > 0 else -1
    return True, remaining, limit


def get_usage(client_key: str, plan_id: str) -> dict:
    """Current quota state without consuming."""
    plan = plans_service.get_plan(plan_id)
    limit = int(plan.get("queries_per_day", 0))
    today = _today()
    _prune(today)
    used = _get_used(client_key, plan["id"], today)
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
    if _engine is not None and _table is not None:
        try:
            with _engine.begin() as conn:
                conn.execute(_table.delete())
        except Exception:
            logger.exception("Failed to reset persistent usage state")


def _get_used(client_key: str, plan_id: str, today: str) -> int:
    if _engine is not None and _table is not None:
        try:
            with _engine.connect() as conn:
                row = conn.execute(
                    select(_table.c.used).where(
                        (_table.c.client_key == client_key)
                        & (_table.c.plan_id == plan_id)
                        & (_table.c.usage_day == datetime.strptime(today, "%Y-%m-%d").date())
                    )
                ).first()
            return int(row.used) if row else 0
        except Exception:
            logger.exception("Failed to read persistent usage")
    return _counters.get((client_key, plan_id, today), 0)


def _set_used(client_key: str, plan_id: str, today: str, used: int) -> None:
    _counters[(client_key, plan_id, today)] = used
    if _engine is None or _table is None:
        return
    try:
        usage_day = datetime.strptime(today, "%Y-%m-%d").date()
        with _engine.begin() as conn:
            row = conn.execute(
                select(_table.c.id).where(
                    (_table.c.client_key == client_key)
                    & (_table.c.plan_id == plan_id)
                    & (_table.c.usage_day == usage_day)
                )
            ).first()
            if row:
                conn.execute(_table.update().where(_table.c.id == row.id).values(used=used))
            else:
                conn.execute(_table.insert().values(
                    client_key=client_key,
                    plan_id=plan_id,
                    usage_day=usage_day,
                    used=used,
                ))
    except Exception:
        logger.exception("Failed to persist usage")
