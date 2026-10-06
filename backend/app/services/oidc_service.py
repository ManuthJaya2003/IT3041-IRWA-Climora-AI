"""Generic OIDC SSO: authorization-code flow with PKCE + JWKS verification.

Works with any OIDC-compliant provider (Okta, Entra ID, Auth0, Google).
No provider SDK needed — discovery + JWKS over HTTPS, signatures via
python-jose, HTTP via httpx. Injectable fetchers keep it unit-testable.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

try:
    from jose import jwt
except ImportError:  # pragma: no cover
    jwt = None  # type: ignore

_discovery_cache: dict[str, tuple[float, dict]] = {}
_jwks_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 600


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def callback_url(public_origin: str) -> str:
    return public_origin.rstrip("/") + "/api/v1/auth/sso/callback"


async def fetch_json(url: str, timeout: float = 10.0) -> dict:
    import httpx
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("OIDC endpoint did not return a JSON object.")
    return data


async def discover(issuer: str) -> dict:
    """OIDC discovery document, cached briefly."""
    base = issuer.strip().rstrip("/")
    now = time.time()
    hit = _discovery_cache.get(base)
    if hit and hit[0] > now:
        return hit[1]
    doc = await fetch_json(base + "/.well-known/openid-configuration")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not doc.get(key):
            raise ValueError(f"Issuer discovery is missing {key}.")
    _discovery_cache[base] = (now + _CACHE_TTL, doc)
    return doc


async def fetch_jwks(jwks_uri: str) -> dict:
    now = time.time()
    hit = _jwks_cache.get(jwks_uri)
    if hit and hit[0] > now:
        return hit[1]
    doc = await fetch_json(jwks_uri)
    if not isinstance(doc.get("keys"), list):
        raise ValueError("JWKS endpoint did not return a key set.")
    _jwks_cache[jwks_uri] = (now + _CACHE_TTL, doc)
    return doc


def build_start_url(*, authorization_endpoint: str, client_id: str,
                    redirect_uri: str, state: str, challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return authorization_endpoint + "?" + urlencode(params)


async def exchange_code(*, token_endpoint: str, code: str, redirect_uri: str,
                        client_id: str, verifier: str,
                        client_secret: str | None = None) -> dict:
    """Exchange an authorization code for tokens (PKCE, secret optional)."""
    import httpx
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        body["client_secret"] = client_secret
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_endpoint, data=body)
    if resp.status_code != 200:
        raise ValueError(f"Token exchange failed (HTTP {resp.status_code}).")
    data = resp.json()
    if not data.get("id_token"):
        raise ValueError("Token endpoint did not return an ID token.")
    return data


def verify_id_token(id_token: str, *, issuer: str, audience: str,
                    jwks: dict | None = None) -> dict:
    """Verify signature (JWKS), iss, aud, exp. Returns {email, name}."""
    if jwt is None:
        raise RuntimeError("JWT library unavailable.")
    if jwks is None:
        raise ValueError("JWKS is required for verification.")
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    key_data = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key_data is None and len(jwks.get("keys", [])) == 1:
        key_data = jwks["keys"][0]
    if key_data is None:
        raise ValueError("No matching signing key (kid mismatch).")
    claims = jwt.decode(
        id_token, key_data,
        algorithms=["RS256", "ES256"],
        audience=audience,
        issuer=issuer,
        options={"require_exp": True, "require_iss": True, "require_aud": True},
    )
    email = str(claims.get("email", "")).lower().strip()
    if not email or "@" not in email:
        raise ValueError("ID token has no email claim.")
    if claims.get("email_verified") is False:
        raise ValueError("Email address is not verified at the identity provider.")
    name = str(claims.get("name") or claims.get("preferred_username") or email.split("@")[0])
    return {"email": email, "name": name[:120], "sub": str(claims.get("sub", ""))}


async def verify_id_token_remote(id_token: str, *, issuer: str, audience: str) -> dict:
    doc = await discover(issuer)
    jwks = await fetch_jwks(doc["jwks_uri"])
    try:
        return verify_id_token(id_token, issuer=issuer, audience=audience, jwks=jwks)
    except ValueError as exc:
        if "kid" in str(exc).lower():
            # Key rotation: refresh once and retry.
            _jwks_cache.pop(doc["jwks_uri"], None)
            jwks = await fetch_jwks(doc["jwks_uri"])
            return verify_id_token(id_token, issuer=issuer, audience=audience, jwks=jwks)
        raise
