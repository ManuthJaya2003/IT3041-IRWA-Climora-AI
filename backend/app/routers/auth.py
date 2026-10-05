"""User account endpoints: register, login, Google Sign-In, profile."""

from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.services import auth_service
from app.services import plans_service
from app.services import usage_service

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleRequest(BaseModel):
    id_token: str


def _token_response(user: dict) -> dict:
    token = auth_service.create_access_token(user["id"])
    state = usage_service.get_usage(f"user:{user['id']}", user.get("plan_id", "free"))
    return {"access_token": token, "token_type": "bearer", "user": auth_service._public_user(user), "usage": state}


@router.post("/register")
async def register(body: RegisterRequest):
    try:
        user = auth_service.create_user(body.email, body.name, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _token_response(user)


@router.post("/login")
async def login(body: LoginRequest):
    try:
        user = auth_service.authenticate(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return _token_response(user)


@router.post("/google")
async def google_sign_in(body: GoogleRequest):
    try:
        info = await auth_service.verify_google_id_token(body.id_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    user = auth_service.get_or_create_google_user(info["email"], info["name"])
    return _token_response(user)


async def _require_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.")
    user_id = auth_service.decode_user_id(auth[7:].strip())
    user = auth_service.get_user_by_id(user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired — please sign in again.")
    return user

RequireUser = Depends(_require_user)


@router.get("/me")
async def me(user: dict = RequireUser):
    plan = plans_service.get_plan(user.get("plan_id"))
    state = usage_service.get_usage(f"user:{user['id']}", plan["id"])
    return {"user": auth_service._public_user(user), "usage": state}


@router.get("/config")
async def auth_config():
    from app.config import settings

    return {"google_client_id": settings.google_client_id, "google_enabled": bool(settings.google_client_id)}


class SsoConsumeRequest(BaseModel):
    code: str


@router.get("/sso/start")
async def sso_start(org: str):
    """Begin enterprise SSO: returns the IdP authorization URL (PKCE, state-bound)."""
    from app.config import settings
    from app.services import oidc_service, org_service

    entry = org_service.get_org_by_slug(org)
    if entry is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    if not entry.get("sso_configured"):
        raise HTTPException(status_code=400, detail="SSO is not configured for this organization.")
    try:
        doc = await oidc_service.discover(entry["sso_issuer"])
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Identity provider unreachable: {exc}")
    verifier, challenge = oidc_service.pkce_pair()
    state = org_service.create_sso_state(entry["id"], verifier)
    url = oidc_service.build_start_url(
        authorization_endpoint=doc["authorization_endpoint"],
        client_id=entry["sso_client_id"],
        redirect_uri=oidc_service.callback_url(settings.public_origin),
        state=state,
        challenge=challenge,
    )
    return {"authorization_url": url, "org": org_service._public_org(entry)}


@router.get("/sso/callback")
async def sso_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """IdP redirect target: validates state, logs the user in, hands a
    one-time code to the frontend (never puts tokens in the URL)."""
    from fastapi.responses import RedirectResponse
    from app.config import settings
    from app.services import oidc_service, org_service

    frontend = settings.frontend_origin.rstrip("/")
    if error:
        return RedirectResponse(f"{frontend}/?sso_error={error}", status_code=302)
    saved = org_service.pop_sso_state(state) if state else None
    if not saved:
        return RedirectResponse(f"{frontend}/?sso_error=invalid_state", status_code=302)
    org = org_service.get_org(saved["org_id"])
    if org is None or not code:
        return RedirectResponse(f"{frontend}/?sso_error=login_failed", status_code=302)
    try:
        doc = await oidc_service.discover(org["sso_issuer"])
        tokens = await oidc_service.exchange_code(
            token_endpoint=doc["token_endpoint"],
            code=code,
            redirect_uri=oidc_service.callback_url(settings.public_origin),
            client_id=org["sso_client_id"],
            verifier=saved["verifier"],
            client_secret=org_service._secret(org["id"]),
        )
        info = await oidc_service.verify_id_token_remote(
            tokens["id_token"], issuer=org["sso_issuer"], audience=org["sso_client_id"],
        )
    except ValueError as exc:
        return RedirectResponse(f"{frontend}/?sso_error={type(exc).__name__}", status_code=302)
    except Exception:
        return RedirectResponse(f"{frontend}/?sso_error=provider_error", status_code=302)
    domain = (org.get("domain") or "").lower()
    if domain and not info["email"].endswith("@" + domain):
        org_service.audit(org["id"], info["email"], "sso.rejected", "email domain not allowed")
        return RedirectResponse(f"{frontend}/?sso_error=domain_not_allowed", status_code=302)
    user = auth_service.get_user_by_email(info["email"])
    if user is None:
        user = auth_service.create_user(info["email"], info["name"], None, provider="sso")
    if org_service.get_role(org["id"], user["id"]) is None:
        org_service.add_member(org["id"], user["id"], "member")
        org_service.audit(org["id"], info["email"], "sso.login", "provisioned via SSO")
    else:
        org_service.audit(org["id"], info["email"], "sso.login", "")
    once = org_service.create_sso_code(user["id"], org["id"])
    return RedirectResponse(f"{frontend}/?sso_code={once}", status_code=302)


@router.post("/sso/consume")
async def sso_consume(body: SsoConsumeRequest):
    """Exchange a one-time SSO code for a session JWT."""
    from app.services import org_service

    saved = org_service.pop_sso_code(body.code)
    if not saved:
        raise HTTPException(status_code=400, detail="Invalid or expired SSO code.")
    user = auth_service.get_user_by_id(saved["user_id"])
    if user is None:
        raise HTTPException(status_code=400, detail="Account no longer exists.")
    return _token_response(user)
