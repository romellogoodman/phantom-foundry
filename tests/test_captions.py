"""Captions: the BB&S style names the series in every caption; most later
American books name it once in the page heading and caption sizes alone."""
from foundry.book import leaf_furniture, parse_bare_caption, parse_caption


def _line(text, y0, h=30, x0=100):
    words = [{"text": t, "box": [x0 + 60 * i, y0, x0 + 60 * i + 50, y0 + h]} for i, t in enumerate(text.split())]
    return {"text": text, "x0": x0, "y0": y0, "x1": x0 + 60 * len(words), "y1": y0 + h, "words": words}


def test_named_caption_is_not_bare():
    text = "4 A 7a 42 Point Cadillac Condensed 8¾ lbs., $5.25"
    assert parse_caption(text)["series"] == "Cadillac Condensed"
    assert parse_bare_caption(text) is None


def test_size_only_captions():
    for text, size in [("36 POINT", 36), ("48 Point 3 A $4 15 6a $3 85 $8 00", 48),
                       ("6 Point Font |2 00 28 A |0 85 58 a $1 15", 6), ("24 Point No. 70", 24)]:
        assert parse_caption(text) is None
        assert parse_bare_caption(text)["size"] == size


def test_name_ends_at_a_dash():
    assert parse_caption("24 Point Unique Celtic— Two-Line Pica. $4.05")["series"] == "Unique Celtic"


def test_heading_names_the_series_of_bare_captions():
    ocr = {"size": [2800, 4000], "lines": [
        _line("AMERICAN TYPE FOUNDERS COMPANY", 120, h=37), _line("FLORENTINE HEAVYFACE", 280, h=72),
        _line("4 A 5 a $7 75", 440), _line("36 POINT", 1320), _line("24 POINT", 2040)]}
    caps = leaf_furniture(ocr)["captions"]
    assert [(c["size"], c["series"]) for c in caps] == [(36, "Florentine Heavyface"), (24, "Florentine Heavyface")]


def test_a_page_with_named_captions_keeps_bare_ones_as_boundaries():
    ocr = {"size": [2800, 4000], "lines": [
        _line("LINING GOTHIC", 200, h=70), _line("48 Point Lining Gothic No. 117", 600), _line("48 Point", 1500)]}
    f = leaf_furniture(ocr)
    assert [c["series"] for c in f["captions"]] == ["Lining Gothic No. 117"]
    assert any(b["text"] == "48 Point" for b in f["blockers"])
