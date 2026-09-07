-- Seed for the starter kit: two tenants, the prompt registry, two agent rows.
-- Documents are loaded by scripts/seed.py from examples/documents/*.md so the
-- worked documents stay readable files, not SQL string literals.
--
-- The two org ids are fixed by contract: the same UUIDs are set as the
-- custom:org_id attribute on the two Cognito users in infra/terraform/cognito.tf.

insert into organizations (id, slug, name) values
  ('11111111-1111-4111-8111-111111111111', 'acme',       'Acme Fabrication, Inc.'),
  ('22222222-2222-4222-8222-222222222222', 'blueharbor', 'Blue Harbor Logistics LLC')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- Prompt registry
-- ---------------------------------------------------------------------------
insert into prompts (slug, description) values
  ('compliance-assistant-system', 'System prompt for the conversational compliance assistant'),
  ('obligation-extractor-system', 'System prompt for structured extraction of obligations from a document'),
  ('gap-checker-system',          'System prompt for the gap-check agent added in flow 06')
on conflict (slug) do nothing;

insert into prompt_revisions (slug, revision, model_id, system_text, user_template, is_active) values
  ('compliance-assistant-system', 1, 'MODEL_MEDIUM',
   'You are a compliance assistant for one organization. Answer questions about that organization''s permits and the obligations extracted from them.
Use the tools to read obligations and documents; never invent a citation, a date, or a requirement that is not in the data.
When you list obligations, give the citation, the requirement in one line, the frequency, and the responsible party if known.
Keep answers short and factual.',
   null, true),
  ('obligation-extractor-system', 1, 'MODEL_SMALL',
   'You extract compliance obligations from a permit, regulation, or policy document.
An obligation is a concrete thing the permittee must do, keep, submit, notify, or not exceed.
For each obligation return: citation (the section number as written), requirement (one sentence, imperative), frequency (one of: monthly, quarterly, semi-annual, annual, on-event, once, ongoing), responsible_party (if the document names one, else null), due_rule (the deadline phrase as written, else null).
Return every obligation you find. Do not merge distinct obligations. Do not add obligations that are not in the text.',
   'Extract all obligations from the following document.

<document>
{{document}}
</document>',
   true),
  ('gap-checker-system', 1, 'MODEL_MEDIUM',
   'You are a compliance gap checker. Given the organization''s extracted obligations, identify which obligations have no evidence of completion in the last period and rank them by regulatory risk (notification and reporting deadlines first). Be concrete and brief.',
   null, true)
on conflict (slug, revision) do nothing;

-- ---------------------------------------------------------------------------
-- Agent definitions (A3): one row per agent. Flow 06 inserts a third row live.
-- ---------------------------------------------------------------------------
insert into agent_definitions (agent_ref, environment, version, description, model_size, prompt_slug, tools, structured_output, is_active) values
  ('compliance-assistant', 'prod', 1, 'Conversational Q&A over a tenant''s obligations and documents',
   'medium', 'compliance-assistant-system', '["list_obligations", "get_document"]'::jsonb, null, true),
  ('obligation-extractor', 'prod', 1, 'Reads one document, writes its obligations as rows',
   'small', 'obligation-extractor-system', '[]'::jsonb, 'ObligationList', true)
on conflict (agent_ref, environment, version) do nothing;
