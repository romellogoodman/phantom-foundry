"""cast — vectorize cut glyphs.

Two engines, always both:
  potrace  deterministic control trace, run locally here.
  arrow    Quiver's model, called by the driving agent through the Quiver MCP
           server; the returned SVG is ingested here so the run is logged with
           model id, task/creation ids, and the input's checksum.

`diff` compares the two traces against each other and against the scan.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .face import Face
from .outline import bbox_of_mask, path_stats, rasterize, svg_to_path, svg_viewbox

POTRACE_ARGS = ["--svg", "--turdsize", "2", "--alphamax", "1.0", "--opttolerance", "0.2"]


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _glyph_list(face: Face, glyphs: list[str] | None) -> list[str]:
    if glyphs:
        return glyphs
    return [e.glyph for e in face.read_manifest()]


def cast_potrace(face: Face, glyphs: list[str] | None = None) -> dict:
    face.ensure_layout()
    potrace = shutil.which("potrace")
    if not potrace:
        raise RuntimeError("potrace not found on PATH (brew install potrace)")
    version = subprocess.run([potrace, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    results = []
    for g in _glyph_list(face, glyphs):
        png = face.glyphs / f"{g}.png"
        pbm = face.svg_potrace / f"{g}.pbm"
        svg = face.svg_potrace / f"{g}.svg"
        Image.open(png).convert("1").save(pbm)
        t0 = time.time()
        subprocess.run([potrace, *POTRACE_ARGS, "-o", str(svg), str(pbm)], check=True)
        dt = time.time() - t0
        pbm.unlink()
        stats = path_stats(svg_to_path(svg))
        rec = {"glyph": g, "engine": "potrace", "version": version, "args": POTRACE_ARGS,
               "input": str(png.relative_to(face.dir)), "input_sha256": _sha256(png),
               "output": str(svg.relative_to(face.dir)), "seconds": round(dt, 3), **stats}
        face.log_event("cast", **rec)
        results.append(rec)
    return {"face": face.name, "cast": results}


def cast_arrow_ingest(face: Face, glyph: str, from_svg: str, model: str | None = None,
                      task_id: str | None = None, creation_id: str | None = None) -> dict:
    face.ensure_layout()
    src = Path(from_svg)
    png = face.glyphs / f"{glyph}.png"
    dest = face.svg_arrow / f"{glyph}.svg"
    shutil.copyfile(src, dest)
    stats = path_stats(svg_to_path(dest))
    rec = {"glyph": glyph, "engine": "arrow", "model": model, "task_id": task_id,
           "creation_id": creation_id, "input": str(png.relative_to(face.dir)),
           "input_sha256": _sha256(png), "output": str(dest.relative_to(face.dir)),
           "viewbox": svg_viewbox(dest), **stats}
    face.log_event("cast", **rec)
    return rec


def _fit_to_box(path, target_bbox: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    """Transform mapping the path's bounds onto target_bbox (uniform-ish: separate sx, sy)."""
    l, t, r, b = path.bounds
    tx0, ty0, tx1, ty1 = target_bbox
    sx = (tx1 - tx0) / (r - l)
    sy = (ty1 - ty0) / (b - t)
    return (sx, sy, tx0 - l * sx, ty0 - t * sy)


def diff(face: Face, glyphs: list[str] | None = None) -> dict:
    """Ink-mask comparison. Each trace is bbox-fitted onto the scan's ink bbox so
    the metric is shape fidelity, independent of how each engine framed its output."""
    results = []
    for g in _glyph_list(face, glyphs):
        png = face.glyphs / f"{g}.png"
        scan = np.asarray(Image.open(png).convert("L")) < 128
        size = (scan.shape[1], scan.shape[0])
        scan_bbox = bbox_of_mask(scan)
        masks = {}
        stats = {}
        for engine, d in (("potrace", face.svg_potrace), ("arrow", face.svg_arrow)):
            svg = d / f"{g}.svg"
            if not svg.exists():
                continue
            path = svg_to_path(svg)
            masks[engine] = rasterize(path, size, _fit_to_box(path, scan_bbox))
            stats[engine] = path_stats(path)

        def iou(a, b):
            return float((a & b).sum() / max(1, (a | b).sum()))

        rec = {"glyph": g, "scan_ink_px": int(scan.sum()), "engines": list(masks)}
        for e, m in masks.items():
            rec[f"{e}_iou_scan"] = round(iou(m, scan), 4)
            rec[f"{e}_ink_px"] = int(m.sum())
            rec[f"{e}_points"] = stats[e]["points"]
            rec[f"{e}_contours"] = stats[e]["contours"]
        if "potrace" in masks and "arrow" in masks:
            rec["arrow_iou_potrace"] = round(iou(masks["arrow"], masks["potrace"]), 4)
            rec["arrow_minus_potrace_px"] = int((masks["arrow"] & ~masks["potrace"]).sum())
            rec["potrace_minus_arrow_px"] = int((masks["potrace"] & ~masks["arrow"]).sum())
        face.log_event("diff", **rec)
        results.append(rec)
        (face.proofs / f"{g}_diff.json").write_text(json.dumps(rec, indent=2))
    return {"face": face.name, "diff": results}
