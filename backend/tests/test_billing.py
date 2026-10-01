"""Billing tests: plans catalogue, per-plan quotas, usage endpoint.

Run with:  python -m pytest tests/test_billing.py
(or directly:  python tests/test_billing.py)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import plans_service  # noqa: E402
from app.services import usage_service  # noqa: E402
from app.routers import deps as deps_module  # noqa: E402


def _client():
    # No context manager → lifespan (agent subprocesses) is NOT started.
    return TestClient(app, raise_server_exceptions=False)


def test_plans_endpoint_lists_four_tiers():
    resp = _client().get("/api/v1/billing/plans")
    assert resp.status_code == 200, resp.text
    plans = resp.json()["plans"]
    assert [p["id"] for p in plans] == ["free", "premium", "business", "enterprise"]
    for plan in plans:
        assert plan["features"], plan["id"]
        assert "queries_per_day" in plan


def test_unknown_plan_falls_back_to_free():
    assert plans_service.get_plan("platinum")["id"] == "free"
    assert plans_service.get_plan(None)["id"] == "free"


def test_quota_exhaustion_returns_429_with_upgrade_hint():
    old = plans_service.PLANS["free"]["queries_per_day"]
    plans_service.PLANS["free"]["queries_per_day"] = 1
    usage_service.reset_usage_state()
    deps_module.reset_rate_limit_state()
    try:
        client = _client()
        first = client.post("/api/v1/chat/query", json={"query": "hello"})
        assert first.status_code == 200, first.text
        second = client.post("/api/v1/chat/query", json={"query": "hello"})
        assert second.status_code == 429, second.text
        assert "quota" in second.json()["detail"].lower()
    finally:
        plans_service.PLANS["free"]["queries_per_day"] = old
        usage_service.reset_usage_state()
        deps_module.reset_rate_limit_state()


def test_usage_endpoint_reports_quota_state():
    usage_service.reset_usage_state()
    try:
        client = _client()
        resp = client.get("/api/v1/billing/usage")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["plan"] == "free"
        assert body["used_today"] == 0
        assert body["remaining_today"] == body["daily_limit"] > 0
    finally:
        usage_service.reset_usage_state()


def test_usage_consumes_after_query():
    usage_service.reset_usage_state()
    deps_module.reset_rate_limit_state()
    try:
        client = _client()
        client.post("/api/v1/chat/query", json={"query": "hello"})
        body = client.get("/api/v1/billing/usage").json()
        assert body["used_today"] == 1
    finally:
        usage_service.reset_usage_state()
        deps_module.reset_rate_limit_state()


if __name__ == "__main__":
    tests = [
        test_plans_endpoint_lists_four_tiers,
        test_unknown_plan_falls_back_to_free,
        test_quota_exhaustion_returns_429_with_upgrade_hint,
        test_usage_endpoint_reports_quota_state,
        test_usage_consumes_after_query,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
