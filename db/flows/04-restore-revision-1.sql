update prompt_revisions set is_active = false where slug = 'compliance-assistant-system';
update prompt_revisions set is_active = true  where slug = 'compliance-assistant-system' and revision = 1;
