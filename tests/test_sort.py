"""sort: ink height → cap height, baseline at ink bottom, counters keep opposite winding."""

import pathops
import pytest

from foundry.outline import flatten, signed_area
from foundry.sort import normalize


def _glyph_with_counter():
    p = pathops.Path()
    pen = p.getPen()
    # SVG-style y-down box 200 tall with a hole; outer drawn clockwise on screen
    pen.moveTo((10, 10)); pen.lineTo((110, 10)); pen.lineTo((110, 210)); pen.lineTo((10, 210)); pen.closePath()
    pen.moveTo((40, 60)); pen.lineTo((40, 160)); pen.lineTo((80, 160)); pen.lineTo((80, 60)); pen.closePath()
    return p


def test_normalize_scales_to_cap_height_and_baseline():
    out, meta = normalize(_glyph_with_counter(), cap_height=700, sidebearing=40)
    l, b, r, t = out.bounds
    assert (b, t) == pytest.approx((0, 700))
    assert l == pytest.approx(40)
    assert meta["scale"] == pytest.approx(3.5)
    assert r - l == pytest.approx(350)


def test_normalize_outer_ccw_counter_cw():
    out, _ = normalize(_glyph_with_counter(), cap_height=700, sidebearing=40)
    areas = sorted((signed_area(poly) for poly in flatten(out)), key=abs, reverse=True)
    assert areas[0] > 0     # outer contour counter-clockwise (UFO/PostScript convention)
    assert areas[1] < 0     # counter runs the other way, so it punches through
