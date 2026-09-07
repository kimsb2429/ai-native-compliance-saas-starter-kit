"""B14 in the kit: one pool, tenant set per transaction, Postgres enforces the line."""

import psycopg
import pytest

from tests.conftest import ACME, BLUE


def _titles(url, org):
    with psycopg.connect(url) as conn:
        with conn.transaction():
            conn.execute("select set_config('app.org_id', %s, true)", (org,))
            return sorted(r[0] for r in conn.execute("select title from documents").fetchall())


def test_each_tenant_sees_only_its_own_documents(database_url):
    assert _titles(database_url, ACME) == ["Air Quality Operating Permit AQ-2024-0117"]
    assert _titles(database_url, BLUE) == ["Industrial Stormwater General Permit SW-2023-0882"]


def test_no_tenant_setting_sees_nothing(database_url):
    with psycopg.connect(database_url) as conn:
        assert conn.execute("select count(*) from documents").fetchone()[0] == 0
        assert conn.execute("select count(*) from obligations").fetchone()[0] == 0


def test_setting_does_not_leak_across_transactions_on_one_connection(database_url):
    with psycopg.connect(database_url) as conn:
        with conn.transaction():
            conn.execute("select set_config('app.org_id', %s, true)", (ACME,))
            assert conn.execute("select count(*) from documents").fetchone()[0] == 1
        # same physical connection, new transaction, no setting: nothing visible
        with conn.transaction():
            assert conn.execute("select count(*) from documents").fetchone()[0] == 0


def test_tenant_cannot_insert_rows_for_another_tenant(database_url):
    with psycopg.connect(database_url) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute("select set_config('app.org_id', %s, true)", (BLUE,))
                conn.execute(
                    "insert into obligations (org_id, requirement) values (%s, 'planted by blue harbor')", (ACME,)
                )


def test_owner_role_is_bound_too_force_rls(database_url):
    """The pool's single role owns the tables; FORCE ROW LEVEL SECURITY keeps it honest."""
    with psycopg.connect(database_url) as conn:
        forced = conn.execute(
            "select relforcerowsecurity from pg_class where relname in ('documents','obligations')"
        ).fetchall()
        assert forced and all(r[0] for r in forced)
