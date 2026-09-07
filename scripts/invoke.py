"""Invoke the deployed runtime as one tenant, with a Cognito ID token as bearer.

  uv run python scripts/invoke.py --tenant acme-user --payload examples/payloads/02-ask-quarterly-obligations.json

Reads runtime URL, user pool client id, and user passwords from Terraform outputs
(or from env: RUNTIME_INVOKE_URL, COGNITO_CLIENT_ID, COGNITO_PASSWORD_<USER>).
The tenant is never in the body: it travels only as the verified custom:org_id claim.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import uuid

import boto3
import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]


def tf_output(name: str) -> str:
    out = subprocess.run(["terraform", "-chdir=infra/terraform", "output", "-json", name],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"terraform output {name} failed: {out.stderr.strip()}")
    return json.loads(out.stdout)


def id_token(username: str, region: str) -> str:
    client_id = os.getenv("COGNITO_CLIENT_ID") or tf_output("cognito_client_id")
    password = os.getenv(f"COGNITO_PASSWORD_{username.upper().replace('-', '_')}")
    if not password:
        password = tf_output("cognito_users")[username]["password"]
    cognito = boto3.client("cognito-idp", region_name=region)
    resp = cognito.initiate_auth(
        ClientId=client_id, AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return resp["AuthenticationResult"]["IdToken"]


def invoke(payload: dict, token: str, url: str, session_id: str) -> dict | list:
    body = {k: v for k, v in payload.items() if not k.startswith("_")}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }
    events: list[dict] = []
    with httpx.stream("POST", url, headers=headers, json=body, timeout=300) as r:
        ctype = r.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            for line in r.iter_lines():
                if line.startswith("data: "):
                    try:
                        events.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        events.append({"type": "raw", "line": line[6:]})
            return events
        r.read()
        if r.status_code >= 400:
            return {"http_status": r.status_code, "body": r.text[:2000]}
        try:
            return r.json()
        except ValueError:
            return {"http_status": r.status_code, "body": r.text[:2000]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True, help="Cognito username, e.g. acme-user")
    ap.add_argument("--payload", required=True, help="path to a payload JSON")
    ap.add_argument("--session", default=None, help="runtime session id (33+ chars); default: new")
    ap.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    args = ap.parse_args()

    payload = json.loads(pathlib.Path(args.payload).read_text())
    url = os.getenv("RUNTIME_INVOKE_URL") or tf_output("runtime_invoke_url")
    session_id = args.session or f"kit-{uuid.uuid4()}-{uuid.uuid4().hex[:8]}"
    result = invoke(payload, id_token(args.tenant, args.region), url, session_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
