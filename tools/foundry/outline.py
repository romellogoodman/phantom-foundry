"""Shared outline utilities: SVG → pathops.Path, flattening, rasterization."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pathops
from PIL import Image, ImageDraw
from svgelements import (SVG, Arc, Close, CubicBezier, Line, Move,
                         Path as SvgPath, QuadraticBezier, Shape)


def svg_to_path(svg_file: str | Path) -> pathops.Path:
    """Load every shape in an SVG (transforms applied) into one pathops.Path."""
    svg = SVG.parse(str(svg_file), reify=True, ppi=72)
    out = pathops.Path()
    pen = out.getPen()
    for el in svg.elements():
        if isinstance(el, SvgPath):
            p = el
        elif isinstance(el, Shape):
            p = SvgPath(el)
        else:
            continue
        p.reify()
        open_contour = False
        for seg in p.segments():
            if isinstance(seg, Move):
                if open_contour:
                    pen.closePath()
                pen.moveTo((seg.end.x, seg.end.y))
                open_contour = True
            elif isinstance(seg, Line):
                pen.lineTo((seg.end.x, seg.end.y))
            elif isinstance(seg, QuadraticBezier):
                pen.qCurveTo((seg.control.x, seg.control.y), (seg.end.x, seg.end.y))
            elif isinstance(seg, CubicBezier):
                pen.curveTo((seg.control1.x, seg.control1.y), (seg.control2.x, seg.control2.y),
                            (seg.end.x, seg.end.y))
            elif isinstance(seg, Arc):
                for c in seg.as_cubic_curves():
                    pen.curveTo((c.control1.x, c.control1.y), (c.control2.x, c.control2.y),
                                (c.end.x, c.end.y))
            elif isinstance(seg, Close):
                if open_contour:
                    pen.closePath()
                    open_contour = False
        if open_contour:
            pen.closePath()
    return out


def svg_viewbox(svg_file: str | Path) -> tuple[float, float, float, float] | None:
    svg = SVG.parse(str(svg_file), ppi=72)
    vb = getattr(svg, "viewbox", None)
    if vb is None:
        return None
    return (vb.x, vb.y, vb.width, vb.height)


def path_stats(path: pathops.Path) -> dict:
    contours = 0
    on, off = 0, 0
    for verb, pts in path.segments:
        if verb == "moveTo":
            contours += 1
            on += 1
        elif verb == "lineTo":
            on += 1
        elif verb == "qCurveTo":
            off += len(pts) - 1
            on += 1
        elif verb == "curveTo":
            off += 2
            on += 1
    return {"contours": contours, "on_curve": on, "off_curve": off, "points": on + off}


def flatten(path: pathops.Path, steps: int = 16) -> list[list[tuple[float, float]]]:
    """Flatten each contour to a polygon (list of points)."""
    polys: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    last = (0.0, 0.0)
    for verb, pts in path.segments:
        if verb == "moveTo":
            if cur:
                polys.append(cur)
            cur = [pts[0]]
            last = pts[0]
        elif verb == "lineTo":
            cur.append(pts[0])
            last = pts[0]
        elif verb == "qCurveTo":
            # pathops may emit implied on-curve points between multiple off-curves
            ctrls = list(pts[:-1])
            end = pts[-1]
            pts_seq = []
            p0 = last
            for i, c in enumerate(ctrls):
                if i < len(ctrls) - 1:
                    nxt = ctrls[i + 1]
                    mid = ((c[0] + nxt[0]) / 2, (c[1] + nxt[1]) / 2)
                    pts_seq.append((p0, c, mid))
                    p0 = mid
                else:
                    pts_seq.append((p0, c, end))
            for a, c, b in pts_seq:
                for k in range(1, steps + 1):
                    t = k / steps
                    x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t ** 2 * b[0]
                    y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t ** 2 * b[1]
                    cur.append((x, y))
            last = end
        elif verb == "curveTo":
            c1, c2, b = pts
            a = last
            for k in range(1, steps + 1):
                t = k / steps
                mt = 1 - t
                x = mt ** 3 * a[0] + 3 * mt ** 2 * t * c1[0] + 3 * mt * t ** 2 * c2[0] + t ** 3 * b[0]
                y = mt ** 3 * a[1] + 3 * mt ** 2 * t * c1[1] + 3 * mt * t ** 2 * c2[1] + t ** 3 * b[1]
                cur.append((x, y))
            last = b
        elif verb == "closePath":
            if cur:
                polys.append(cur)
                cur = []
    if cur:
        polys.append(cur)
    return polys


def signed_area(poly: list[tuple[float, float]]) -> float:
    a = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2


def rasterize(path: pathops.Path, size: tuple[int, int], transform=None) -> np.ndarray:
    """Nonzero-winding rasterization to a boolean ink mask of the given (w, h).

    transform: optional (sx, sy, tx, ty) applied as x*sx+tx, y*sy+ty before drawing.
    """
    w, h = size
    winding = np.zeros((h, w), dtype=np.int16)
    for poly in flatten(path):
        if len(poly) < 3:
            continue
        if transform:
            sx, sy, tx, ty = transform
            poly = [(x * sx + tx, y * sy + ty) for x, y in poly]
        layer = Image.new("L", (w, h), 0)
        ImageDraw.Draw(layer).polygon(poly, fill=1)
        sign = 1 if signed_area(poly) > 0 else -1
        winding += sign * np.asarray(layer, dtype=np.int16)
    return winding != 0


def bbox_of_mask(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
