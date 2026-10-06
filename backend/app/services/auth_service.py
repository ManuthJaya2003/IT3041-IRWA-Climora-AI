"""Real-world user accounts: password hashing, JWT sessions, server-side plans.

Replaces the old client-spoofable ``X-Plan`` model:

- ``POST /auth/register`` / ``/login`` / ``/google`` issue a JWT.
- The plan lives on the user row (PostgreSQL, memory fallback for dev).
- Quota and plan resolution prefer the authenticated user; ``X-Plan`` is
  only honoured for anonymous (logged-out) callers who are always Free.

Google Sign-In verifies the ID token against Google's tokeninfo endpoint
(no extra dependency) and checks ``aud`` against GOOGLE_CLIENT_ID when set.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services import plans_service

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import (
        Column, DateTime, MetaData, String, Table, create_engine, select,
    )
    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    Column = DateTime = MetaData = String = Table = create_engine = select = None
    _SQLALCHEMY_AVAILABLE = False

try:
    from passlib.context import CryptContext
    _pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
except ImportError:  # pragma: no cover
    _pwd = None

try:
    from jose import JWTError, jwt
except ImportError:  # pragma: no cover
    JWTError = Exception  # type: ignore
    jwt = None  # type: ignore

ALGORITHM = "HS256"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_engine = None
_table = None
# Memory fallback for dev without PostgreSQL: {email_lower: user_dict}
_users: dict[str, dict] = {}
_ids: dict[str, dict] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def initialize(database_url: str | None = None) -> str:
    """Create the users table when PostgreSQL is reachable. Returns backend name."""
    global _engine, _table
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
        table = Table(
            "users", metadata,
            Column("id", String(64), primary_key=True),
            Column("email", String(320), unique=True, nullable=False, index=True),
            Column("name", String(120), nullable=False, default=""),
            Column("password_hash", String(256), nullable=True),
            Column("provider", String(16), nullable=False, default="local"),
            Column("plan_id", String(32), nullable=False, default="free"),
            Column("billing_cycle", String(16), nullable=False, default="monthly"),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(table.select().limit(1))
        _engine = engine
        _table = table
        return "postgresql" if is_pg else "sqlite"
    except Exception:
        logger.exception("Users persistence unavailable; using memory")
        _engine = None
        _table = None
        return "memory"


def validate_email(email: str) -> str:
    clean = email.strip().lower()
    if not _EMAIL_RE.match(clean):
        raise ValueError("Enter a valid email address.")
    return clean


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")


def hash_password(password: str) -> str:
    if _pwd is None:
        raise RuntimeError("Password hashing unavailable (passlib missing).")
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or _pwd is None:
        return False
    try:
        return _pwd.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    if jwt is None:
        raise RuntimeError("JWT unavailable (python-jose missing).")
    expire = _utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.secret_key, algorithm=ALGORITHM)


def decode_user_id(token: str) -> str | None:
    if jwt is None:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub else None
    except Exception:
        return None


def _row_to_user(row) -> dict:
    return {
        "id": row.id,
        "email": row.email,
        "name": row.name or "",
        "password_hash": row.password_hash,
        "provider": row.provider or "local",
        "plan_id": (row.plan_id or "free").lower(),
        "billing_cycle": row.billing_cycle or "monthly",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _public_user(user: dict) -> dict:
    from app.services import plans_service
    plan = plans_service.get_plan(user.get("plan_id"))
    try:
        from app.services import org_service
        enterprise = org_service.user_has_enterprise(user["id"])
    except Exception:
        enterprise = False
    effective = plans_service.get_plan("enterprise") if enterprise else plan
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "provider": user.get("provider", "local"),
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "effective_plan_id": effective["id"],
        "effective_plan_name": effective["name"],
        "billing_cycle": user.get("billing_cycle", "monthly"),
        "created_at": user.get("created_at", ""),
    }


def get_user_by_email(email: str) -> dict | None:
    clean = email.strip().lower()
    if _engine is not None and _table is not None:
        try:
            with _engine.connect() as conn:
                row = conn.execute(
                    select(_table).where(_table.c.email == clean)
                ).first()
            return _row_to_user(row) if row else None
        except Exception:
            logger.exception("Failed to read user")
    return _users.get(clean)


def get_user_by_id(user_id: str) -> dict | None:
    if _engine is not None and _table is not None:
        try:
            with _engine.connect() as conn:
                row = conn.execute(
                    select(_table).where(_table.c.id == user_id)
                ).first()
            return _row_to_user(row) if row else None
        except Exception:
            logger.exception("Failed to read user by id")
    return _ids.get(user_id)


def _persist(user: dict) -> None:
    _users[user["email"].lower()] = user
    _ids[user["id"]] = user
    if _engine is None or _table is None:
        return
    try:
        with _engine.begin() as conn:
            existing = conn.execute(
                select(_table.c.id).where(_table.c.email == user["email"].lower())
            ).first()
            values = {
                "id": user["id"],
                "email": user["email"].lower(),
                "name": user.get("name", ""),
                "password_hash": user.get("password_hash"),
                "provider": user.get("provider", "local"),
                "plan_id": user.get("plan_id", "free"),
                "billing_cycle": user.get("billing_cycle", "monthly"),
                "created_at": _utcnow(),
            }
            if existing:
                conn.execute(
                    _table.update().where(_table.c.id == user["id"]).values(
                        name=values["name"],
                        password_hash=values["password_hash"],
                        provider=values["provider"],
                        plan_id=values["plan_id"],
                        billing_cycle=values["billing_cycle"],
                    )
                )
            else:
                conn.execute(_table.insert().values(**values))
    except Exception:
        logger.exception("Failed to persist user")


def create_user(email: str, name: str, password: str | None, provider: str = "local") -> dict:
    clean = validate_email(email)
    if get_user_by_email(clean) is not None:
        raise ValueError("An account with this email already exists.")
    if provider == "local":
        if not password:
            raise ValueError("Password is required.")
        validate_password(password)
        password_hash = hash_password(password)
    else:
        password_hash = None
    user = {
        "id": uuid.uuid4().hex[:16],
        "email": clean,
        "name": (name or "").strip()[:120] or clean.split("@")[0],
        "password_hash": password_hash,
        "provider": provider,
        "plan_id": "free",
        "billing_cycle": "monthly",
        "created_at": _utcnow().isoformat(),
    }
    _persist(user)
    return user


def authenticate(email: str, password: str) -> dict:
    user = get_user_by_email(email.strip().lower())
    if user is None or not verify_password(password, user.get("password_hash")):
        raise ValueError("Invalid email or password.")
    return user


def get_or_create_google_user(email: str, name: str) -> dict:
    existing = get_user_by_email(email)
    if existing is not None:
        return existing
    return create_user(email, name or email.split("@")[0], None, provider="google")


def set_plan(user_id: str, plan_id: str, billing_cycle: str = "monthly") -> dict:
    plan = plans_service.get_plan(plan_id)
    if plan["id"] == "enterprise":
        raise ValueError("Enterprise is handled via sales - contact hello@climora.ai.")
    if billing_cycle not in ("monthly", "annual"):
        billing_cycle = "monthly"
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("User not found.")
    user["plan_id"] = plan["id"]
    user["billing_cycle"] = billing_cycle
    _persist(user)
    return user


async def verify_google_id_token(id_token: str) -> dict:
    """Verify a Google ID token and return {email, name}. Raises ValueError."""
    import httpx

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
        )
    if resp.status_code != 200:
        raise ValueError("Google sign-in failed - invalid token.")
    data = resp.json()
    email = str(data.get("email", "")).lower()
    if not email or not _EMAIL_RE.match(email):
        raise ValueError("Google account has no verified email.")
    aud = str(data.get("aud", ""))
    expected = (settings.google_client_id or "").strip()
    if expected and aud != expected:
        raise ValueError("Google token was issued for a different app.")
    return {"email": email, "name": str(data.get("name", "") or email.split("@")[0])}


def reset_state() -> None:
    _users.clear()
    _ids.clear()
