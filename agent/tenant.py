"""Tenant identity: verified JWT claim -> ContextVar (B14, kit form).

The engagement read tenancy from the request body and trusted it. Here the
AgentCore runtime already validated the bearer token against the Cognito
discovery URL before the request reached this process; the same token is
forwarded in the Authorization header, and this module verifies it a second
time in-process (signature, issuer, audience) and reads the org claim. The org
id is then parked on a ContextVar for the life of the invoke. Nothing in the
payload can name a tenant.
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass
from uuid import UUID

import jwt
from jwt import PyJWKClient

from agent import settings

logger = logging.getLogger(__name__)

_current_org: contextvars.ContextVar[UUID | None] = contextvars.ContextVar("current_org", default=None)
_jwk_client: PyJWKClient | None = None


class TenantError(Exception):
    """Raised when no verified tenant can be established for a request."""


@dataclass(frozen=True)
class Tenant:
    org_id: UUID
    subject: str
    username: str | None


def _jwks() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        if not settings.JWT_JWKS_URL:
            raise TenantError("JWT_JWKS_URL is not configured")
        _jwk_client = PyJWKClient(settings.JWT_JWKS_URL, cache_keys=True, lifespan=3600)
    return _jwk_client


def tenant_from_bearer(authorization: str | None) -> Tenant:
    """Verify the bearer token and return the tenant it names."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise TenantError("missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    signing_key = _jwks().get_signing_key_from_jwt(token)
    options = {"require": ["exp", "iat"], "verify_aud": settings.JWT_AUDIENCE is not None}
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        options=options,
    )
    raw = claims.get(settings.JWT_ORG_CLAIM)
    if not raw:
        raise TenantError(f"token has no {settings.JWT_ORG_CLAIM} claim")
    try:
        org_id = UUID(str(raw))
    except ValueError as e:
        raise TenantError(f"{settings.JWT_ORG_CLAIM} is not a UUID") from e
    return Tenant(org_id=org_id, subject=str(claims.get("sub", "")), username=claims.get("cognito:username"))


def activate(tenant: Tenant) -> contextvars.Token:
    return _current_org.set(tenant.org_id)


def deactivate(token: contextvars.Token) -> None:
    _current_org.reset(token)


def current_org() -> UUID:
    org = _current_org.get()
    if org is None:
        raise TenantError("no tenant in context")
    return org
