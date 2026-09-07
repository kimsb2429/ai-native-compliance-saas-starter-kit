"""Run one example flow end to end and record its outcome.

  uv run python scripts/demo.py 03

Steps: run _before_sql (if any) against the database, invoke the runtime as the
payload's _tenant, write the outcome to examples/expected/<nn>.json, run
_after_sql (if any). The expected files are committed so a reader can diff a
fresh run against the recorded one.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import uuid

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from invoke import id_token, invoke, tf_output  # noqa: E402
from seed import database_url  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_sql(relpath: str) -> None:
    with psycopg.connect(database_url(), autocommit=True) as conn:
        conn.execute((ROOT / relpath).read_text())
    print(f"  sql: {relpath}")


def main() -> None:
    flow = sys.argv[1] if len(sys.argv) > 1 else "02"
    matches = sorted((ROOT / "examples/payloads").glob(f"{flow}-*.json"))
    if not matches:
        sys.exit(f"no payload for flow {flow}")
    path = matches[0]
    payload = json.loads(path.read_text())
    region = os.getenv("AWS_REGION", "us-east-1")
    print(f"flow {flow}: {path.name}\n  proves: {payload.get('_proves')}")
    if payload.get("_before_sql"):
        run_sql(payload["_before_sql"])
    url = os.getenv("RUNTIME_INVOKE_URL") or tf_output("runtime_invoke_url")
    session_id = f"kit-{uuid.uuid4()}-{uuid.uuid4().hex[:8]}"
    try:
        result = invoke(payload, id_token(payload["_tenant"], region), url, session_id)
        if isinstance(result, dict) and "modelStreamErrorException" in str(result.get("error", "")):
            print("  model stream error (transient); retrying once")
            result = invoke(payload, id_token(payload["_tenant"], region), url, session_id)
    finally:
        if payload.get("_after_sql"):
            run_sql(payload["_after_sql"])
    record = {
        "flow": flow, "payload_file": path.name, "tenant": payload["_tenant"],
        "proves": payload.get("_proves"), "recorded_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "result": result,
    }
    out = ROOT / "examples/expected" / f"{flow}.json"
    out.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(result, indent=2)[:3000])
    print(f"  recorded: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
