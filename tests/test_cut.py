"""cut: stem measurement and the survey/label conventions."""

import numpy as np

from foundry.cut import _runs, category_of, main_component, stacked_piece, stem_width_px


def test_runs():
    assert _runs(np.array([0, 1, 1, 0, 1, 0, 0, 1], dtype=bool)) == [(1, 3), (4, 5), (7, 8)]
    assert _runs(np.zeros(4, dtype=bool)) == []


def test_stem_width_ignores_bars():
    """An E: 20-px stem, full-width bars top/middle/bottom. The stem wins."""
    m = np.zeros((100, 60), dtype=bool)
    m[:, :20] = True                      # stem
    m[0:10, :] = m[45:55, :] = m[90:100, :] = True   # bars
    assert stem_width_px(m) == 20


def test_stem_width_round_letter_reads_sides():
    """An O-ish ring: sides 15 px; the closed top/bottom rows are wide."""
    m = np.zeros((100, 80), dtype=bool)
    m[:, :15] = m[:, 65:] = True
    m[0:12, :] = m[88:100, :] = True
    assert stem_width_px(m) == 15


def test_category_of():
    assert category_of("A") == "cap" and category_of("a") == "lower"
    assert category_of("8") == "figure" and category_of("&") == "punct"


def test_stacked_piece_dot_yes_speck_no():
    assert stacked_piece((0, 40), (60, 300), piece_px=800, main_px=12000)     # dot above the stem
    assert not stacked_piece((250, 262), (60, 300), piece_px=70, main_px=15000)  # speck beside the o
    assert not stacked_piece((310, 322), (60, 300), piece_px=70, main_px=15000)  # speck under the letter
    assert stacked_piece((100, 200), (60, 300), piece_px=1000, main_px=12000)  # broken stroke, 8%


def test_main_component_is_the_letter_not_the_speck_at_center():
    """A U-shaped letter with a speck inside its counter (at the box center)
    and a neighbor's stem poking in at the right edge: the U wins."""
    m = np.zeros((100, 80), dtype=bool)
    m[10:90, 10:20] = m[10:90, 50:60] = m[80:90, 10:60] = True     # the U
    m[48:52, 33:37] = True                                         # speck at the center
    m[0:100, 76:80] = True                                         # neighbor at the right edge
    comp, seed = main_component(m)
    assert comp[85, 30] and not comp[50, 35] and not comp[50, 78]
    assert comp.sum() == m[10:90, 10:60].sum() - 16                    # the U alone, minus the speck
