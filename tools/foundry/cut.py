"""cut — punchcutting: crop individual glyphs out of specimen scans.

The manifest gives a rough box per glyph (page pixel coords). cut binarizes
that region, flood-fills the ink component nearest the box center, and
tightens the crop to that component. Two files are kept per glyph:

  glyphs/<glyph>_raw.png   the untouched grayscale crop (the specimen)
  glyphs/<glyph>.png       the binarized, isolated glyph on white (the cut)
  glyphs/<glyph>.json      tight bbox in page coords, threshold, ink stats
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from .face import Face, GlyphEntry


def otsu_threshold(im: Image.Image) -> int:
    hist = im.histogram()
    total = sum(hist)
    sum_all = sum(i * h for i, h in enumerate(hist))
    sum_b = 0.0
    w_b = 0
    best_t, best_var = 128, -1.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return best_t


def find_seed(binary: Image.Image, cx: int, cy: int, max_r: int = 400) -> tuple[int, int]:
    """Spiral outward from (cx, cy) to the nearest ink pixel."""
    px = binary.load()
    w, h = binary.size
    if px[cx, cy] == 0:
        return cx, cy
    for r in range(1, max_r):
        for dx in range(-r, r + 1):
            for dy in (-r, r):
                x, y = cx + dx, cy + dy
                if 0 <= x < w and 0 <= y < h and px[x, y] == 0:
                    return x, y
        for dy in range(-r + 1, r):
            for dx in (-r, r):
                x, y = cx + dx, cy + dy
                if 0 <= x < w and 0 <= y < h and px[x, y] == 0:
                    return x, y
    raise RuntimeError("no ink found near box center")


def cut_glyph(face: Face, entry: GlyphEntry, pad_frac: float = 0.06) -> dict:
    page = Image.open(face.specimen_jp2(entry.leaf)).convert("L")
    box = (entry.x, entry.y, entry.x + entry.w, entry.y + entry.h)
    raw = page.crop(box)
    raw.save(face.glyphs / f"{entry.glyph}_raw.png")

    t = otsu_threshold(raw)
    binary = raw.point(lambda v: 0 if v < t else 255).convert("L")

    seed = find_seed(binary, raw.width // 2, raw.height // 2)
    work = binary.copy()
    ImageDraw.floodfill(work, seed, 128, thresh=0)
    component = work.point(lambda v: 255 if v == 128 else 0)  # component -> white
    bbox = component.getbbox()
    if bbox is None:
        raise RuntimeError(f"empty component for {entry.glyph}")

    x0, y0, x1, y1 = bbox
    pad = int(round((y1 - y0) * pad_frac))
    out_w, out_h = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad
    cut = Image.new("L", (out_w, out_h), 255)
    mask = component.crop(bbox)
    ink = Image.new("L", mask.size, 0)
    cut.paste(ink, (pad, pad), mask)
    cut.save(face.glyphs / f"{entry.glyph}.png")

    ink_px = sum(1 for v in mask.getdata() if v == 255)
    info = {
        "glyph": entry.glyph, "unicode": entry.unicode, "leaf": entry.leaf,
        "rough_box": list(box),
        "tight_box_page": [entry.x + x0, entry.y + y0, entry.x + x1, entry.y + y1],
        "pad": pad, "cut_size": [out_w, out_h],
        "threshold": t, "seed": [entry.x + seed[0], entry.y + seed[1]],
        "ink_pixels": ink_px, "ink_height_px": y1 - y0, "ink_width_px": x1 - x0,
    }
    (face.glyphs / f"{entry.glyph}.json").write_text(json.dumps(info, indent=2))
    face.log_event("cut", **info)
    return info


def cut(face: Face, glyphs: list[str] | None = None) -> dict:
    face.ensure_layout()
    entries = face.read_manifest()
    if glyphs:
        entries = [e for e in entries if e.glyph in glyphs]
    return {"face": face.name, "cut": [cut_glyph(face, e) for e in entries]}
