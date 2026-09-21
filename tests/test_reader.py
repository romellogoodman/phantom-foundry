"""The two-model reader: what counts as agreement, and word breaks from box gaps."""
from foundry.reader import OVERLAPPING, agree, parse_tokens, spaced


def test_parse_tokens():
    assert parse_tokens('{"tokens": ["A", "[fi]", "~"]}') == ["A", "[fi]", "~"]
    assert parse_tokens('```json\\n{"tokens": ["A"]}\\n```') == ["A"]
    assert parse_tokens(None) is None and parse_tokens("sorry") is None and parse_tokens('{"tokens": "AB"}') is None


def test_agreement_needs_every_model_and_the_box_count():
    assert agree([["A", "B"], ["A", "B"]], 2) == ["A", "B"]
    assert agree([["A", "B"], ["A", "8"]], 2) is None            # they differ
    assert agree([["A", "B"], ["A", "B"]], 3) is None            # same, but not one token per box
    assert agree([None, ["A", "B"]], 2) is None                  # one gave nothing


def test_word_breaks_come_back_from_the_gaps():
    box = lambda x: {"x": x, "w": 40, "h": 100}
    letters = [box(0), box(50), box(100), box(220), box(270)]    # a wide gap after the third box
    assert spaced(list("THEOX"), letters) == "THE OX"
    assert spaced(list("AB"), [box(0)]) == "A B"                 # boxes don't fit: fall back, never guess


def test_overlapping_series_are_left_alone():
    assert OVERLAPPING.search("Cloister Bold Italic") and OVERLAPPING.search("Typo Script")
    assert not OVERLAPPING.search("Italian Gothic".replace("Italian", "Latin"))
