"""Enterprise organizations: membership, per-org SSO config, audit log.

Model (PostgreSQL, memory fallback for dev — same pattern as auth_service):

- org: id, slug (unique, URL-safe), name, domain (email domain auto-provision),
  plan_id ("enterprise"), SSO fields (issuer, client_id, client_secret or None
  with PKCE), billing state (status trial/active, trial_ends_at, activated_at,
  billing_cycle, receipt), created_at.
- membership: org_id + user_id (+ role owner/admin/member).
- audit: org-scoped event log (actor, action, detail, timestamp).

Client secrets are stored reversibly because the token exchange needs them;
a production deployment should move them to a secret manager.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import (
        Column, DateTime, MetaData, String, Table, Text,
        create_engine, select,
    )
    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    Column = DateTime = MetaData = String = Table = Text = create_engine = select = None
    _SQLALCHEMY_AVAILABLE = False

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_engine = None
_orgs = None
_members = None
_audit = None

# Memory fallback.
_orgs_mem: dict[str, dict] = {}          # id -> org
_slugs_mem: dict[str, str] = {}          # slug -> id
_members_mem: dict[tuple[str, str], str] = {}  # (org_id, user_id) -> role
_audit_mem: list[dict] = []

# Short-lived SSO login states and one-time codes (memory only by design).
_sso_states: dict[str, dict] = {}  # state -> {org_id, verifier, exp}
_sso_codes: dict[str, dict] = {}   # code -> {user_id, org_id, exp}
SSO_STATE_TTL = 600
SSO_CODE_TTL = 600


TRIAL_DAYS = 14


def _utcnow():
    return datetime.now(timezone.utc)


def _trial_ends_at() -> str:
    return (_utcnow() + timedelta(days=TRIAL_DAYS)).isoformat()


async def initialize(database_url: str | None = None) -> str:
    global _engine, _orgs, _members, _audit
    url = database_url if database_url is not None else settings.database_url
    if not url or not _SQLALCHEMY_AVAILABLE:
        return "memory"
    try:
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        is_pg = "postgresql" in url
        kwargs: dict = {"pool_pre_ping": True}
        if is_pg:
            kwargs.update(pool_size=2, max_overflow=2, connect_args={"connect_timeout": 3})
        engine = create_engine(url, **kwargs)
        metadata = MetaData()
        orgs = Table(
            "orgs", metadata,
            Column("id", String(64), primary_key=True),
            Column("slug", String(64), unique=True, nullable=False, index=True),
            Column("name", String(120), nullable=False),
            Column("domain", String(255), nullable=True),
            Column("plan_id", String(32), nullable=False, default="enterprise"),
            Column("sso_issuer", String(512), nullable=True),
            Column("sso_client_id", String(255), nullable=True),
            Column("sso_client_secret", Text, nullable=True),
            Column("status", String(16), nullable=False, default="trial"),
            Column("trial_ends_at", DateTime(timezone=True), nullable=True),
            Column("activated_at", DateTime(timezone=True), nullable=True),
            Column("billing_cycle", String(16), nullable=False, default="annual"),
            Column("receipt", String(64), nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        members = Table(
            "memberships", metadata,
            Column("org_id", String(64), nullable=False, index=True),
            Column("user_id", String(64), nullable=False, index=True),
            Column("role", String(16), nullable=False, default="member"),
        )
        audit = Table(
            "org_audit", metadata,
            Column("id", String(64), primary_key=True),
            Column("org_id", String(64), nullable=False, index=True),
            Column("actor", String(320), nullable=False),
            Column("action", String(64), nullable=False),
            Column("detail", Text, nullable=False, default=""),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(orgs.select().limit(1))
        _engine, _orgs, _members, _audit = engine, orgs, members, audit
        return "postgresql" if is_pg else "sqlite"
    except Exception:
        logger.exception("Orgs persistence unavailable; using memory")
        _engine = _orgs = _members = _audit = None
        return "memory"


def validate_slug(slug: str) -> str:
    clean = slug.strip().lower()
    if not _SLUG_RE.match(clean):
        raise ValueError("Slug must be 3-50 lowercase letters, numbers or dashes.")
    return clean


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def org_status(org: dict) -> str:
    """Effective billing status: active > trial (unexpired) > expired."""
    if org.get("activated_at"):
        return "active"
    trial_end = _parse_dt(org.get("trial_ends_at"))
    if trial_end is not None and trial_end > _utcnow():
        return "trial"
    return "expired"


def _row_org(row) -> dict:
    org = {
        "id": row.id, "slug": row.slug, "name": row.name,
        "domain": row.domain or "", "plan_id": row.plan_id or "enterprise",
        "sso_issuer": row.sso_issuer or "", "sso_client_id": row.sso_client_id or "",
        "sso_configured": bool(row.sso_issuer and row.sso_client_id),
        "trial_ends_at": row.trial_ends_at.isoformat() if getattr(row, "trial_ends_at", None) else "",
        "activated_at": row.activated_at.isoformat() if getattr(row, "activated_at", None) else "",
        "billing_cycle": getattr(row, "billing_cycle", None) or "annual",
        "receipt": getattr(row, "receipt", None) or "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }
    org["status"] = org_status(org)
    return org


def _public_org(org: dict, role: str | None = None) -> dict:
    # Never expose the client secret.
    pub = {
        "id": org["id"], "slug": org["slug"], "name": org["name"],
        "domain": org.get("domain", ""), "plan_id": org.get("plan_id", "enterprise"),
        "sso_issuer": org.get("sso_issuer", ""),
        "sso_client_id": org.get("sso_client_id", ""),
        "sso_configured": bool(org.get("sso_issuer") and org.get("sso_client_id")),
        "trial_ends_at": org.get("trial_ends_at", ""),
        "activated_at": org.get("activated_at", ""),
        "billing_cycle": org.get("billing_cycle", "annual"),
        "receipt": org.get("receipt", ""),
        "role": role,
        "created_at": org.get("created_at", ""),
    }
    pub["status"] = org_status(org)
    return pub


def _with_flag(org: dict | None) -> dict | None:
    if org is not None:
        org["sso_configured"] = bool(org.get("sso_issuer") and org.get("sso_client_id"))
    return org


def get_org(org_id: str) -> dict | None:
    if _engine is not None and _orgs is not None:
        try:
            with _engine.connect() as conn:
                row = conn.execute(select(_orgs).where(_orgs.c.id == org_id)).first()
            return _with_flag(_row_org(row) if row else None)
        except Exception:
            logger.exception("Failed to read org")
    return _with_flag(_orgs_mem.get(org_id))


def get_org_by_slug(slug: str) -> dict | None:
    clean = slug.strip().lower()
    if _engine is not None and _orgs is not None:
        try:
            with _engine.connect() as conn:
                row = conn.execute(select(_orgs).where(_orgs.c.slug == clean)).first()
            return _with_flag(_row_org(row) if row else None)
        except Exception:
            logger.exception("Failed to read org by slug")
    org_id = _slugs_mem.get(clean)
    return _with_flag(_orgs_mem.get(org_id) if org_id else None)


def _secret(org_id: str) -> str | None:
    """Client secret (server-side only, never serialized)."""
    org = get_org(org_id)
    if org is None:
        return None
    if _engine is not None and _orgs is not None:
        try:
            with _engine.connect() as conn:
                row = conn.execute(
                    select(_orgs.c.sso_client_secret).where(_orgs.c.id == org_id)
                ).first()
            return row.sso_client_secret if row else None
        except Exception:
            logger.exception("Failed to read org secret")
            return None
    full = _orgs_mem.get(org_id, {})
    return full.get("sso_client_secret")


def create_org(name: str, slug: str, owner_id: str, domain: str = "") -> dict:
    from app.services import auth_service
    clean_slug = validate_slug(slug)
    clean_name = (name or "").strip()[:120] or clean_slug
    if get_org_by_slug(clean_slug) is not None:
        raise ValueError("An organization with this slug already exists.")
    clean_domain = domain.strip().lower()
    if clean_domain and "." not in clean_domain:
        raise ValueError("Domain must look like company.example.")
    org = {
        "id": uuid.uuid4().hex[:16],
        "slug": clean_slug,
        "name": clean_name,
        "domain": clean_domain,
        "plan_id": "enterprise",
        "sso_issuer": "",
        "sso_client_id": "",
        "sso_client_secret": None,
        "status": "trial",
        "trial_ends_at": _trial_ends_at(),
        "activated_at": "",
        "billing_cycle": "annual",
        "receipt": "",
        "created_at": _utcnow().isoformat(),
    }
    _persist_org(org)
    _set_role(org["id"], owner_id, "owner")
    owner = auth_service.get_user_by_id(owner_id)
    audit(org["id"], (owner or {}).get("email", owner_id), "org.created", f"name={clean_name}")
    return org


def _persist_org(org: dict) -> None:
    _orgs_mem[org["id"]] = dict(org)
    _slugs_mem[org["slug"]] = org["id"]
    if _engine is None or _orgs is None:
        return
    try:
        with _engine.begin() as conn:
            # Tolerate older databases whose orgs table predates the billing
            # columns (they simply keep working without trial/activation data).
            cols = set(_orgs.c.keys())
            values = {k: v for k, v in org.items()
                      if k in cols and k not in ("id", "slug", "sso_configured", "status")}
            for dt_key in ("trial_ends_at", "activated_at", "created_at"):
                if dt_key in values:
                    values[dt_key] = _parse_dt(values[dt_key]) or _utcnow()
            if "created_at" in cols and "created_at" not in values:
                values["created_at"] = _utcnow()
            existing = conn.execute(
                select(_orgs.c.id).where(_orgs.c.slug == org["slug"])
            ).first()
            if existing:
                conn.execute(_orgs.update().where(_orgs.c.id == org["id"]).values(**values))
            else:
                conn.execute(_orgs.insert().values(id=org["id"], slug=org["slug"], **values))
    except Exception:
        logger.exception("Failed to persist org")


def configure_sso(org_id: str, issuer: str, client_id: str, client_secret: str = "") -> dict:
    org = get_org(org_id)
    if org is None:
        raise ValueError("Organization not found.")
    issuer = issuer.strip().rstrip("/")
    if not (issuer.startswith("https://") and len(issuer) > len("https://x")):
        raise ValueError("Issuer must be an https:// URL.")
    client_id = client_id.strip()
    if not client_id:
        raise ValueError("Client ID is required.")
    full = _orgs_mem.get(org_id, dict(org))
    secret = client_secret.strip() or _secret(org_id)
    full.update({"sso_issuer": issuer, "sso_client_id": client_id,
                 "sso_client_secret": secret})
    _persist_org(full)
    return get_org(org_id) or org


def get_role(org_id: str, user_id: str) -> str | None:
    if _engine is not None and _members is not None:
        try:
            with _engine.connect() as conn:
                row = conn.execute(
                    select(_members.c.role).where(
                        (_members.c.org_id == org_id) & (_members.c.user_id == user_id)
                    )
                ).first()
            return row.role if row else None
        except Exception:
            logger.exception("Failed to read membership")
            return None
    return _members_mem.get((org_id, user_id))


def _set_role(org_id: str, user_id: str, role: str) -> None:
    _members_mem[(org_id, user_id)] = role
    if _engine is None or _members is None:
        return
    try:
        with _engine.begin() as conn:
            existing = conn.execute(
                select(_members.c.role).where(
                    (_members.c.org_id == org_id) & (_members.c.user_id == user_id)
                )
            ).first()
            if existing:
                conn.execute(_members.update().where(
                    (_members.c.org_id == org_id) & (_members.c.user_id == user_id)
                ).values(role=role))
            else:
                conn.execute(_members.insert().values(org_id=org_id, user_id=user_id, role=role))
    except Exception:
        logger.exception("Failed to persist membership")


def add_member(org_id: str, user_id: str, role: str = "member") -> None:
    if role not in ("owner", "admin", "member"):
        raise ValueError("Role must be owner, admin or member.")
    if get_org(org_id) is None:
        raise ValueError("Organization not found.")
    _set_role(org_id, user_id, role)


def add_member_by_email(org_id: str, email: str, actor: str, role: str = "member") -> dict:
    """Direct-add a user by email (owner/admin action, no mail server needed)."""
    from app.services import auth_service
    clean = email.strip().lower()
    if not _EMAIL_RE.match(clean):
        raise ValueError("Enter a valid email address.")
    user = auth_service.get_user_by_email(clean)
    if user is None:
        # Provisioned seat: real name/SSO fills in on first sign-in.
        user = auth_service.create_user(clean, clean.split("@")[0], None, provider="invited")
    add_member(org_id, user["id"], role)
    audit(org_id, actor, "member.added", f"email={clean} role={role}")
    return auth_service._public_user(user)


def orgs_for_user(user_id: str) -> list[dict]:
    out = []
    if _engine is not None and _members is not None:
        try:
            with _engine.connect() as conn:
                rows = conn.execute(
                    select(_members.c.org_id, _members.c.role).where(_members.c.user_id == user_id)
                ).fetchall()
            pairs = [(r.org_id, r.role) for r in rows]
        except Exception:
            logger.exception("Failed to list memberships")
            pairs = []
    else:
        pairs = [(oid, role) for (oid, uid), role in _members_mem.items() if uid == user_id]
    for oid, role in pairs:
        org = get_org(oid)
        if org is not None:
            out.append(_public_org(org, role))
    return out


def members_of(org_id: str) -> list[dict]:
    from app.services import auth_service
    if _engine is not None and _members is not None:
        try:
            with _engine.connect() as conn:
                rows = conn.execute(
                    select(_members.c.user_id, _members.c.role).where(_members.c.org_id == org_id)
                ).fetchall()
            pairs = [(r.user_id, r.role) for r in rows]
        except Exception:
            logger.exception("Failed to list members")
            return []
    else:
        pairs = [(uid, role) for (oid, uid), role in _members_mem.items() if oid == org_id]
    out = []
    for uid, role in pairs:
        user = auth_service.get_user_by_id(uid)
        if user is not None:
            pub = auth_service._public_user(user)
            pub["org_role"] = role
            out.append(pub)
    return out


def user_has_enterprise(user_id: str) -> bool:
    """Enterprise quota inheritance: membership in a trial/active org unlocks it.

    Expired-trial orgs grant nothing — members fall back to personal plans.
    """
    for org in orgs_for_user(user_id):
        if org.get("plan_id") == "enterprise" and org_status(org) in ("trial", "active"):
            return True
    return False


def activate_org(org_id: str, actor: str, billing_cycle: str = "annual", receipt: str = "") -> dict:
    """Record a (demo) enterprise purchase on the org. A real Stripe webhook
    should call this same function after verified payment."""
    org = get_org(org_id)
    if org is None:
        raise ValueError("Organization not found.")
    if billing_cycle not in ("monthly", "annual"):
        billing_cycle = "annual"
    full = _orgs_mem.get(org_id, dict(org))
    if full.get("sso_client_secret") is None:
        # Don't wipe a stored secret when activating from a cold memory cache.
        full["sso_client_secret"] = _secret(org_id)
    full.update({
        "activated_at": _utcnow().isoformat(),
        "billing_cycle": billing_cycle,
        "receipt": (receipt or "")[:64],
    })
    _persist_org(full)
    audit(org_id, actor, "org.activated", f"cycle={billing_cycle} receipt={full['receipt']}")
    return get_org(org_id) or org


def audit(org_id: str, actor: str, action: str, detail: str = "") -> None:
    entry = {
        "id": uuid.uuid4().hex[:16],
        "org_id": org_id,
        "actor": actor,
        "action": action,
        "detail": detail[:2000],
        "created_at": _utcnow().isoformat(),
    }
    _audit_mem.append(entry)
    del _audit_mem[:-500]
    if _engine is None or _audit is None:
        return
    try:
        with _engine.begin() as conn:
            conn.execute(_audit.insert().values(
                id=entry["id"], org_id=org_id, actor=actor, action=action,
                detail=entry["detail"], created_at=_utcnow(),
            ))
    except Exception:
        logger.exception("Failed to persist audit entry")


def audit_log(org_id: str, limit: int = 100) -> list[dict]:
    if _engine is not None and _audit is not None:
        try:
            with _engine.connect() as conn:
                rows = conn.execute(
                    select(_audit).where(_audit.c.org_id == org_id)
                    .order_by(_audit.c.created_at.desc()).limit(max(1, min(limit, 200)))
                ).fetchall()
            return [{
                "id": r.id, "actor": r.actor, "action": r.action,
                "detail": r.detail, "created_at": r.created_at.isoformat() if r.created_at else "",
            } for r in rows]
        except Exception:
            logger.exception("Failed to read audit log")
    items = [e for e in reversed(_audit_mem) if e["org_id"] == org_id]
    return [{k: v for k, v in e.items() if k != "org_id"} for e in items[: max(1, min(limit, 200))]]


# --- SSO login states / one-time codes (memory only) ---

def _prune_sso() -> None:
    now = time.time()
    for store in (_sso_states, _sso_codes):
        for k in [k for k, v in store.items() if v["exp"] <= now]:
            del store[k]


def create_sso_state(org_id: str, verifier: str) -> str:
    _prune_sso()
    state = secrets.token_urlsafe(24)
    _sso_states[state] = {"org_id": org_id, "verifier": verifier, "exp": time.time() + SSO_STATE_TTL}
    return state


def pop_sso_state(state: str) -> dict | None:
    _prune_sso()
    return _sso_states.pop(state, None)


def create_sso_code(user_id: str, org_id: str) -> str:
    _prune_sso()
    code = secrets.token_urlsafe(24)
    _sso_codes[code] = {"user_id": user_id, "org_id": org_id, "exp": time.time() + SSO_CODE_TTL}
    return code


def pop_sso_code(code: str) -> dict | None:
    _prune_sso()
    return _sso_codes.pop(code, None)


def reset_state() -> None:
    _orgs_mem.clear()
    _slugs_mem.clear()
    _members_mem.clear()
    _audit_mem.clear()
    _sso_states.clear()
    _sso_codes.clear()
