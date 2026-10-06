"""Stripe payment tests: config gating, checkout flow, webhook (all offline).

Stripe HTTP is faked; webhook signatures use real HMAC. Run with:
venv\\Scripts\\python -m pytest tests/test_stripe.py -q
"""

import hashlib
import hmac
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import auth_service  # noqa: E402
from app.services import org_service  # noqa: E402


def _client():
    return TestClient(app, raise_server_exceptions=False)


class _Resp:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class _FakeSessions:
    """Fake httpx.AsyncClient serving scripted Stripe responses."""
    posted = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, data=None, auth=None):
        type(self).posted = dict(data or {})
        return _Resp(200, {"id": "cs_test_123", "url": "https://checkout.stripe.com/pay/cs_test_123"})

    async def get(self, url, auth=None):
        return _Resp(200, dict(type(self).session_json))


def _register(client, email: str) -> dict:
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "name": "T",
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_payment_config_and_demo_gating(monkeypatch):
    auth_service.reset_state()
    org_service.reset_state()
    client = _client()
    monkeypatch.setattr(settings, "stripe_secret_key", None)
    assert client.get("/api/v1/billing/payment-config").json() == {"stripe_enabled": False}
    user = _register(client, "demo@pay.example")
    H = {"Authorization": f"Bearer {user['access_token']}"}
    # No keys → checkout creation refused, demo subscribe works.
    assert client.post("/api/v1/billing/checkout-session", json={
        "plan_id": "premium", "annual": False,
        "success_url": "http://localhost:5173/?checkout=success", "cancel_url": "http://localhost:5173/",
    }, headers=H).status_code == 503
    ok = client.post("/api/v1/billing/subscribe",
                     json={"plan_id": "premium", "billing_cycle": "monthly"}, headers=H)
    assert ok.status_code == 200, ok.text

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    assert client.get("/api/v1/billing/payment-config").json() == {"stripe_enabled": True}
    # Keys present → paid demo subscribe refused, real checkout required.
    forced = client.post("/api/v1/billing/subscribe",
                         json={"plan_id": "premium", "billing_cycle": "monthly"}, headers=H)
    assert forced.status_code == 400, forced.text
    free = client.post("/api/v1/billing/subscribe",
                       json={"plan_id": "free", "billing_cycle": "monthly"}, headers=H)
    assert free.status_code == 200, free.text


def test_checkout_create_and_verify(monkeypatch):
    import httpx
    auth_service.reset_state()
    org_service.reset_state()
    client = _client()
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(httpx, "AsyncClient", _FakeSessions)
    user = _register(client, "buyer@pay.example")
    H = {"Authorization": f"Bearer {user['access_token']}"}

    created = client.post("/api/v1/billing/checkout-session", json={
        "plan_id": "premium", "annual": True,
        "success_url": "http://localhost:5173/?checkout=success", "cancel_url": "http://localhost:5173/",
    }, headers=H)
    assert created.status_code == 200, created.text
    assert created.json()["checkout_url"].startswith("https://checkout.stripe.com")
    # Session is bound to the account, amounts in LKR cents, yearly interval.
    assert _FakeSessions.posted["client_reference_id"] == user["user"]["id"]
    assert _FakeSessions.posted["line_items[0][price_data][unit_amount]"] == str(14900 * 100)
    assert _FakeSessions.posted["line_items[0][price_data][recurring][interval]"] == "year"

    _FakeSessions.session_json = {
        "id": "cs_test_123", "status": "complete", "payment_status": "paid",
        "client_reference_id": user["user"]["id"],
        "metadata": {"plan_id": "premium", "billing_cycle": "annual"},
    }
    verified = client.get("/api/v1/billing/checkout-session/cs_test_123", headers=H)
    assert verified.status_code == 200, verified.text
    assert verified.json()["plan_id"] == "premium"
    me = client.get("/api/v1/auth/me", headers=H).json()
    assert me["user"]["plan_id"] == "premium"

    # Another account cannot claim the session.
    other = _register(client, "thief@pay.example")
    OH = {"Authorization": f"Bearer {other['access_token']}"}
    stolen = client.get("/api/v1/billing/checkout-session/cs_test_123", headers=OH)
    assert stolen.status_code == 403, stolen.text

    # Unpaid session → 409, no activation.
    _FakeSessions.session_json = dict(_FakeSessions.session_json, status="open", payment_status="unpaid")
    pending = client.get("/api/v1/billing/checkout-session/cs_test_123", headers=H)
    assert pending.status_code == 409, pending.text


def _sign(secret: str, payload: bytes) -> str:
    t = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"


def test_webhook_activates_plan():
    auth_service.reset_state()
    org_service.reset_state()
    client = _client()
    old_secret, old_key = settings.stripe_webhook_secret, settings.stripe_secret_key
    settings.stripe_webhook_secret = "whsec_test"
    settings.stripe_secret_key = "sk_test_fake"
    try:
        user = _register(client, "hook@pay.example")
        event = {"type": "checkout.session.completed", "data": {"object": {
            "id": "cs_test_9", "client_reference_id": user["user"]["id"],
            "metadata": {"plan_id": "business", "billing_cycle": "monthly"},
        }}}
        raw = json.dumps(event).encode()
        r = client.post("/api/v1/billing/webhook", content=raw, headers={
            "Content-Type": "application/json",
            "Stripe-Signature": _sign("whsec_test", raw),
        })
        assert r.status_code == 200, r.text
        me = client.get("/api/v1/auth/me",
                        headers={"Authorization": f"Bearer {user['access_token']}"}).json()
        assert me["user"]["plan_id"] == "business", me

        bad = client.post("/api/v1/billing/webhook", content=raw, headers={
            "Content-Type": "application/json", "Stripe-Signature": "t=1,v1=deadbeef",
        })
        assert bad.status_code == 400, bad.text
    finally:
        settings.stripe_webhook_secret = old_secret
        settings.stripe_secret_key = old_key


if __name__ == "__main__":
    tests = [test_payment_config_and_demo_gating, test_checkout_create_and_verify,
             test_webhook_activates_plan]
    failed = 0
    for fn in tests:
        try:
            import inspect
            if "monkeypatch" in inspect.signature(fn).parameters:
                print(f"SKIP {fn.__name__} (needs pytest monkeypatch)")
                continue
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
