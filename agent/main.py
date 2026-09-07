"""AgentCore entrypoint: /invocations and /ping, served by BedrockAgentCoreApp.

Request contract (JSON body):
  agent_ref    which agent_definitions row to build           required
  prompt       the user message (chat agents)                  required unless extractor
  document_id  which document to extract (extractor only; the assistant reads
               documents through its own get_document tool)      optional
  stream       true -> SSE events, false -> one JSON object     default true

Tenant identity is NOT in the body. It comes from the verified bearer token
(see agent/tenant.py). Session identity is the runtime session header, which
AgentCore maps to an isolated microVM per session.
"""

from __future__ import annotations

import asyncio
import logging
import time

import psycopg
from bedrock_agentcore import BedrockAgentCoreApp
from psycopg_pool import PoolTimeout
from bedrock_agentcore.runtime.context import RequestContext

from agent import settings, tenant
from agent.builder import build_agent
from agent.db import close_pool, pool
from agent.extract import extract_and_store

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


def _authorization(context: RequestContext | None) -> str | None:
    headers = (context.request_headers if context else None) or {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            return value
    return None


def _event_to_wire(event: dict) -> dict | None:
    """Reduce Strands stream events to a small, serializable vocabulary."""
    if "data" in event and isinstance(event["data"], str):
        return {"type": "text", "text": event["data"]}
    if "current_tool_use" in event and event.get("current_tool_use", {}).get("name"):
        tu = event["current_tool_use"]
        return {"type": "tool_use", "name": tu.get("name")}
    if "result" in event:
        result = event["result"]
        return {"type": "end", "stop_reason": str(getattr(result, "stop_reason", ""))}
    return None


async def _stream(built, prompt: str, started: float, who: tenant.Tenant):
    # The framework iterates this generator in its own task, so the tenant
    # ContextVar set in invoke() is not visible here. Set it again in this
    # context and clear it when the stream ends.
    token = tenant.activate(who)
    try:
        async for wire in _stream_events(built, prompt, started):
            yield wire
    finally:
        tenant.deactivate(token)


async def _stream_events(built, prompt: str, started: float):
    yield {"type": "start", "agent_ref": built.definition.agent_ref, "agent_version": built.definition.version,
           "prompt_slug": built.prompt.slug, "prompt_revision": built.prompt.revision, "model_id": built.model_id}
    last_tool = None
    async for event in built.agent.stream_async(prompt):
        wire = _event_to_wire(event)
        if wire is None:
            continue
        if wire["type"] == "tool_use":
            if wire["name"] == last_tool:
                continue
            last_tool = wire["name"]
        yield wire
    yield {"type": "done", "elapsed_ms": int((time.time() - started) * 1000)}


async def _collect(built, prompt: str, started: float) -> dict:
    text, tools, stop = [], [], None
    async for wire in _stream_events(built, prompt, started):
        if wire["type"] == "text":
            text.append(wire["text"])
        elif wire["type"] == "tool_use":
            tools.append(wire["name"])
        elif wire["type"] == "end":
            stop = wire["stop_reason"]
    return {"agent_ref": built.definition.agent_ref, "agent_version": built.definition.version,
            "prompt_slug": built.prompt.slug, "prompt_revision": built.prompt.revision, "model_id": built.model_id,
            "tools_used": tools, "stop_reason": stop, "text": "".join(text),
            "elapsed_ms": int((time.time() - started) * 1000)}


@app.entrypoint
async def invoke(payload: dict, context: RequestContext | None = None):
    started = time.time()
    try:
        # JWKS fetch on a cache miss is blocking HTTP; keep it off the event loop.
        who = await asyncio.to_thread(tenant.tenant_from_bearer, _authorization(context))
    except tenant.TenantError as e:
        logger.warning("rejected: %s", e)
        return {"error": f"unauthorized: {e}"}

    agent_ref = payload.get("agent_ref")
    if not agent_ref:
        return {"error": "agent_ref is required"}
    session_id = (context.session_id if context else None) or "local"
    token = tenant.activate(who)
    try:
        built = await asyncio.to_thread(build_agent, agent_ref, who.org_id, session_id)
        if built.definition.structured_output == "ObligationList":
            return await extract_and_store(built, who.org_id, payload.get("document_id"))
        prompt = payload.get("prompt")
        if not prompt:
            return {"error": "prompt is required"}
        if payload.get("stream", True):
            return _stream(built, prompt, started, who)
        return await _collect(built, prompt, started)
    except LookupError as e:
        return {"error": str(e)}
    except (psycopg.Error, PoolTimeout) as e:
        logger.exception("database unavailable")
        return {"error": f"database unavailable: {type(e).__name__}"}
    finally:
        tenant.deactivate(token)


@app.ping
def ping():
    from bedrock_agentcore.runtime.models import PingStatus

    return PingStatus.HEALTHY


if __name__ == "__main__":
    pool()  # open the pool before the first request lands
    try:
        app.run()
    finally:
        close_pool()
