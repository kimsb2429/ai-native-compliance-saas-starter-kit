"""Test fixtures: a throwaway schema on the local Postgres, and a local JWKS server.

Run `docker run -d --name kit-pg -e POSTGRES_PASSWORD=kit -e POSTGRES_USER=kit \
  -e POSTGRES_DB=compliance -p 127.0.0.1:5439:5432 postgres:17-alpine` first, or set TEST_DATABASE_URL.
"""

from __future__ import annotations

import http.server
import json
import os
import pathlib
import threading
import time
import uuid

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DB = os.getenv("TEST_DATABASE_URL", "postgresql://kit:kit@localhost:5439/compliance")
ACME = "11111111-1111-4111-8111-111111111111"
BLUE = "22222222-2222-4222-8222-222222222222"


@pytest.fixture(scope="session")
def database_url():
    """Fresh database per test session so schema.sql runs clean."""
    name = "kit_test_" + uuid.uuid4().hex[:8]
    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute(f'create database "{name}"')
    url = TEST_DB.rsplit("/", 1)[0] + "/" + name
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute((ROOT / "db/schema.sql").read_text())
        conn.execute((ROOT / "db/seed.sql").read_text())
        for org, path, title in [
            (ACME, "examples/documents/acme-air-permit.md", "Air Quality Operating Permit AQ-2024-0117"),
            (BLUE, "examples/documents/blueharbor-stormwater-permit.md", "Industrial Stormwater General Permit SW-2023-0882"),
        ]:
            with conn.transaction():
                conn.execute("select set_config('app.org_id', %s, true)", (org,))
                conn.execute("insert into documents (org_id, title, kind, body) values (%s, %s, 'permit', %s)",
                             (org, title, (ROOT / path).read_text()))
    # The runtime role: plain LOGIN, NOBYPASSRLS. Superusers ignore RLS, so tests
    # exercise the same role the deployed agent uses.
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("alter role kit_app password 'kit_app'")
    app_url = url.replace("//kit:kit@", "//kit_app:kit_app@")
    os.environ["DATABASE_URL"] = app_url
    yield app_url
    from agent.db import close_pool
    close_pool()
    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute(f'drop database "{name}" with (force)')


@pytest.fixture(scope="session")
def jwks_server():
    """An RSA key pair and a tiny HTTP server publishing its JWKS."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    kid = "test-key-1"
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})
    body = json.dumps({"keys": [jwk]}).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # silence
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    os.environ["JWT_JWKS_URL"] = f"http://127.0.0.1:{port}/jwks.json"
    os.environ["JWT_ISSUER"] = "https://issuer.test"
    os.environ["JWT_AUDIENCE"] = "kit-test-client"
    os.environ["JWT_ORG_CLAIM"] = "custom:org_id"

    def mint(org_id: str, **extra) -> str:
        claims = {"sub": "user-" + org_id[:4], "iss": "https://issuer.test", "aud": "kit-test-client",
                  "iat": int(time.time()), "exp": int(time.time()) + 600, "custom:org_id": org_id,
                  "cognito:username": "user-" + org_id[:4]}
        claims.update(extra)
        return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})

    yield mint
    server.shutdown()
