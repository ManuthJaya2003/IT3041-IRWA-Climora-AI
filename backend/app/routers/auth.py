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
