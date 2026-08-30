"""justify — set each glyph's sidebearings (typefounding: justifying the matrix).

The specimen is the evidence. Wood type is set solid, so the gap between
two printed letters is the sum of their blocks' shoulders; `survey` measured
those gaps and `justify` takes its target from them. The rule is the usual
one for spacing by eye, made mechanical: a straight side gets the full
target, a side that curves or slopes away gets less, in proportion to how
much white it already brings — measured as the mean depth of the ink edge
from the glyph's extreme over the cap height.

  sb = straight − depth·(1 − e^(−mean_depth/depth)),  floored at `min`

Constructed glyphs are spaced the same way. Kerning stays a human pass.
"""

from __future__ import annotations

import math

import numpy as np
import pathops
import ufoLib2
from fontTools.pens.transformPen import TransformPen

from .face import Face
from .outline import rasterize
from .sort import ufo_path

DEFAULTS = {"straight": 20, "min": -10, "depth": 25}


def side_depths(path: pathops.Path, cap: float, step: int = 4) -> tuple[float, float]:
    """Mean distance from the glyph's left/right extreme to its ink edge,
    sampled over rows from baseline to cap (white the side already carries).
    Extremes are taken from the raster itself so edge rounding cancels."""
    l, b, r, t = path.bounds
    w = int(r - l) + 4
    h = int(cap) + 2
    mask = rasterize(path, (w, h), (1, -1, -l + 2, cap + 1))   # y-up units → rows
    rows = [np.nonzero(mask[row])[0] for row in range(1, h - 1, step)]
    rows = [xs for xs in rows if len(xs)]
    if not rows:
        return 0.0, 0.0
    xmin = min(int(xs.min()) for xs in rows)
    xmax = max(int(xs.max()) for xs in rows)
    left = [int(xs.min()) - xmin for xs in rows]
    right = [xmax - int(xs.max()) for xs in rows]
    return float(np.mean(left)), float(np.mean(right))


def sidebearings(path: pathops.Path, cap: float, straight: float, min_sb: float, depth: float) -> tuple[int, int, dict]:
    """A side loses sidebearing for the white it already carries, saturating:
    loss = depth × (1 − e^(−mean_depth/depth)). A flat stem loses nothing, a
    bowl a little, an open side (T, L's right, A's legs) at most `depth`."""
    dl, dr = side_depths(path, cap)
    def sb(d):
        loss = depth * (1 - math.exp(-d / depth)) if depth > 0 else 0
        return int(round(max(min_sb, straight - loss)))
    return sb(dl), sb(dr), {"depth_left": round(dl, 1), "depth_right": round(dr, 1)}


def printed_gaps(face: Face, data: dict) -> dict:
    """Median gap between adjacent printed letters on each labeled specimen
    line, in font units (survey boxes × the line's sort scale; word gaps skipped)."""
    import json
    lines = data.get("lines", {})
    out = {}
    for rec in face.read_log("label"):
        if "text" not in rec:
            continue
        sp = face.specimens / f"leaf{rec['leaf']:04d}_survey.json"
        key = f"{rec['leaf']}:{rec['line']}"
        if not sp.exists() or key not in lines:
            continue
        band = next((b for b in json.loads(sp.read_text())["lines"] if b["band"] == rec["band"]), None)
        if band is None:
            continue
        words = rec["text"].split()
        word_breaks, n = set(), 0
        for w in words[:-1]:
            n += len(w); word_breaks.add(n)
        scale = lines[key]["scale"]
        L = band["letters"]
        gaps = [(L[i + 1]["x"] - (L[i]["x"] + L[i]["w"])) * scale
                for i in range(len(L) - 1) if (i + 1) not in word_breaks]
        if gaps:
            out[key] = round(float(np.median(gaps)), 1)
    return out


def justify(face: Face, glyphs: list[str] | None = None) -> dict:
    data = face.load()
    cap = data["metrics"]["cap_height"]
    spacing = dict(data["metrics"].get("spacing") or {})
    gaps = printed_gaps(face, data)
    if "straight" not in spacing and gaps:
        # half the median printed gap: two straight sides meeting should reproduce the specimen
        spacing["straight"] = int(round(float(np.median(list(gaps.values()))) / 2))
        spacing["basis"] = "derived: half the median printed letter gap across the specimen lines"
    spacing["printed_gaps"] = gaps
    params = {**DEFAULTS, **spacing}
    data["metrics"]["spacing"] = params
    face.save(data)
    font = ufoLib2.Font.open(ufo_path(face))
    results = []
    for g in font:
        if glyphs and g.name not in glyphs:
            continue
        if g.name in (".notdef", "space") or not len(g):
            continue
        path = pathops.Path()
        g.draw(path.getPen())
        l, b, r, t = path.bounds
        lsb, rsb, depths = sidebearings(path, cap, params["straight"], params["min"], params["depth"])
        moved = pathops.Path()
        path.draw(TransformPen(moved.getPen(), (1, 0, 0, 1, lsb - l, 0)))
        g.clearContours()
        moved.draw(g.getPen())
        g.width = int(round((r - l) + lsb + rsb))
        g.lib["com.phantomfoundry.justify"] = {"lsb": lsb, "rsb": rsb, **depths, "params": params}
        rec = {"glyph": g.name, "lsb": lsb, "rsb": rsb, "width": g.width, **depths}
        face.log_event("justify", **rec)
        results.append(rec)
    if "space" in font:
        font["space"].width = int(round(params.get("word", 0.25 * data["metrics"]["upm"])))
    font.save(ufo_path(face), overwrite=True)
    return {"face": face.name, "params": params, "justified": results}
