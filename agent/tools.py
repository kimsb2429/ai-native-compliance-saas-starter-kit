"""Tools the assistant can call. Each is built per invoke with the tenant bound.

Strands may run tools on a worker thread, where a ContextVar set on the request
task is not guaranteed to be visible. Binding org_id into the closure at build
time removes that class of bug: the tool cannot query as anyone else.
"""

from __future__ import annotations

from uuid import UUID

from strands import tool

from agent.db import tenant_txn


def make_tools(org_id: UUID, names: list[str]) -> list:
    @tool
    def list_obligations(frequency: str | None = None) -> str:
        """List this organization's compliance obligations, optionally filtered by frequency
        (monthly, quarterly, semi-annual, annual, on-event, once, ongoing)."""
        with tenant_txn(org_id) as cur:
            if frequency:
                cur.execute(
                    """select o.citation, o.requirement, o.frequency, o.responsible_party, o.due_rule, d.title
                       from obligations o left join documents d on d.id = o.document_id
                       where o.frequency = %s order by d.title, o.citation""",
                    (frequency,),
                )
            else:
                cur.execute(
                    """select o.citation, o.requirement, o.frequency, o.responsible_party, o.due_rule, d.title
                       from obligations o left join documents d on d.id = o.document_id
                       order by d.title, o.citation"""
                )
            rows = cur.fetchall()
        if not rows:
            return "No obligations found for this organization."
        lines = []
        for r in rows:
            who = f" — responsible: {r['responsible_party']}" if r["responsible_party"] else ""
            due = f" — due: {r['due_rule']}" if r["due_rule"] else ""
            lines.append(f"[{r['title']} §{r['citation']}] ({r['frequency']}) {r['requirement']}{who}{due}")
        return "\n".join(lines)

    @tool
    def get_document(document_id: str | None = None) -> str:
        """Return the full text of one of this organization's documents. With no id, returns the most recent."""
        with tenant_txn(org_id) as cur:
            if document_id:
                cur.execute("select title, kind, body from documents where id = %s", (document_id,))
            else:
                cur.execute("select title, kind, body from documents order by created_at desc limit 1")
            row = cur.fetchone()
        if row is None:
            return "No such document for this organization."
        return f"# {row['title']} ({row['kind']})\n\n{row['body']}"

    registry = {"list_obligations": list_obligations, "get_document": get_document}
    unknown = [n for n in names if n not in registry]
    if unknown:
        raise LookupError(f"agent definition names unknown tools: {unknown}")
    return [registry[n] for n in names]
