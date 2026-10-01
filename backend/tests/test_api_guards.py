"""API guard tests: admin auth, rate limiting, shared session history.

Run with:  python -m pytest tests/test_api_guards.py
(or directly:  python tests/test_api_guards.py)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import deps as deps_module  # noqa: E402
from app.agents.orchestrator.shared import get_orchestrator  # noqa: E402


def _client():
    # NOTE: instantiated without a context manager so the lifespan
    # (agent subprocesses) is NOT started — these tests cover the
    # HTTP guards, not the agent pipeline.
    return TestClient(app, raise_server_exceptions=False)


def test_history_empty_for_unknown_session():
    client = _client()
    resp = client.get("/api/v1/chat/history?session_id=no-such-session")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == "no-such-session"
    assert body["messages"] == []


def test_history_requires_session_id_param():
    client = _client()
    resp = client.get("/api/v1/chat/history")
    assert resp.status_code == 200, resp.text
    assert resp.json()["messages"] == []


def test_shared_orchestrator_singleton():
    assert get_orchestrator() is get_orchestrator()


def test_session_history_round_trip():
    from app.services.history_service import history_service
    orch = get_orchestrator()
    orch._store_session("test-sess", "flood in Kandy?", type("R", (), {"summary": "ok"})())
    try:
        client = _client()
        resp = client.get("/api/v1/chat/history?session_id=test-sess")
        assert resp.status_code == 200, resp.text
        messages = resp.json()["messages"]
        assert messages and messages[-1]["query"] == "flood in Kandy?"
    finally:
        history_service.reset_state()


def test_admin_guard_blocks_mutation_with_wrong_token():
    old = settings.admin_token
    settings.admin_token = "test-secret"
    try:
        client = _client()
        resp = client.post("/api/v1/vectors/seed")
        assert resp.status_code == 401, resp.text
        resp = client.post("/api/v1/vectors/seed", headers={"X-Admin-Token": "wrong"})
        assert resp.status_code == 401, resp.text
    finally:
        settings.admin_token = old


def test_admin_guard_allows_reads_without_token():
    old = settings.admin_token
    settings.admin_token = "test-secret"
    try:
        client = _client()
        # Read-only routes stay public even when a token is configured.
        resp = client.get("/api/v1/vectors/stats")
        assert resp.status_code in (200, 503), resp.text
    finally:
        settings.admin_token = old


def test_rate_limit_returns_429():
    old_limit, old_window = settings.rate_limit_requests, settings.rate_limit_window_seconds
    settings.rate_limit_requests, settings.rate_limit_window_seconds = 2, 60
    deps_module.reset_rate_limit_state()
    try:
        client = _client()
        payload = {"query": "hello there"}
        assert client.post("/api/v1/chat/query", json=payload).status_code == 200
        assert client.post("/api/v1/chat/query", json=payload).status_code == 200
        resp = client.post("/api/v1/chat/query", json=payload)
        assert resp.status_code == 429, resp.text
    finally:
        settings.rate_limit_requests, settings.rate_limit_window_seconds = old_limit, old_window
        deps_module.reset_rate_limit_state()


if __name__ == "__main__":
    tests = [
        test_history_empty_for_unknown_session,
        test_history_requires_session_id_param,
        test_shared_orchestrator_singleton,
        test_session_history_round_trip,
        test_admin_guard_blocks_mutation_with_wrong_token,
        test_admin_guard_allows_reads_without_token,
        test_rate_limit_returns_429,
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
