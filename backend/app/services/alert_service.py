"""Persistent Web Push subscriptions and deduplicated alert delivery."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from pywebpush import webpush, WebPushException
except ImportError:  # pragma: no cover - optional during minimal local setup
    webpush = None
    WebPushException = Exception

try:
    from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, select
except ImportError:  # pragma: no cover
    Column = DateTime = Integer = MetaData = String = Table = Text = create_engine = select = None


class AlertService:
    def __init__(self):
        self._engine = None
        self._subscriptions = None
        self._alerts = None
        self._memory_subscriptions: dict[str, dict] = {}

    async def initialize(self, database_url: Optional[str] = None) -> None:
        url = database_url if database_url is not None else settings.database_url
        if not url or create_engine is None:
            return
        try:
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            self._engine = create_engine(url, pool_pre_ping=True)
            metadata = MetaData()
            self._subscriptions = Table(
                "push_subscriptions", metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("subscription_key", String(128), unique=True, nullable=False),
                Column("endpoint", Text, nullable=False),
                Column("subscription_json", Text, nullable=False),
                Column("location", String(120), nullable=False),
                Column("created_at", DateTime(timezone=True), nullable=False),
            )
            self._alerts = Table(
                "weather_alerts", metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("dedupe_key", String(128), unique=True, nullable=False),
                Column("location", String(120), nullable=False),
                Column("title", String(255), nullable=False),
                Column("body", Text, nullable=False),
                Column("created_at", DateTime(timezone=True), nullable=False),
            )
            metadata.create_all(self._engine)
        except Exception:
            logger.exception("Web Push database initialization failed")
            self._engine = None

    @staticmethod
    def key(subscription: dict) -> str:
        return hashlib.sha256(subscription["endpoint"].encode("utf-8")).hexdigest()

    def save_subscription(self, subscription: dict, location: str) -> None:
        key = self.key(subscription)
        self._memory_subscriptions[key] = {"subscription": subscription, "location": location}
        if self._engine is None or self._subscriptions is None:
            return
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(self._subscriptions.c.id).where(self._subscriptions.c.subscription_key == key)
            ).first()
            values = {
                "subscription_key": key,
                "endpoint": subscription["endpoint"],
                "subscription_json": json.dumps(subscription),
                "location": location,
                "created_at": datetime.now(timezone.utc),
            }
            if existing:
                conn.execute(self._subscriptions.update().where(self._subscriptions.c.id == existing.id).values(**values))
            else:
                conn.execute(self._subscriptions.insert().values(**values))

    def remove_subscription(self, subscription: dict) -> None:
        key = self.key(subscription)
        self._memory_subscriptions.pop(key, None)
        if self._engine is not None and self._subscriptions is not None:
            with self._engine.begin() as conn:
                conn.execute(self._subscriptions.delete().where(self._subscriptions.c.subscription_key == key))

    def _subscriptions_list(self) -> list[dict]:
        if self._engine is None or self._subscriptions is None:
            return list(self._memory_subscriptions.values())
        with self._engine.connect() as conn:
            rows = conn.execute(self._subscriptions.select()).fetchall()
        return [{"subscription": json.loads(row.subscription_json), "location": row.location} for row in rows]

    def send_test(self, subscription: dict) -> None:
        if webpush is None or not settings.vapid_private_key:
            raise RuntimeError("Web Push is not configured. Set VAPID_PRIVATE_KEY first.")
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": "Climora AI test alert", "body": "Web Push alerts are working."}),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )

    def send_to_all(self, title: str, body: str) -> int:
        sent = 0
        for item in self._subscriptions_list():
            try:
                if webpush is None or not settings.vapid_private_key:
                    break
                webpush(
                    subscription_info=item["subscription"],
                    data=json.dumps({"title": title, "body": body}),
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject},
                )
                sent += 1
            except WebPushException as exc:
                logger.warning("Web Push delivery failed: %s", exc)
                response = getattr(exc, "response", None)
                if response is not None and getattr(response, "status_code", None) in (404, 410):
                    self.remove_subscription(item["subscription"])
        return sent

    def subscription_count(self) -> int:
        return len(self._subscriptions_list())

    def _already_sent(self, dedupe_key: str) -> bool:
        if self._engine is None or self._alerts is None:
            return False
        with self._engine.connect() as conn:
            return conn.execute(
                select(self._alerts.c.id).where(self._alerts.c.dedupe_key == dedupe_key)
            ).first() is not None

    def _record_alert(self, dedupe_key: str, location: str, title: str, body: str) -> None:
        if self._engine is not None and self._alerts is not None:
            with self._engine.begin() as conn:
                conn.execute(self._alerts.insert().values(
                    dedupe_key=dedupe_key,
                    location=location,
                    title=title,
                    body=body,
                    created_at=datetime.now(timezone.utc),
                ))

    async def monitor_once(self) -> int:
        """Check subscribed locations and send deduplicated severe-weather alerts."""
        sent = 0
        for item in self._subscriptions_list():
            location = item["location"]
            if not location:
                continue
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    geo = await client.get(
                        "https://geocoding-api.open-meteo.com/v1/search",
                        params={"name": location, "count": 1, "language": "en", "format": "json"},
                    )
                    result = geo.json().get("results", [])
                    if not result:
                        continue
                    place = result[0]
                    weather = await client.get(
                        "https://api.open-meteo.com/v1/forecast",
                        params={
                            "latitude": place["latitude"],
                            "longitude": place["longitude"],
                            "current": "temperature_2m,wind_speed_10m",
                            "hourly": "precipitation_probability",
                            "forecast_days": 1,
                        },
                    )
                data = weather.json()
                current = data.get("current", {})
                probability = max(data.get("hourly", {}).get("precipitation_probability", [0])[:6] or [0])
                wind = float(current.get("wind_speed_10m", 0))
                temperature = float(current.get("temperature_2m", 0))
                condition = "rain" if probability >= 80 else "wind" if wind >= 60 else "heat" if temperature >= 38 else ""
                if not condition:
                    continue
                day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                dedupe_key = hashlib.sha256(f"{location.lower()}:{day}:{condition}".encode()).hexdigest()
                if self._already_sent(dedupe_key):
                    continue
                title = f"Climora AI - severe {condition} risk"
                body = f"{location}: {condition} conditions may require preparation. Check official local guidance."
                if webpush is not None and settings.vapid_private_key:
                    webpush(
                        subscription_info=item["subscription"],
                        data=json.dumps({"title": title, "body": body}),
                        vapid_private_key=settings.vapid_private_key,
                        vapid_claims={"sub": settings.vapid_subject},
                    )
                    self._record_alert(dedupe_key, location, title, body)
                    sent += 1
            except Exception as exc:
                logger.warning("Weather alert check failed for %s: %s", location, exc)
        return sent


alert_service = AlertService()
