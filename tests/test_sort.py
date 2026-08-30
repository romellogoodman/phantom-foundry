"""sort: glyphs share their line's baseline and scale; counters keep opposite winding."""

import pathops
import pytest
from fontTools.misc.transform import Transform

from foundry.outline import flatten, signed_area
from foundry.sort import drop_small_contours, glyph_transform, line_metrics, place


def _box_with_counter():
    """An SVG-style (y-down) box 100 wide × 200 tall at (10,10) with a hole."""
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((10, 10)); pen.lineTo((110, 10)); pen.lineTo((110, 210)); pen.lineTo((10, 210)); pen.closePath()
    pen.moveTo((40, 60)); pen.lineTo((40, 160)); pen.lineTo((80, 160)); pen.lineTo((80, 60)); pen.closePath()
    return p


def _info(**over):
    # a cut whose ink is 100×200 px with pad 10, sitting on page row 1200
    base = {"glyph": "H", "category": "cap", "cut_size": [120, 220], "pad": 10,
            "tight_box_page": [500, 1000, 600, 1200], "ink_height_px": 200, "ink_width_px": 100, "stem_px": 20}
    base.update(over)
    return base


def test_line_metrics_uses_caps_medians():
    infos = [_info(glyph="H"), _info(glyph="O", ink_height_px=204, tight_box_page=[700, 998, 800, 1202]),
             _info(glyph="E", ink_height_px=201, tight_box_page=[900, 1000, 1000, 1201]),
             _info(glyph="a", category="lower", ink_height_px=140)]
    m = line_metrics(infos)
    assert m["n_caps"] == 3
    assert m["cap_height_px"] == 201 and m["baseline_px"] == 1201
    assert m["x_height_px"] == 140
    assert m["stem_px"] == 20


def test_line_metrics_falls_back_to_all_glyphs():
    m = line_metrics([_info(category="figure", ink_height_px=150)])
    assert m["n_caps"] == 1 and m["cap_height_px"] == 150


def test_glyph_transform_puts_ink_on_baseline_at_cap_height():
    info = _info()
    # SVG doc is the cut at 1.333× (pt units), so kx = ky = 0.75
    xform = glyph_transform(info, (160, 293.333), scale=3.5, baseline_px=1200, lsb=40)
    # ink's top-left in SVG units: pad 10 px → 13.333; ink bottom: 210 px → 280
    x, y = xform.transformPoint((13.3333, 13.3333))
    assert (x, y) == pytest.approx((40, 700), abs=0.05)
    x, y = xform.transformPoint((13.3333, 280))
    assert (x, y) == pytest.approx((40, 0), abs=0.05)


def test_glyph_on_a_line_keeps_its_own_position():
    """A glyph that sits 20 px above the line's baseline stays 20 px × scale above it."""
    info = _info(tight_box_page=[500, 980, 600, 1180])
    xform = glyph_transform(info, (120, 220), scale=2.0, baseline_px=1200, lsb=0)
    _, y = xform.transformPoint((10, 210))          # ink bottom, SVG == pixels here
    assert y == pytest.approx(40)


def test_place_outer_ccw_counter_cw():
    out = place(_box_with_counter(), Transform(1, 0, 0, -1, 0, 220))
    areas = sorted((signed_area(poly) for poly in flatten(out)), key=abs, reverse=True)
    assert areas[0] > 0     # outer contour counter-clockwise (UFO/PostScript convention)
    assert areas[1] < 0     # counter runs the other way, so it punches through


def test_drop_small_contours_removes_specks_only():
    p = _box_with_counter()
    pen = p.getPen()
    pen.moveTo((150, 150)); pen.lineTo((153, 150)); pen.lineTo((153, 153)); pen.closePath()   # a 4.5 unit² speck
    out = place(p, Transform(1, 0, 0, -1, 0, 220))
    kept, dropped = drop_small_contours(out, min_area=50)
    assert len(dropped) == 1 and dropped[0] < 50
    assert len(list(kept.contours)) == 2
    same, none = drop_small_contours(out, min_area=0)
    assert none == [] and len(list(same.contours)) == 3
