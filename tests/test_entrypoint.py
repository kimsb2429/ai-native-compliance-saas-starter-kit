"""The whole invoke path with a scripted model: JWT -> tenant -> row -> prompt -> agent -> outcome."""

import importlib

import pytest
from bedrock_agentcore.runtime.context import RequestContext

from tests.conftest import ACME, BLUE
from tests.fake_model import FakeModel


@pytest.fixture
def main_mod(database_url, jwks_server, monkeypatch):
    from agent import settings, tenant, builder, main
    importlib.reload(settings); importlib.reload(tenant); importlib.reload(builder); importlib.reload(main)
    return main


def _ctx(token: str) -> RequestContext:
    return RequestContext(session_id="test-session", request_headers={"Authorization": f"Bearer {token}"})


@pytest.mark.asyncio
async def test_unauthorized_without_token(main_mod):
    out = await main_mod.invoke({"agent_ref": "compliance-assistant", "prompt": "hi"}, RequestContext())
    assert "unauthorized" in out["error"]


@pytest.mark.asyncio
async def test_assistant_non_stream_uses_registry_prompt_and_tool(main_mod, jwks_server, monkeypatch):
    fake = FakeModel(text="You must stack test quarterly.", call_tool="list_obligations")
    monkeypatch.setattr(main_mod, "build_agent", _patched_builder(fake))
    out = await main_mod.invoke(
        {"agent_ref": "compliance-assistant", "prompt": "quarterly?", "stream": False}, _ctx(jwks_server(ACME)))
    assert out["prompt_slug"] == "compliance-assistant-system" and out["prompt_revision"] == 1
    assert out["tools_used"] == ["list_obligations"] and "quarterly" in out["text"]
    assert fake.seen_system[0].startswith("You are a compliance assistant")


@pytest.mark.asyncio
async def test_assistant_stream_yields_wire_events(main_mod, jwks_server, monkeypatch):
    monkeypatch.setattr(main_mod, "build_agent", _patched_builder(FakeModel(text="streamed")))
    gen = await main_mod.invoke({"agent_ref": "compliance-assistant", "prompt": "x"}, _ctx(jwks_server(ACME)))
    events = [e async for e in gen]
    kinds = [e["type"] for e in events]
    assert kinds[0] == "start" and kinds[-1] == "done" and "text" in kinds and "end" in kinds


@pytest.mark.asyncio
async def test_extractor_writes_rows_for_the_calling_tenant_only(main_mod, jwks_server, monkeypatch):
    structured = {"obligations": [
        {"citation": "2.1", "requirement": "Conduct a stack test each quarter.", "frequency": "quarterly",
         "responsible_party": None, "due_rule": "within 30 days of the test"},
        {"citation": "4.1", "requirement": "Submit the annual emissions inventory.", "frequency": "annual",
         "responsible_party": None, "due_rule": "by March 1"},
    ]}
    monkeypatch.setattr(main_mod, "build_agent", _patched_builder(FakeModel(structured=structured)))
    out = await main_mod.invoke({"agent_ref": "obligation-extractor"}, _ctx(jwks_server(BLUE)))
    assert out["count"] == 2 and out["title"].startswith("Industrial Stormwater")
    from agent.tools import make_tools
    from uuid import UUID
    acme = {t.tool_name: t for t in make_tools(UUID(ACME), ["list_obligations"])}
    blue = {t.tool_name: t for t in make_tools(UUID(BLUE), ["list_obligations"])}
    assert "stack test" in blue["list_obligations"]().lower()
    assert "stack test" not in acme["list_obligations"]().lower()


@pytest.mark.asyncio
async def test_unknown_agent_ref_is_a_clean_error(main_mod, jwks_server):
    out = await main_mod.invoke({"agent_ref": "nope", "prompt": "x"}, _ctx(jwks_server(ACME)))
    assert out["error"].startswith("Agent not found")


def _patched_builder(fake: FakeModel):
    from agent import builder as b

    def build(agent_ref, org_id, session_id):
        real = b._model
        b._model = lambda model_id: fake  # noqa: E731
        try:
            return b.build_agent(agent_ref, org_id, session_id)
        finally:
            b._model = real

    return build
