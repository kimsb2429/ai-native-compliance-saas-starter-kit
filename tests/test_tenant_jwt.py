"""Tenant comes from a verified token, never from the body."""

import importlib

import pytest

from tests.conftest import ACME, BLUE


@pytest.fixture
def tenant_mod(jwks_server):
    from agent import settings, tenant
    importlib.reload(settings)
    importlib.reload(tenant)
    return tenant


def test_valid_token_yields_org(jwks_server, tenant_mod):
    t = tenant_mod.tenant_from_bearer("Bearer " + jwks_server(ACME))
    assert str(t.org_id) == ACME


def test_wrong_audience_rejected(jwks_server, tenant_mod):
    with pytest.raises(Exception):
        tenant_mod.tenant_from_bearer("Bearer " + jwks_server(BLUE, aud="someone-else"))


def test_missing_claim_rejected(jwks_server, tenant_mod):
    import jwt as pyjwt  # noqa: F401
    tok = jwks_server(ACME)
    # forge: strip the claim by minting with an empty org
    with pytest.raises(tenant_mod.TenantError):
        tenant_mod.tenant_from_bearer("Bearer " + jwks_server("", ))


def test_no_header_rejected(tenant_mod):
    with pytest.raises(tenant_mod.TenantError):
        tenant_mod.tenant_from_bearer(None)


def test_contextvar_roundtrip(jwks_server, tenant_mod):
    t = tenant_mod.tenant_from_bearer("Bearer " + jwks_server(BLUE))
    token = tenant_mod.activate(t)
    try:
        assert str(tenant_mod.current_org()) == BLUE
    finally:
        tenant_mod.deactivate(token)
    with pytest.raises(tenant_mod.TenantError):
        tenant_mod.current_org()
