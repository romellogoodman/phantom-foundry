"""justify: straight sides get the full sidebearing, deeper sides lose more, saturating."""

import pathops

from foundry.justify import sidebearings


def _shape(points):
    p = pathops.Path(); pen = p.getPen()
    pen.moveTo(points[0])
    for pt in points[1:]:
        pen.lineTo(pt)
    pen.closePath()
    return p


def test_straight_sides_get_full_value():
    box = _shape([(40, 0), (150, 0), (150, 700), (40, 700)])
    lsb, rsb, d = sidebearings(box, 700, straight=20, min_sb=-10, depth=25)
    assert (lsb, rsb) == (20, 20)
    assert d["depth_left"] < 1 and d["depth_right"] < 1


def test_sloping_side_loses_but_saturates():
    # straight left side; right edge slopes 100 units over the height → mean depth ≈ 50
    wedge = _shape([(40, 0), (250, 0), (150, 700), (40, 700)])
    lsb, rsb, d = sidebearings(wedge, 700, straight=20, min_sb=-10, depth=25)
    assert lsb == 20
    assert 40 < d["depth_right"] < 60
    assert -5 <= rsb <= 0                    # lost ~22 of a possible 25, not 50


def test_deeper_side_loses_more_but_never_past_depth():
    t = pathops.Path()
    for pts in ([(40, 600), (280, 600), (280, 700), (40, 700)], [(105, 0), (215, 0), (215, 600), (105, 600)]):
        _shape(pts).draw(t.getPen())
    lsb, rsb, d = sidebearings(t, 700, straight=20, min_sb=-10, depth=25)
    assert d["depth_left"] > 50
    assert lsb == rsb and -4 <= lsb <= -1   # 20 − 25·(1 − e^(−~2.2)) ≈ −2
    lsb2, _, _ = sidebearings(t, 700, straight=20, min_sb=0, depth=25)
    assert lsb2 == 0                          # the floor wins
