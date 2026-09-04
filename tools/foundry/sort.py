"""sort — normalize traces into the face's UFO.

Glyphs printed on the same specimen line (same leaf + line) share a
baseline and a scale, exactly as they did on the page: the line's cap
height is the median ink height of its capitals, its baseline the median
ink bottom, and every glyph on it is scaled by the same factor and placed
where it actually sat. Round letters keep their overshoot, lowercase and
figures fall into place without being told where, and the four sizes of a
wood face each get their own scale so the font's cap height is the same
for all of them.

Per glyph: load the trace, map SVG units → cut-PNG pixels → page pixels →
font units, resolve overlaps and fix winding (counters punch), optionally
drop contours below `min_contour_area`, add sidebearings, write the glyph.
The UFO is the master source; svg/ is never edited. Glyphs not in the
manifest (e.g. constructed ones) are left alone.
"""

from __future__ import annotations

import hashlib
import statistics

import pathops
import ufoLib2
from fontTools.misc.transform import Transform
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.roundingPen import RoundingPen
from fontTools.pens.transformPen import TransformPen
from svgelements import SVG

from .face import Face, GlyphEntry, fname
from .outline import flatten, path_stats, signed_area, svg_to_path


def ufo_path(face: Face):
    return face.ufo / f"{face.name}.ufo"


def open_or_create_font(face: Face) -> ufoLib2.Font:
    p = ufo_path(face)
    return ufoLib2.Font.open(p) if p.exists() else ufoLib2.Font()


# -- line metrics ---------------------------------------------------------

