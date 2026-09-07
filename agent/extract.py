"""Document intake: one document in, obligation rows out (flow 01).

The extractor agent has a structured-output schema on its row. The runtime
renders the registry's user template around the document text, asks the model
for an ObligationList, and writes the rows back inside the tenant transaction.
"""

from __future__ import annotations

import logging
from uuid import UUID

from agent.builder import BuiltAgent
from agent.db import tenant_txn
from agent.models import ObligationList

logger = logging.getLogger(__name__)


def load_document(org_id: UUID, document_id: str | None) -> dict:
    with tenant_txn(org_id) as cur:
        if document_id:
            cur.execute("select id, title, kind, body from documents where id = %s", (document_id,))
        else:
            cur.execute("select id, title, kind, body from documents order by created_at desc limit 1")
        row = cur.fetchone()
    if row is None:
        raise LookupError("document not found for this organization")
    return row


async def extract_and_store(built: BuiltAgent, org_id: UUID, document_id: str | None) -> dict:
    doc = load_document(org_id, document_id)
    user_text = built.prompt.render_user(document=doc["body"]) or doc["body"]
    result = await built.agent.invoke_async(user_text, structured_output_model=ObligationList)
    parsed: ObligationList = result.structured_output  # type: ignore[assignment]
    with tenant_txn(org_id) as cur:
        cur.execute("delete from obligations where document_id = %s", (doc["id"],))
        for ob in parsed.obligations:
            cur.execute(
                """insert into obligations (org_id, document_id, citation, requirement, frequency, responsible_party, due_rule)
                   values (%s, %s, %s, %s, %s, %s, %s)""",
                (str(org_id), doc["id"], ob.citation, ob.requirement, ob.frequency, ob.responsible_party, ob.due_rule),
            )
    logger.info("stored %d obligations for document %s", len(parsed.obligations), doc["id"])
    return {
        "document_id": str(doc["id"]),
        "title": doc["title"],
        "obligations": [o.model_dump() for o in parsed.obligations],
        "count": len(parsed.obligations),
        "stop_reason": str(result.stop_reason),
    }
