"""Agents as rows (A3, kit form): read the active definition, build a live Agent.

One image serves every agent_ref. The row names the model size, the prompt
slug, the tools, and (optionally) a structured-output schema. The prompt slug
resolves through the registry (A26); the tools are bound to the tenant (B14).
Adding an agent is an INSERT, and the next invoke builds it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from strands import Agent
from strands.models import BedrockModel

from agent import settings
from agent.db import platform_txn
from agent.models import STRUCTURED_OUTPUT_MODELS
from agent.prompts import PromptRevision, get_prompt
from agent.tools import make_tools

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentDefinition:
    agent_ref: str
    environment: str
    version: int
    model_size: str
    prompt_slug: str
    tools: list[str]
    structured_output: str | None


@dataclass(frozen=True)
class BuiltAgent:
    agent: Agent
    definition: AgentDefinition
    prompt: PromptRevision


def load_definition(agent_ref: str, environment: str = settings.ENVIRONMENT) -> AgentDefinition:
    with platform_txn() as cur:
        cur.execute(
            """select agent_ref, environment, version, model_size, prompt_slug, tools, structured_output
               from agent_definitions where agent_ref = %s and environment = %s and is_active""",
            (agent_ref, environment),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"Agent not found: {agent_ref} (env={environment})")
    return AgentDefinition(
        agent_ref=row["agent_ref"],
        environment=row["environment"],
        version=row["version"],
        model_size=row["model_size"],
        prompt_slug=row["prompt_slug"],
        tools=list(row["tools"] or []),
        structured_output=row["structured_output"],
    )


def _model(model_id: str) -> BedrockModel:
    kwargs: dict = {"model_id": model_id, "temperature": 0.2}
    if settings.GUARDRAIL_ID:
        kwargs.update(
            guardrail_id=settings.GUARDRAIL_ID,
            guardrail_version=settings.GUARDRAIL_VERSION,
            guardrail_trace="enabled",
            guardrail_redact_input=True,
            guardrail_redact_output=True,
            guardrail_redact_output_message="[response withheld by the compliance guardrail]",
        )
    return BedrockModel(**kwargs)


def build_agent(agent_ref: str, org_id: UUID, session_id: str) -> BuiltAgent:
    definition = load_definition(agent_ref)
    prompt = get_prompt(definition.prompt_slug)
    model_id = prompt.model_id  # size aliases were resolved in prompts.py; the revision's id wins
    structured = STRUCTURED_OUTPUT_MODELS.get(definition.structured_output) if definition.structured_output else None
    agent = Agent(
        model=_model(model_id),
        system_prompt=prompt.system_text,
        tools=make_tools(org_id, definition.tools),
        structured_output_model=structured,
        callback_handler=None,
        trace_attributes={
            "agent_ref": definition.agent_ref,
            "agent_version": definition.version,
            "prompt_slug": prompt.slug,
            "prompt_revision": prompt.revision,
            "session_id": session_id,
        },
    )
    logger.info(
        "built agent %s v%s prompt=%s r%s model=%s tools=%s",
        definition.agent_ref, definition.version, prompt.slug, prompt.revision, model_id, definition.tools,
    )
    return BuiltAgent(agent=agent, definition=definition, prompt=prompt)