def line_metrics(infos: list[dict]) -> dict:
    """Shared metrics for the glyphs printed at one size on a leaf, from their
    cut records. Capitals define the size; with none, the tallest lowercase
    (ascenders stand about cap high) do. Medians, so a speck stuck to one
    letter can't move the line. Each band the size was printed on gets its
    own baseline (`baselines`), since CAPITALS and Mixed case sit on two lines."""
    caps = [i for i in infos if i.get("category", "cap") == "cap"]
    if caps:
        cap_px, cap_source = statistics.median(i["ink_height_px"] for i in caps), "caps"
    else:
        lower = [i for i in infos if i.get("category") == "lower"] or infos
        tall = sorted((i["ink_height_px"] for i in lower), reverse=True)
        cap_px, cap_source = statistics.median(tall[:max(1, len(tall) // 3)]), "ascenders"
    baselines = {}
    for band in sorted({str(i.get("band") or "") for i in infos}):
        on = [i for i in infos if str(i.get("band") or "") == band]
        ref = [i for i in on if i.get("category", "cap") == "cap"] or on
        baselines[band] = statistics.median(i["tight_box_page"][3] for i in ref)
    m = {
        "n_caps": len(caps),
        "cap_height_px": cap_px,
        "cap_source": cap_source,
        "baseline_px": baselines[sorted(baselines)[0]],
        "baselines": baselines,
        "glyphs": [i["glyph"] for i in infos],
    }
    for cat, key in (("lower", "x_height_px"), ("figure", "figure_height_px")):
        sel = [i for i in infos if i.get("category") == cat]
        if sel:
            m[key] = statistics.median(i["ink_height_px"] for i in sel)
    stems = [i["stem_px"] for i in caps if i.get("stem_px")]
    if stems:
        m["stem_px"] = statistics.median(stems)
    return m


# -- placement ------------------------------------------------------------

def svg_doc_size(svg_file) -> tuple[float, float]:
    """The SVG's document size in the same units its path coordinates come
    back in (svgelements resolves `pt` to px), so cut_px / doc = SVG→pixel."""
    svg = SVG.parse(str(svg_file), reify=True, ppi=72)
    return float(svg.width), float(svg.height)


def glyph_transform(info: dict, doc_size: tuple[float, float], scale: float, baseline_px: float,
                    lsb: float) -> Transform:
    """SVG units → font units for a potrace trace of the cut PNG.

    SVG → cut pixels by the document size; cut pixels → page pixels by the
    cut's origin (tight box minus pad); page → font: x from the ink's left
    edge plus lsb, y up from the line's baseline, both times `scale`."""
    cut_w, cut_h = info["cut_size"]
    kx, ky = cut_w / doc_size[0], cut_h / doc_size[1]
    pad = info["pad"]
    tight_y0 = info["tight_box_page"][1]
    return Transform(kx * scale, 0, 0, -ky * scale,
                     lsb - pad * scale,
                     (baseline_px - tight_y0 + pad) * scale)


def place(path: pathops.Path, xform: Transform) -> pathops.Path:
    out = pathops.Path()
    path.draw(TransformPen(out.getPen(), xform))
    return pathops.simplify(out, fix_winding=True, clockwise=False)


def drop_small_contours(path: pathops.Path, min_area: float) -> tuple[pathops.Path, list[float]]:
    """Remove contours whose area is below min_area (font units²), e.g. paper
    specks. Returns the kept path and the areas dropped. min_area <= 0 keeps all."""
    if min_area <= 0:
        return path, []
    kept, dropped = pathops.Path(), []
    pen = kept.getPen()
    for c in path.contours:
        polys = flatten(c)
        area = abs(signed_area(polys[0])) if polys and len(polys[0]) >= 3 else 0.0
        if area < min_area:
            dropped.append(round(area, 1))
        else:
            c.draw(pen)
    return kept, dropped


def _fit_to_ink(path: pathops.Path, info: dict) -> Transform:
    """For traces whose coordinate space isn't the cut's (Arrow): map the
    trace's bounds onto the cut's ink box, uniformly by height."""
    l, t, r, b = path.bounds
    pad = info["pad"]
    k = info["ink_height_px"] / (b - t)
    return Transform(k, 0, 0, k, pad - l * k, pad - t * k)


# -- the stage ------------------------------------------------------------

def sort(face: Face, glyphs: list[str] | None = None, engine: str = "potrace") -> dict:
    face.ensure_layout()
    data = face.load()
    metrics = data.setdefault("metrics", {})
    upm = metrics.setdefault("upm", 1000)
    cap = metrics.setdefault("cap_height", 700)
    sb = metrics.setdefault("sidebearing", 40)
    min_area = metrics.setdefault("min_contour_area", 0)

    entries = face.read_manifest()
    groups: dict[str, list[GlyphEntry]] = {}
    for e in entries:
        groups.setdefault(e.group, []).append(e)
    lines = {}
    for key, es in groups.items():
        infos = [face.glyph_info(e.glyph) for e in es if (face.glyphs / f"{fname(e.glyph)}.json").exists()]
        if not infos:
            continue
        m = line_metrics(infos)
        m["scale"] = cap / m["cap_height_px"]
        if "stem_px" in m:
            m["stem_units"] = round(m["stem_px"] * m["scale"], 1)
        for key_px, key_units in (("x_height_px", "x_height"), ("figure_height_px", "figure_height")):
            if key_px in m:
                m[key_units] = round(m[key_px] * m["scale"])
        lines[key] = m
    data["lines"] = {k: {kk: (round(v, 5) if isinstance(v, float) else v) for kk, v in m.items()}
                     for k, m in lines.items()}
    xh = [m["x_height"] for m in lines.values() if "x_height" in m]
    if xh:
        metrics["x_height"] = int(statistics.median(xh))
    face.save(data)

    font = open_or_create_font(face)
    font.info.unitsPerEm = upm
    src_dir = face.svg_arrow if engine == "arrow" else face.svg_potrace
    if glyphs:
        entries = [e for e in entries if e.glyph in glyphs]

    results = []
    for e in entries:
        svg = src_dir / f"{fname(e.glyph)}.svg"
        if not svg.exists():
            continue
        info = face.glyph_info(e.glyph)
        m = lines[e.group]
        path = svg_to_path(svg)
        baseline = m["baselines"].get(str(e.band or ""), m["baseline_px"])
        if engine == "potrace":
            xform = glyph_transform(info, svg_doc_size(svg), m["scale"], baseline, sb)
        else:
            xform = glyph_transform(info, tuple(info["cut_size"]), m["scale"], baseline, sb) \
                .transform(_fit_to_ink(path, info))
        out = place(path, xform)
        out, dropped = drop_small_contours(out, min_area)
        l, b, r, t = out.bounds

        if e.glyph in font:
            del font[e.glyph]
        g = font.newGlyph(e.glyph)
        out.draw(Qu2CuPen(RoundingPen(g.getPen()), max_err=1.0, all_cubic=True))
        g.unicodes = [int(e.unicode, 16)] if e.unicode else []
        g.width = int(round(r + sb))
        stem_units = round(info["stem_px"] * m["scale"], 1) if info.get("stem_px") else None
        g.lib["com.phantomfoundry.sort"] = {
            "engine": engine, "source_svg": str(svg.relative_to(face.dir)),
            "source_sha256": hashlib.sha256(svg.read_bytes()).hexdigest(),
            "line": e.group, "band": e.band, "category": e.category, "scale": round(m["scale"], 5),
            "baseline_px": baseline, "cap_height_px": m["cap_height_px"],
            "alignment": "line: shared scale (cap_height / median cap ink height), shared baseline (median cap ink bottom)",
            "sidebearing": sb, "dropped_contours": dropped,
            **({"stem_units": stem_units} if stem_units is not None else {}),   # plist cannot hold None
        }
        rec = {"glyph": e.glyph, "engine": engine, "line": e.group, "category": e.category,
               "width": g.width, "bounds": [round(v) for v in (l, b, r, t)],
               "stem_units": stem_units, "dropped_contours": dropped, **path_stats(out),
               "scale": round(m["scale"], 5)}
        face.log_event("sort", **rec)
        results.append(rec)

    font.save(ufo_path(face), overwrite=True)
    return {"face": face.name, "ufo": str(ufo_path(face).relative_to(face.dir)),
            "lines": data["lines"], "sorted": results}
