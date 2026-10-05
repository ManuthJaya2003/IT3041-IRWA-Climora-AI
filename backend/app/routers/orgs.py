"""Enterprise organizations: create, members, SSO config, audit log."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.routers.deps import get_current_user_optional
from app.services import auth_service, org_service

router = APIRouter()


def _me(request: Request) -> dict:
    user = get_current_user_optional(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return user


def _org_or_404(org_id: str) -> dict:
    org = org_service.get_org(org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return org


def _require_role(org_id: str, user_id: str, *roles: str) -> str:
    role = org_service.get_role(org_id, user_id)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization.")
    if roles and role not in roles:
        raise HTTPException(
            status_code=403,
            detail=f"Requires role: {' or '.join(roles)} (you are {role}).",
        )
    return role


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=3, max_length=50)
    domain: str = Field(default="", max_length=255)


class InviteRequest(BaseModel):
    email: str
    role: str = Field(default="member", pattern="^(member|admin|owner)$")


class SsoConfigRequest(BaseModel):
    issuer: str = Field(min_length=len("https://x"), max_length=512)
    client_id: str = Field(min_length=1, max_length=255)
    client_secret: str = Field(default="", max_length=2000)


@router.post("")
async def create_org(body: CreateOrgRequest, request: Request):
    user = _me(request)
    try:
        org = org_service.create_org(body.name, body.slug, user["id"], body.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"org": org_service._public_org(org, "owner")}


@router.get("/mine")
async def my_orgs(request: Request):
    user = _me(request)
    return {"orgs": org_service.orgs_for_user(user["id"])}


@router.get("/{org_id}")
async def get_org(org_id: str, request: Request):
    user = _me(request)
    org = _org_or_404(org_id)
    role = _require_role(org_id, user["id"])
    return {"org": org_service._public_org(org, role)}


@router.get("/{org_id}/members")
async def list_members(org_id: str, request: Request):
    user = _me(request)
    _org_or_404(org_id)
    _require_role(org_id, user["id"])
    return {"members": org_service.members_of(org_id)}


@router.post("/{org_id}/invite")
async def invite_member(org_id: str, body: InviteRequest, request: Request):
    user = _me(request)
    _org_or_404(org_id)
    _require_role(org_id, user["id"], "owner", "admin")
    try:
        member = org_service.add_member_by_email(org_id, body.email, user["email"], body.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"member": member}


@router.post("/{org_id}/sso")
async def configure_sso(org_id: str, body: SsoConfigRequest, request: Request):
    """Connect the org's identity provider (Okta, Entra ID, Auth0, Google...)."""
    user = _me(request)
    _org_or_404(org_id)
    _require_role(org_id, user["id"], "owner")
    try:
        org = org_service.configure_sso(org_id, body.issuer, body.client_id, body.client_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    org_service.audit(org_id, user["email"], "sso.configured", f"issuer={org['sso_issuer']}")
    return {"org": org_service._public_org(org, "owner")}


@router.get("/{org_id}/audit")
async def get_audit(org_id: str, request: Request, limit: int = 100):
    user = _me(request)
    _org_or_404(org_id)
    _require_role(org_id, user["id"], "owner", "admin")
    return {"events": org_service.audit_log(org_id, limit)}
