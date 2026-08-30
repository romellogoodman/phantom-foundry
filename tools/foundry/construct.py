"""construct — draw the letters no specimen shows, from the ones it does.

A revival from an incomplete showing has to make up the rest. Here that is
done in the open: each constructed glyph is a recipe in
faces/<face>/construct.yaml — a short stack of operations on parts of the
traced glyphs (E without its bottom arm is F; M upside down is W) and plain
geometry measured from them (a stroke of the A's leg thickness). The recipe
is the record; the glyph carries it in its lib and face.json flags it
`constructed`, so a made-up Z can never pass for a traced one.

Operations (each combines with the running shape by `mode`: add | subtract | intersect):
  glyph:  NAME  [dx, dy, flip_y, flip_x]   a traced (or already constructed) glyph
  rect:   [x0, y0, x1, y1]
  poly:   [[x, y], ...]
  stroke: {from: [x, y], to: [x, y], thickness: T}   parallelogram, T measured horizontally
  clip:   [x0, y0, x1, y1]                            shorthand for rect + intersect
Then the shape is shifted so its left ink edge sits at the face's sidebearing.
"""

from __future__ import annotations

import pathops
import ufoLib2
import yaml
from fontTools.misc.transform import Transform
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.roundingPen import RoundingPen
from fontTools.pens.transformPen import TransformPen

from .face import Face
from .outline import path_stats
from .sort import drop_small_contours, ufo_path


def _ccw(points):
    """Every primitive is drawn counter-clockwise (positive area) so shapes add
    under nonzero winding instead of cancelling where they overlap."""
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))
    return points if area > 0 else list(reversed(points))


def _poly(points) -> pathops.Path:
    pts = _ccw([tuple(pt) for pt in points])
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo(pts[0])
    for pt in pts[1:]:
        pen.lineTo(pt)
    pen.closePath()
    return p


def _rect(x0, y0, x1, y1) -> pathops.Path:
    return _poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _stroke(a, b, thickness) -> pathops.Path:
    h = thickness / 2
    return _poly([(a[0] - h, a[1]), (a[0] + h, a[1]), (b[0] + h, b[1]), (b[0] - h, b[1])])


def _glyph(font: ufoLib2.Font, name: str, cap: float, dx=0, dy=0, flip_y=False, flip_x=False) -> pathops.Path:
    src = pathops.Path()
    font[name].draw(src.getPen())
    l, b, r, t = src.bounds
    xf = Transform(1, 0, 0, 1, dx, dy)
    if flip_y:
        xf = xf.transform(Transform(1, 0, 0, -1, 0, cap))        # about the cap height
    if flip_x:
        xf = xf.transform(Transform(-1, 0, 0, 1, l + r, 0))      # about the glyph's own center
    out = pathops.Path()
    src.draw(TransformPen(out.getPen(), xf))
    # a flip reverses orientation; re-fix so outer contours stay counter-clockwise
    return pathops.simplify(out, fix_winding=True, clockwise=False)


def _combine(acc: pathops.Path | None, shape: pathops.Path, mode: str) -> pathops.Path:
    if acc is None:
        if mode != "add":
            raise ValueError("the first operation must add a shape")
        return shape
    out = pathops.Path()
    if mode == "add":
        pathops.union([acc, shape], out.getPen(), clockwise=False)
    elif mode == "subtract":
        pathops.difference([acc], [shape], out.getPen(), clockwise=False)
    elif mode == "intersect":
        pathops.intersection([acc], [shape], out.getPen(), clockwise=False)
    else:
        raise ValueError(f"unknown mode {mode!r}")
    return out


def build_one(font: ufoLib2.Font, ops: list[dict], cap: float, lsb: float) -> tuple[pathops.Path, list[str]]:
    acc, sources = None, []
    for op in ops:
        mode = op.get("mode", "add")
        if "glyph" in op:
            sources.append(op["glyph"])
            shape = _glyph(font, op["glyph"], cap, op.get("dx", 0), op.get("dy", 0),
                           op.get("flip_y", False), op.get("flip_x", False))
        elif "rect" in op:
            shape = _rect(*op["rect"])
        elif "poly" in op:
            shape = _poly(op["poly"])
        elif "stroke" in op:
            s = op["stroke"]
            shape = _stroke(s["from"], s["to"], s["thickness"])
        elif "clip" in op:
            shape, mode = _rect(*op["clip"]), "intersect"
        else:
            raise ValueError(f"unknown op {op!r}")
        acc = _combine(acc, shape, mode)
    acc = pathops.simplify(acc, fix_winding=True, clockwise=False)
    acc, _slivers = drop_small_contours(acc, 30)   # boolean-op slivers, not design
    l, b, r, t = acc.bounds
    out = pathops.Path()
    acc.draw(TransformPen(out.getPen(), Transform(1, 0, 0, 1, lsb - l, 0)))
    return out, sources


def construct(face: Face, glyphs: list[str] | None = None) -> dict:
    recipe_path = face.dir / "construct.yaml"
    if not recipe_path.exists():
        raise FileNotFoundError(f"no recipes: {recipe_path}")
    recipes = yaml.safe_load(recipe_path.read_text()) or {}
    data = face.load()
    cap, sb = data["metrics"]["cap_height"], data["metrics"].get("sidebearing", 40)
    font = ufoLib2.Font.open(ufo_path(face))
    results = []
    for name, r in recipes.items():
        if glyphs and name not in glyphs:
            continue
        path, sources = build_one(font, r["ops"], cap, sb)
        if name in font:
            del font[name]
        g = font.newGlyph(name)
        # pathops can hand back quadratics; the UFO/CFF wants cubics
        path.draw(Qu2CuPen(RoundingPen(g.getPen()), max_err=1.0, all_cubic=True))
        uni = r.get("unicode") or (f"{ord(name):04X}" if len(name) == 1 else None)
        g.unicodes = [int(uni, 16)] if uni else []
        l, b, rr, t = path.bounds
        g.width = int(round(rr + sb))
        g.lib["com.phantomfoundry.construct"] = {
            "from": sorted(set(sources)), "note": r.get("note", ""), "ops": r["ops"],
            "category": r.get("category", "cap"),
            "reason": "not shown in the source specimen; built from the traced letters",
        }
        rec = {"glyph": name, "from": sorted(set(sources)), "width": g.width,
               "bounds": [round(v) for v in (l, b, rr, t)], **path_stats(path), "note": r.get("note", "")}
        face.log_event("construct", **rec)
        results.append(rec)
    font.save(ufo_path(face), overwrite=True)
    return {"face": face.name, "constructed": results}
