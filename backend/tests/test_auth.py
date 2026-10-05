"""Auth tests: register/login, server-side plans, spoof resistance.

Run with:  venv\\Scripts\\python -m pytest tests/test_auth.py -q
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import auth_service  # noqa: E402


def _client():
    return TestClient(app, raise_server_exceptions=False)


def test_register_login_and_me():
    auth_service.reset_state()
    client = _client()
    email = "auth_test@climora.ai"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "name": "Auth"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    assert r.json()["user"]["plan_id"] == "free"

    # Duplicate email rejected.
    dup = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "name": "Auth"})
    assert dup.status_code == 400

    # Wrong password rejected.
    bad = client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpass1"})
    assert bad.status_code == 401

    good = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert good.status_code == 200, good.text

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["user"]["email"] == email


def test_subscribe_requires_auth_and_spoof_blocked():
    auth_service.reset_state()
    client = _client()
    # Anonymous subscribe rejected.
    anon = client.post("/api/v1/billing/subscribe", json={"plan_id": "premium", "billing_cycle": "monthly"})
    assert anon.status_code == 401, anon.text

    r = client.post("/api/v1/auth/register", json={"email": "sub@climora.ai", "password": "password123", "name": "Sub"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    sub = client.post("/api/v1/billing/subscribe", json={"plan_id": "premium", "billing_cycle": "monthly"}, headers=headers)
    assert sub.status_code == 200, sub.text
    assert sub.json()["user"]["plan_id"] == "premium"

    # X-Plan: enterprise cannot escalate a premium account.
    usage = client.get("/api/v1/billing/usage", headers={**headers, "X-Plan": "enterprise"})
    assert usage.status_code == 200, usage.text
    assert usage.json()["plan"] == "premium"

    # Enterprise still goes via sales.
    ent = client.post("/api/v1/billing/subscribe", json={"plan_id": "enterprise", "billing_cycle": "monthly"}, headers=headers)
    assert ent.status_code == 400


if __name__ == "__main__":
    for fn in [test_register_login_and_me, test_subscribe_requires_auth_and_spoof_blocked]:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {fn.__name__}: {exc!r}")
            sys.exit(1)
