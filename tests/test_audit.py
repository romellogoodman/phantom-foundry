"""The label audit: a cut unlike its siblings, or more like another letter's cuts, is flagged."""
import csv

import numpy as np
from PIL import Image

from foundry.audit import audit, label_of, likeness, _mask
from foundry.face import Face, fname


def _draw(path, shape, size=120):
    a = np.full((size, size), 255, dtype="uint8")
    if shape == "bar":                       # an I: a tall stem
        a[10:110, 50:70] = 0
    elif shape == "ring":                    # an O
        yy, xx = np.mgrid[:size, :size]
        r = np.hypot(yy - 60, xx - 60)
        a[(r < 50) & (r > 32)] = 0
    elif shape == "ell":                     # an L
        a[10:110, 20:40] = 0
        a[90:110, 20:100] = 0
    Image.fromarray(a).resize((size * 2, size * 2) if path.stem.endswith("big") else (size, size)).save(path)


def _face(tmp_path, monkeypatch, cuts):
    import foundry.face as face_mod
    monkeypatch.setattr(face_mod, "FACES_DIR", tmp_path)
    f = Face("t")
    f.glyphs.mkdir(parents=True)
    with f.manifest_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["glyph", "unicode", "leaf", "line", "band", "category", "x", "y", "w", "h", "notes"])
        for glyph, shape in cuts:
            w.writerow([glyph, "", 1, "72pt", 1, "cap", 0, 0, 1, 1, ""])
            _draw(f.glyphs / f"{fname(glyph)}.png", shape)
    return f


def test_label_of():
    assert label_of("E.six") == "E" and label_of("a.30pt_2") == "a" and label_of("O") == "O"


def test_same_shape_at_two_sizes_is_alike(tmp_path):
    _draw(tmp_path / "a.png", "ell")
    _draw(tmp_path / "a_big.png", "ell")
    assert likeness(_mask(tmp_path / "a.png"), _mask(tmp_path / "a_big.png")) > 0.9


def test_a_mislabeled_cut_is_flagged(tmp_path, monkeypatch):
    f = _face(tmp_path, monkeypatch, [("L", "ell"), ("L.six", "ell"), ("L.eight", "ring"),      # an O filed as an L
                                      ("O", "ring"), ("O.six", "ring"), ("H", "bar")])
    flags = audit(f)["flags"]
    assert {x["glyph"] for x in flags} == {"L.eight"}
    assert any(x["check"] == "looks more like O" for x in flags)


def test_clean_face_has_no_flags(tmp_path, monkeypatch):
    f = _face(tmp_path, monkeypatch, [("L", "ell"), ("L.six", "ell"), ("O", "ring"), ("O.six", "ring")])
    assert audit(f)["flags"] == []


def test_an_unread_face_is_skipped_not_failed(tmp_path, monkeypatch):
    import foundry.face as face_mod
    from foundry.build import build
    monkeypatch.setattr(face_mod, "FACES_DIR", tmp_path)
    f = Face("unread-face")
    f.glyphs.mkdir(parents=True)
    f.manifest_path.write_text("glyph,unicode,leaf,line,band,category,x,y,w,h,notes\n")
    assert build(f) == {"face": "unread-face", "ran": [], "skipped": [], "unread": True, "seconds": 0.0}
