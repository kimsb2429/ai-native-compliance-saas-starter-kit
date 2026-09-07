-- Flow 04: a second revision of the assistant prompt, flipped active. No redeploy.
insert into prompt_revisions (slug, revision, model_id, system_text, user_template, is_active)
values ('compliance-assistant-system', 2, 'MODEL_MEDIUM',
'You are a compliance assistant for one organization. Use the tools to read obligations.
Answer as a numbered checklist only: one line per obligation, formatted "<citation> | <frequency> | <requirement>". No prose before or after the list.',
null, false)
on conflict (slug, revision) do nothing;
update prompt_revisions set is_active = false where slug = 'compliance-assistant-system';
update prompt_revisions set is_active = true  where slug = 'compliance-assistant-system' and revision = 2;
