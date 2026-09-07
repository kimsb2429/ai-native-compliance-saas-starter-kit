"""A26 and A3 in the kit: registry reads, revision flip, agent row build (no model call)."""

import psycopg

from agent import prompts
from agent.builder import load_definition


def test_active_revision_resolves_and_caches(database_url):
    prompts.invalidate()
    rev = prompts.get_prompt("compliance-assistant-system")
    assert rev.revision == 1 and "compliance assistant" in rev.system_text
    assert rev.model_id.startswith("us.") or rev.model_id.startswith("global.")


def test_flipping_active_revision_changes_the_prompt_without_redeploy(database_url):
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("""insert into prompt_revisions (slug, revision, model_id, system_text, is_active)
                        values ('compliance-assistant-system', 2, 'MODEL_SMALL', 'REVISED: answer in exactly one sentence.', false)""")
        with conn.transaction():
            conn.execute("update prompt_revisions set is_active = false where slug = 'compliance-assistant-system'")
            conn.execute("update prompt_revisions set is_active = true where slug = 'compliance-assistant-system' and revision = 2")
    prompts.invalidate("compliance-assistant-system")
    rev = prompts.get_prompt("compliance-assistant-system")
    assert rev.revision == 2 and rev.system_text.startswith("REVISED")
    # restore
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.transaction():
            conn.execute("update prompt_revisions set is_active = false where slug = 'compliance-assistant-system'")
            conn.execute("update prompt_revisions set is_active = true where slug = 'compliance-assistant-system' and revision = 1")
    prompts.invalidate()


def test_only_one_active_revision_per_slug(database_url):
    with psycopg.connect(database_url, autocommit=True) as conn:
        try:
            conn.execute("""insert into prompt_revisions (slug, revision, model_id, system_text, is_active)
                            values ('gap-checker-system', 99, 'MODEL_SMALL', 'dup', true)""")
            raise AssertionError("second active revision was accepted")
        except psycopg.errors.UniqueViolation:
            pass


def test_agent_definition_row_loads(database_url):
    d = load_definition("compliance-assistant")
    assert d.tools == ["list_obligations", "get_document"] and d.structured_output is None
    e = load_definition("obligation-extractor")
    assert e.structured_output == "ObligationList" and e.tools == []


def test_inserting_a_row_adds_an_agent(database_url):
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("""insert into agent_definitions (agent_ref, environment, version, model_size, prompt_slug, tools)
                        values ('gap-checker', 'prod', 1, 'medium', 'gap-checker-system', '["list_obligations"]')
                        on conflict do nothing""")
    d = load_definition("gap-checker")
    assert d.prompt_slug == "gap-checker-system"
