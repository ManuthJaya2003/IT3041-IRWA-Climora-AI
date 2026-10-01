"""Chat history persistence: PostgreSQL when reachable, memory otherwise.

Every conversation turn is always kept in a bounded in-memory cache. When
``DATABASE_URL`` points at a reachable PostgreSQL server, turns are
additionally persisted so history survives backend restarts. Any database
failure degrades silently back to memory — history must never break chat.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import (
        Column, DateTime, Integer, MetaData, String, Table, Text,
        create_engine, desc,
    )
    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover - requirements always include it
    _SQLALCHEMY_AVAILABLE = False

MAX_TURNS_PER_SESSION = 50


class HistoryService:
    """Turn storage with transparent PostgreSQL/memory backends."""

    def __init__(self):
        self._engine = None
        self._table = None
        self._backend = "memory"
        self._memory: dict[str, list[dict]] = {}

    async def initialize(self, database_url: Optional[str] = None) -> str:
        """Connect to a SQL database if possible. Returns the active backend name."""
        url = database_url if database_url is not None else settings.database_url
        if not url or not _SQLALCHEMY_AVAILABLE:
            return self._backend
        try:
            is_pg = url.startswith("postgresql")
            if is_pg and "://" in url and "+" not in url.split("://")[0]:
                # SQLAlchemy defaults to psycopg2; we ship psycopg v3.
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            engine_kwargs: dict = {"pool_pre_ping": True}
            if is_pg:
                engine_kwargs.update(
                    pool_size=2, max_overflow=2, connect_args={"connect_timeout": 3}
                )
            engine = create_engine(url, **engine_kwargs)
            metadata = MetaData()
            table = Table(
                "chat_turns", metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("session_id", String(64), index=True, nullable=False),
                Column("query", Text, nullable=False),
                Column("response_summary", Text, nullable=False),
                Column("created_at", DateTime(timezone=True), nullable=False),
            )
            metadata.create_all(engine)
            with engine.connect() as conn:
                conn.execute(table.select().limit(1))
            self._engine = engine
            self._table = table
            self._backend = "postgresql" if is_pg else "sqlite"
            print(f"   ✓ Chat history backend: {self._backend}")
        except Exception as exc:
            logger.warning("Chat history: PostgreSQL unavailable (%s) — using memory", exc)
            print(f"   ⚠ Chat history: PostgreSQL unavailable — using in-memory history")
            self._engine = None
            self._table = None
            self._backend = "memory"
        return self._backend

    def backend_name(self) -> str:
        return self._backend

    def store_turn(self, session_id: str, query: str, summary: str) -> None:
        """Persist one turn (always cached in memory; PG best-effort)."""
        entry = {
            "query": query,
            "response_summary": summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        turns = self._memory.setdefault(session_id, [])
        turns.append(entry)
        del turns[:-MAX_TURNS_PER_SESSION]

        if self._engine is not None and self._table is not None:
            try:
                with self._engine.begin() as conn:
                    conn.execute(self._table.insert().values(
                        session_id=session_id,
                        query=query,
                        response_summary=summary,
                        created_at=datetime.now(timezone.utc),
                    ))
            except Exception as exc:
                logger.warning("Chat history: failed to persist turn (%s)", exc)

    def get_turns(self, session_id: str) -> list[dict]:
        """Stored turns oldest-first (max 50). PG first, memory fallback."""
        if self._engine is not None and self._table is not None:
            try:
                with self._engine.connect() as conn:
                    rows = conn.execute(
                        self._table.select()
                        .where(self._table.c.session_id == session_id)
                        .order_by(desc(self._table.c.id))
                        .limit(MAX_TURNS_PER_SESSION)
                    ).fetchall()
                turns = [
                    {
                        "query": r.query,
                        "response_summary": r.response_summary,
                        "timestamp": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in rows
                ]
                turns.reverse()
                return turns
            except Exception as exc:
                logger.warning("Chat history: failed to read turns (%s)", exc)
        return list(self._memory.get(session_id, []))

    def reset_state(self) -> None:
        """Clear memory cache (used by tests)."""
        self._memory.clear()

    def close(self) -> None:
        """Dispose pooled connections (shutdown/tests)."""
        try:
            if self._engine is not None:
                self._engine.dispose()
        except Exception as exc:
            logger.warning("Chat history: failed to dispose engine (%s)", exc)
        finally:
            self._engine = None
            self._table = None


history_service = HistoryService()
