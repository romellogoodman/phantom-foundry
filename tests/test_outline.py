"""Outline parsing and rasterization: the geometry the whole pipeline rests on."""

import numpy as np
import pathops
import pytest

from foundry.outline import bbox_of_mask, flatten, path_stats, rasterize, signed_area, svg_to_path

RECT_WITH_HOLE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<g transform="translate(0,100) scale(1,-1)">
<path d="M10 10 H90 V90 H10 Z M30 30 V70 H70 V30 Z"/>
</g></svg>"""


@pytest.fixture
def hole_svg(tmp_path):
    p = tmp_path / "hole.svg"
    p.write_text(RECT_WITH_HOLE)
    return p


def test_svg_to_path_applies_group_transform(hole_svg):
    path = svg_to_path(hole_svg)
    l, t, r, b = path.bounds
    assert (l, t, r, b) == pytest.approx((10, 10, 90, 90))
    assert path_stats(path)["contours"] == 2


def test_rasterize_punches_counter(hole_svg):
    mask = rasterize(svg_to_path(hole_svg), (100, 100))
    assert mask[50, 20]           # in the frame
    assert not mask[50, 50]       # inside the hole
    x0, y0, x1, y1 = bbox_of_mask(mask)          # PIL polygon fill is edge-inclusive
    assert (x0, y0) == (10, 10) and 90 <= x1 <= 91 and 90 <= y1 <= 91
    assert 6400 - 1600 - 400 < mask.sum() < 6400 - 1600 + 400


def test_signed_area_sign_flips_with_orientation():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert signed_area(sq) == 100
    assert signed_area(list(reversed(sq))) == -100


def test_flatten_samples_curves():
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((0, 0)); pen.curveTo((0, 10), (10, 10), (10, 0)); pen.closePath()
    polys = flatten(p, steps=8)
    assert len(polys) == 1 and len(polys[0]) == 1 + 8
