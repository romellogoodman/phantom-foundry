"""audit — is each cut the letter its label says?

A wrong label on a good outline is the worst error a strike can carry: the
trace is faithful, the font is wrong. Two checks, both inside one face, where
the design is constant:

- **siblings**: cuts that share a label (E at 72 pt, E.six, E.eight) should look
  alike once scaled to one size; a cut unlike its siblings is suspect.
- **strangers**: a cut that looks much more like the cuts of *another* label
  than like its own is suspect, unless the two letters are ones a face really
  draws alike (O and 0, I and l, c and C).

Similarity is the overlap (IoU) of the two ink masks, each cropped to its ink
and scaled to a square, times a penalty for differing proportions. Thresholds
were set on BB&S No. 9, whose readings are accepted (see `calibrate`).
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image

from .face import Face, fname

GRID = 32
# letters a face may legitimately draw alike: never flagged as strangers
ALIKE = [set("Il1|!"), set("O0oQ"), set("cC"), set("sS5"), set("vV"), set("wW"), set("xX"), set("zZ2"), set("uU"),
         set("kK"), set("pP"), set("yY"), set(".,'`:;"), set("-—–_"), set("6b"), set("9gq"), set("nu"), set("dp"), set("bq"),
         set("MW"), set("NZ"), set("un")]
SIBLING_FLOOR = 0.45      # a cut's mean likeness to its siblings, below which it is flagged
STRANGER_MARGIN = 0.20    # how much more a cut must resemble another label than its own
STRANGER_MIN = 0.70       # and how strongly it must resemble that other label


def label_of(glyph: str) -> str:
    return glyph.split(".")[0] if not glyph.startswith(".") else glyph


def _mask(path: Path) -> tuple[np.ndarray, float] | None:
    try:
        a = np.asarray(Image.open(path).convert("L")) < 128
    except OSError:
        return None
    ys, xs = np.where(a)
    if len(ys) < 20:
        return None
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    aspect = a.shape[1] / a.shape[0]
    im = Image.fromarray((a * 255).astype("uint8")).resize((GRID, GRID), Image.BILINEAR)
    return np.asarray(im) > 127, aspect


def likeness(a, b) -> float:
    (ma, ra), (mb, rb) = a, b
    union = np.logical_or(ma, mb).sum()
    iou = np.logical_and(ma, mb).sum() / union if union else 0.0
    return float(iou * (min(ra, rb) / max(ra, rb)) ** 0.5)


def _alike(x: str, y: str) -> bool:
    return any(x in s and y in s for s in ALIKE)


def audit(face: Face) -> dict:
    """{'cuts': n, 'pairs': sibling likenesses, 'flags': [...]} for one face."""
    if not face.manifest_path.exists():
        return {"cuts": 0, "pairs": [], "flags": []}
    rows = list(csv.DictReader(face.manifest_path.open()))
    cuts = {}
    for r in rows:
        m = _mask(face.glyphs / f"{fname(r['glyph'])}.png")
        if m is not None:
            cuts[r["glyph"]] = (label_of(r["glyph"]), m, r)
    names = list(cuts)
    flags, pairs = [], []
    for g in names:
        lab, m, r = cuts[g]
        if len(lab) != 1:
            continue                                   # ligatures and named glyphs: no fair comparison
        sib = [likeness(m, cuts[o][1]) for o in names if o != g and cuts[o][0] == lab]
        own = float(np.mean(sib)) if sib else None
        if sib:
            pairs.append(own)
            if own < SIBLING_FLOOR:
                flags.append({"glyph": g, "check": "unlike its siblings", "likeness": round(own, 2), "siblings": len(sib),
                              "leaf": r["leaf"], "line": r["line"], "band": r["band"]})
        best, who = 0.0, None
        for o in names:
            ol = cuts[o][0]
            if ol == lab or len(ol) != 1 or _alike(lab, ol):
                continue
            s = likeness(m, cuts[o][1])
            if s > best:
                best, who = s, o
        ref = max(sib) if sib else 0.0
        if who and best >= STRANGER_MIN and best - ref >= STRANGER_MARGIN and sib:
            flags.append({"glyph": g, "check": f"looks more like {label_of(who)}", "likeness": round(best, 2),
                          "own": round(ref, 2), "leaf": r["leaf"], "line": r["line"], "band": r["band"]})
    return {"cuts": len(cuts), "pairs": pairs, "flags": flags}
