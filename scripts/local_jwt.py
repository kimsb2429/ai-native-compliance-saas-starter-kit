"""Local development only: a throwaway RSA key, a JWKS served on localhost, and
token minting for the two demo tenants. Lets `make local` run the real runtime
against real Bedrock without Cognito. Never used in deployment.

  uv run python scripts/local_jwt.py serve        # prints env exports, serves JWKS on :8790
  uv run python scripts/local_jwt.py token acme   # prints an ID-token-shaped JWT for tenant acme
"""

from __future__ import annotations

import http.server
import json
import pathlib
import sys
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

STATE = pathlib.Path(__file__).resolve().parents[1] / ".local-jwt"
ORGS = {"acme": "11111111-1111-4111-8111-111111111111", "blueharbor": "22222222-2222-4222-8222-222222222222"}
ISSUER, AUDIENCE, KID, PORT = "http://127.0.0.1:8790", "local-kit-client", "local-key-1", 8790


def key():
    STATE.mkdir(exist_ok=True)
    pem = STATE / "key.pem"
    if not pem.exists():
        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return serialization.load_pem_private_key(pem.read_bytes(), password=None)


def serve():
    k = key()
    jwk = json.loads(RSAAlgorithm.to_jwk(k.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    body = json.dumps({"keys": [jwk]}).encode()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        def log_message(self, *a): pass

    print(f"export JWT_JWKS_URL={ISSUER}/jwks.json JWT_ISSUER={ISSUER} JWT_AUDIENCE={AUDIENCE} JWT_ORG_CLAIM=custom:org_id")
    http.server.HTTPServer(("127.0.0.1", PORT), H).serve_forever()


def token(tenant: str) -> str:
    k = key()
    now = int(time.time())
    claims = {"sub": f"local-{tenant}", "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 3600,
              "custom:org_id": ORGS[tenant], "cognito:username": f"{tenant}-user"}
    return jwt.encode(claims, k, algorithm="RS256", headers={"kid": KID})


if __name__ == "__main__":
    if sys.argv[1:2] == ["serve"]:
        serve()
    elif sys.argv[1:2] == ["token"]:
        print(token(sys.argv[2]))
    else:
        sys.exit(__doc__)
