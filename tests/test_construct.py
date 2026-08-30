"""construct: primitives add under nonzero winding regardless of drawing direction; flips keep winding."""

import pathops
import ufoLib2

from foundry.construct import build_one
from foundry.outline import flatten, signed_area


def _font_with_box():
    font = ufoLib2.Font()
    g = font.newGlyph("I")
    pen = g.getPen()
    pen.moveTo((40, 0)); pen.lineTo((150, 0)); pen.lineTo((150, 700)); pen.lineTo((40, 700)); pen.closePath()
    g.width = 190
    return font


def _areas(path):
    return [signed_area(flatten(c)[0]) for c in path.contours]


def test_downward_stroke_adds_instead_of_cancelling():
    font = _font_with_box()
    ops = [{"glyph": "I"}, {"stroke": {"from": [100, 400], "to": [260, 0], "thickness": 90}}]
    path, sources = build_one(font, ops, cap=700, lsb=40)
    areas = _areas(path)
    assert sources == ["I"]
    assert len(areas) == 1 and areas[0] > 700 * 110       # one solid contour bigger than the stem alone


def test_subtract_and_clip():
    font = _font_with_box()
    ops = [{"glyph": "I"}, {"rect": [100, -10, 200, 200], "mode": "subtract"}, {"clip": [0, 0, 300, 600]}]
    path, _ = build_one(font, ops, cap=700, lsb=40)
    l, b, r, t = path.bounds
    assert (b, t) == (0, 600)
    assert abs(_areas(path)[0]) == 110 * 600 - 50 * 200


def test_flip_y_keeps_outer_contour_ccw_and_lsb():
    font = _font_with_box()
    g = font.newGlyph("L")
    pen = g.getPen()
    pen.moveTo((40, 0)); pen.lineTo((250, 0)); pen.lineTo((250, 100)); pen.lineTo((150, 100))
    pen.lineTo((150, 700)); pen.lineTo((40, 700)); pen.closePath()
    path, _ = build_one(font, [{"glyph": "L", "flip_y": True}], cap=700, lsb=40)
    l, b, r, t = path.bounds
    assert (l, b, t) == (40, 0, 700)
    assert _areas(path)[0] > 0                           # still counter-clockwise after the flip
    assert r == 250                                       # the foot is now at the top, same width
