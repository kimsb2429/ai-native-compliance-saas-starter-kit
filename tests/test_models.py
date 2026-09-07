from agent.models import Obligation


def test_null_strings_become_none():
    o = Obligation(citation="1.1", requirement="Do it.", frequency="ongoing", responsible_party="null", due_rule="")
    assert o.responsible_party is None and o.due_rule is None
