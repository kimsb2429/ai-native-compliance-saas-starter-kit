-- Schema for the AI-native compliance management saas platform starter kit.
--
-- Two kinds of table live here:
--   * tenant tables   (organizations, documents, obligations) — protected by
--     row-level security keyed on the transaction-local setting app.org_id.
--   * platform tables (prompts, prompt_revisions, agent_definitions) — shared
--     by every tenant; they are the "agents as rows" (A3) and "prompt registry"
--     (A26) spines. No RLS: there is nothing tenant-specific in them.
--
-- Everything is one pool, one role. Isolation comes from the policy below plus
-- FORCE ROW LEVEL SECURITY, which makes the table owner obey it too.
--
-- Two roles exist on purpose:
--   * the owner/admin role runs this file and the seed (migrations);
--   * kit_app is what the runtime connects as. It is a plain LOGIN role with
--     NOBYPASSRLS. Superusers and BYPASSRLS roles ignore RLS entirely, so the
--     runtime must never hold one. scripts/seed.py creates kit_app.

create table if not exists organizations (
  id          uuid primary key,
  slug        text not null unique,
  name        text not null,
  created_at  timestamptz not null default now()
);

create table if not exists documents (
  id          uuid primary key default gen_random_uuid(),
  org_id      uuid not null references organizations(id),
  title       text not null,
  kind        text not null check (kind in ('permit', 'regulation', 'policy')),
  body        text not null,
  created_at  timestamptz not null default now()
);

create table if not exists obligations (
  id                uuid primary key default gen_random_uuid(),
  org_id            uuid not null references organizations(id),
  document_id       uuid references documents(id) on delete cascade,
  citation          text,
  requirement       text not null,
  frequency         text,          -- e.g. monthly, quarterly, annual, on-event
  responsible_party text,
  due_rule          text,          -- plain-language due rule, e.g. "by March 1"
  created_at        timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Row-level security. The application sets app.org_id once per transaction:
--   select set_config('app.org_id', '<uuid>', true);   -- true = local to txn
-- and every statement in that transaction sees only that tenant's rows.
-- nullif(...) turns an unset setting into NULL, which matches no row.
-- ---------------------------------------------------------------------------
alter table documents   enable row level security;
alter table documents   force  row level security;
alter table obligations enable row level security;
alter table obligations force  row level security;

drop policy if exists tenant_isolation on documents;
create policy tenant_isolation on documents
  using      (org_id = nullif(current_setting('app.org_id', true), '')::uuid)
  with check (org_id = nullif(current_setting('app.org_id', true), '')::uuid);

drop policy if exists tenant_isolation on obligations;
create policy tenant_isolation on obligations
  using      (org_id = nullif(current_setting('app.org_id', true), '')::uuid)
  with check (org_id = nullif(current_setting('app.org_id', true), '')::uuid);

create index if not exists obligations_org_doc on obligations (org_id, document_id);
create index if not exists documents_org       on documents (org_id);

-- ---------------------------------------------------------------------------
-- Prompt registry (A26, kit form). A slug names a prompt; revisions are
-- immutable rows; exactly one revision per slug is active. A revision may
-- carry a model id (a Bedrock id or the alias MODEL_SMALL / MODEL_MEDIUM);
-- when it does, "swap the model" and "edit the prompt" are the same kind of
-- change: insert a row, flip is_active. When it is null, the agent row's
-- model_size decides. No redeploy either way.
-- ---------------------------------------------------------------------------
create table if not exists prompts (
  slug        text primary key,
  description text
);

create table if not exists prompt_revisions (
  slug          text not null references prompts(slug),
  revision      int  not null,
  model_id      text,                -- null = use the agent row's model_size; set = this revision overrides it
  system_text   text not null,
  user_template text,            -- optional; {{document}} style holes rendered by the app
  is_active     boolean not null default false,
  created_at    timestamptz not null default now(),
  primary key (slug, revision)
);
create unique index if not exists one_active_revision_per_slug
  on prompt_revisions (slug) where is_active;

-- ---------------------------------------------------------------------------
-- Agent definitions (A3, kit form). One row = one agent. The runtime builds a
-- live Strands Agent from the active row at invoke time; one image serves
-- every row. Adding an agent is an INSERT.
-- ---------------------------------------------------------------------------
create table if not exists agent_definitions (
  agent_ref         text not null,
  environment       text not null default 'prod',
  version           int  not null default 1,
  description       text,
  model_size        text not null check (model_size in ('small', 'medium')),
  prompt_slug       text not null references prompts(slug),
  tools             jsonb not null default '[]'::jsonb,   -- ["list_obligations", "get_document"]
  structured_output text,                                  -- null | 'ObligationList'
  is_active         boolean not null default true,
  created_at        timestamptz not null default now(),
  primary key (agent_ref, environment, version)
);
create unique index if not exists one_active_definition
  on agent_definitions (agent_ref, environment) where is_active;

-- ---------------------------------------------------------------------------
-- Grants for the runtime role. scripts/seed.py creates kit_app (LOGIN,
-- NOBYPASSRLS) with a real password before running this file, because managed
-- Postgres services reject placeholder passwords at CREATE ROLE time.
-- ---------------------------------------------------------------------------
grant usage on schema public to kit_app;
grant select, insert, update, delete on all tables in schema public to kit_app;
alter default privileges in schema public grant select, insert, update, delete on tables to kit_app;
