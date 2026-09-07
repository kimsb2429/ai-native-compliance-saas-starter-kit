"""Apply db/schema.sql and db/seed.sql, then load the worked documents.

DATABASE_URL from the environment wins; otherwise the script reads the
Terraform output `database_url` from infra/terraform.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import psycopg
from psycopg import sql

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = {
    "11111111-1111-4111-8111-111111111111": ("examples/documents/acme-air-permit.md", "Air Quality Operating Permit AQ-2024-0117", "permit"),
    "22222222-2222-4222-8222-222222222222": ("examples/documents/blueharbor-stormwater-permit.md", "Industrial Stormwater General Permit SW-2023-0882", "permit"),
}


def database_url() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    out = subprocess.run(["terraform", "-chdir=infra/terraform", "output", "-raw", "database_url"],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("DATABASE_URL not set and terraform output failed: " + out.stderr.strip())
    return out.stdout.strip()


def app_password() -> str:
    if os.getenv("APP_DB_PASSWORD"):
        return os.environ["APP_DB_PASSWORD"]
    out = subprocess.run(["terraform", "-chdir=infra/terraform", "output", "-raw", "app_db_password"],
                         cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("APP_DB_PASSWORD not set and terraform output failed: " + out.stderr.strip())
    return out.stdout.strip()


def main() -> None:
    url = database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute((ROOT / "db/schema.sql").read_text())
        conn.execute(sql.SQL("alter role kit_app password {}").format(sql.Literal(app_password())))
        conn.execute((ROOT / "db/seed.sql").read_text())
        for org_id, (path, title, kind) in DOCS.items():
            body = (ROOT / path).read_text()
            with conn.transaction():
                conn.execute("select set_config('app.org_id', %s, true)", (org_id,))
                exists = conn.execute("select 1 from documents where title = %s", (title,)).fetchone()
                if not exists:
                    conn.execute("insert into documents (org_id, title, kind, body) values (%s, %s, %s, %s)",
                                 (org_id, title, kind, body))
        n_docs = conn.execute("select count(*) from documents").fetchone()[0]
    print(f"seeded: schema + prompts + agent rows; documents visible without tenant: {n_docs} (RLS hides them; expect 0)")


if __name__ == "__main__":
    main()
