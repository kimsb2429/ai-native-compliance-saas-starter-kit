from agent.main import _ThinkingFilter


def _run(chunks):
    f = _ThinkingFilter()
    return "".join(f.feed(c) for c in chunks)


def test_strips_whole_block():
    assert _run(["<thinking> plan </thinking>Answer."]) == "Answer."


def test_strips_block_split_across_chunks():
    assert _run(["Hi <thi", "nking>secret", " stuff</thin", "king> there"]) == "Hi  there"


def test_passes_plain_text_and_lone_angle():
    assert _run(["a < b and ", "c > d"]) == "a < b and c > d"
