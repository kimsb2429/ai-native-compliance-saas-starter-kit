-- Flow 06: a third agent, added as one row. The prompt slug was seeded already.
insert into agent_definitions (agent_ref, environment, version, description, model_size, prompt_slug, tools)
values ('gap-checker', 'prod', 1, 'Ranks obligations by regulatory risk when evidence is missing',
        'medium', 'gap-checker-system', '["list_obligations"]'::jsonb)
on conflict (agent_ref, environment, version) do nothing;
