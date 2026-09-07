"""Tools built for one tenant cannot read another tenant's rows."""

from uuid import UUID

import psycopg

from agent.tools import make_tools
from tests.conftest import ACME, BLUE


def test_get_document_is_tenant_bound(database_url):
    acme_tools = {t.tool_name: t for t in make_tools(UUID(ACME), ["get_document", "list_obligations"])}
    blue_tools = {t.tool_name: t for t in make_tools(UUID(BLUE), ["get_document", "list_obligations"])}
    assert "Air Quality" in acme_tools["get_document"]()
    assert "Stormwater" in blue_tools["get_document"]()


def test_list_obligations_sees_only_own_rows(database_url):
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.transaction():
            conn.execute("select set_config('app.org_id', %s, true)", (ACME,))
            doc = conn.execute("select id from documents limit 1").fetchone()[0]
            conn.execute("insert into obligations (org_id, document_id, citation, requirement, frequency) "
                         "values (%s, %s, '2.1', 'Stack test each quarter', 'quarterly')", (ACME, doc))
    acme = {t.tool_name: t for t in make_tools(UUID(ACME), ["list_obligations"])}
    blue = {t.tool_name: t for t in make_tools(UUID(BLUE), ["list_obligations"])}
    assert "Stack test" in acme["list_obligations"](frequency="quarterly")
    assert "No obligations" in blue["list_obligations"]()
