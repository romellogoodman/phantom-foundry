"""sort — normalize traces into the face's UFO.

For each glyph: load the chosen engine's SVG, resolve overlaps and fix winding
(counters punch), scale so the glyph's ink height equals the face's cap height
(caps-only assumption for now — recorded per glyph), flip SVG's y-down to
font y-up, set the baseline at the ink bottom, add sidebearings, and write the
glyph into ufo/<face>.ufo. The UFO is the master source; svg/ is never edited.
"""

from __future__ import annotations

import hashlib

import pathops
import ufoLib2
from fontTools.misc.transform import Transform
from fontTools.pens.roundingPen import RoundingPen
from fontTools.pens.transformPen import TransformPen

from .face import Face
from .outline import path_stats, svg_to_path


def ufo_path(face: Face):
    return face.ufo / f"{face.name}.ufo"


def open_or_create_font(face: Face) -> ufoLib2.Font:
    p = ufo_path(face)
    return ufoLib2.Font.open(p) if p.exists() else ufoLib2.Font()


def normalize(path: pathops.Path, cap_height: float, sidebearing: float) -> tuple[pathops.Path, dict]:
    clean = pathops.simplify(path, fix_winding=True, clockwise=False)
    l, t, r, b = clean.bounds
    scale = cap_height / (b - t)
    # x' = (x - l)*s + sb ; y' = (b - y)*s   (flip y, baseline at ink bottom)
    xform = Transform(scale, 0, 0, -scale, sidebearing - l * scale, b * scale)
    out = pathops.Path()
    clean.draw(TransformPen(out.getPen(), xform))
    out = pathops.simplify(out, fix_winding=True, clockwise=False)  # y-flip reversed orientation
    meta = {"scale": scale, "source_bounds": [l, t, r, b], "ink_width_units": (r - l) * scale}
    return out, meta


def sort(face: Face, glyphs: list[str] | None = None, engine: str = "potrace") -> dict:
    face.ensure_layout()
    data = face.load()
    metrics = data.setdefault("metrics", {})
    upm = metrics.setdefault("upm", 1000)
    cap = metrics.setdefault("cap_height", 700)
    sb = metrics.setdefault("sidebearing", 40)
    face.save(data)

    font = open_or_create_font(face)
    font.info.unitsPerEm = upm
    src_dir = face.svg_arrow if engine == "arrow" else face.svg_potrace
    entries = face.read_manifest()
    if glyphs:
        entries = [e for e in entries if e.glyph in glyphs]

    results = []
    for e in entries:
        svg = src_dir / f"{e.glyph}.svg"
        path = svg_to_path(svg)
        out, meta = normalize(path, cap, sb)
        if e.glyph in font:
            del font[e.glyph]
        g = font.newGlyph(e.glyph)
        out.draw(RoundingPen(g.getPen()))
        g.unicodes = [int(e.unicode, 16)] if e.unicode else []
        g.width = int(round(meta["ink_width_units"] + 2 * sb))
        g.lib["com.phantomfoundry.sort"] = {
            "engine": engine, "source_svg": str(svg.relative_to(face.dir)),
            "source_sha256": hashlib.sha256(svg.read_bytes()).hexdigest(),
            "scale": meta["scale"], "alignment": "cap: ink height -> cap_height, baseline = ink bottom",
            "sidebearing": sb,
        }
        rec = {"glyph": e.glyph, "engine": engine, "width": g.width, **path_stats(out),
               "scale": round(meta["scale"], 5)}
        face.log_event("sort", **rec)
        results.append(rec)

    font.save(ufo_path(face), overwrite=True)
    return {"face": face.name, "ufo": str(ufo_path(face).relative_to(face.dir)), "sorted": results}
