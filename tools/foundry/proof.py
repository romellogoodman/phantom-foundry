"""proof — render proofs into proofs/.

  <glyph>_overlay.png   scan (gray) + potrace (cyan) + arrow (magenta); black = all agree
  <glyph>_traces.png    scan | potrace | arrow, side by side
  waterfall.png         the compiled font rendered at a range of sizes (FreeType via Pillow)
  index.html            everything above, plus diff metrics and provenance
"""

from __future__ import annotations

import html
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .cast import _fit_to_box
from .face import Face
from .outline import bbox_of_mask, rasterize, svg_to_path


def _masks(face: Face, glyph: str):
    scan = np.asarray(Image.open(face.glyphs / f"{glyph}.png").convert("L")) < 128
    size = (scan.shape[1], scan.shape[0])
    bbox = bbox_of_mask(scan)
    out = {"scan": scan}
    for engine, d in (("potrace", face.svg_potrace), ("arrow", face.svg_arrow)):
        svg = d / f"{glyph}.svg"
        if svg.exists():
            path = svg_to_path(svg)
            out[engine] = rasterize(path, size, _fit_to_box(path, bbox))
    return out


def overlay_image(masks: dict) -> Image.Image:
    scan = masks["scan"]
    h, w = scan.shape
    rgb = np.full((h, w, 3), 255, dtype=np.uint8)
    rgb[scan] = (190, 190, 190)
    pot = masks.get("potrace")
    arr = masks.get("arrow")
    if pot is not None:
        rgb[pot] = (0, 150, 210)
    if arr is not None:
        rgb[arr] = (225, 0, 130)
    if pot is not None and arr is not None:
        rgb[pot & arr] = (40, 40, 40)
    return Image.fromarray(rgb)


def traces_image(masks: dict) -> Image.Image:
    panels = [k for k in ("scan", "potrace", "arrow") if k in masks]
    h, w = masks["scan"].shape
    gap = 20
    sheet = Image.new("RGB", (len(panels) * (w + gap) + gap, h + 2 * gap + 30), "white")
    d = ImageDraw.Draw(sheet)
    for i, k in enumerate(panels):
        m = masks[k]
        im = Image.fromarray(np.where(m, 0, 255).astype(np.uint8))
        x = gap + i * (w + gap)
        sheet.paste(im, (x, gap + 30))
        d.text((x, gap), k, fill="black")
    return sheet


def waterfall_image(face: Face, text: str, sizes=(36, 48, 72, 96, 144, 220)) -> Image.Image | None:
    fonts = sorted(face.dist.glob("*.otf")) + sorted(face.dist.glob("*.ttf"))
    if not fonts:
        return None
    lines = []
    for s in sizes:
        f = ImageFont.truetype(str(fonts[0]), s)
        l, t, r, b = f.getbbox(text)
        lines.append((f, s, r - l, b - t, t))
    W = max(x[2] for x in lines) + 80
    H = sum(x[3] + 24 for x in lines) + 40
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    y = 20
    for f, s, w, h, t in lines:
        d.text((40, y - t), text, font=f, fill="black")
        d.text((4, y), str(s), fill=(150, 150, 150))
        y += h + 24
    return im


def proof(face: Face) -> dict:
    face.ensure_layout()
    data = face.load()
    entries = face.read_manifest()
    made = []
    diffs = {}
    for e in entries:
        masks = _masks(face, e.glyph)
        overlay_image(masks).save(face.proofs / f"{e.glyph}_overlay.png")
        traces_image(masks).save(face.proofs / f"{e.glyph}_traces.png")
        made += [f"{e.glyph}_overlay.png", f"{e.glyph}_traces.png"]
        dj = face.proofs / f"{e.glyph}_diff.json"
        if dj.exists():
            diffs[e.glyph] = json.loads(dj.read_text())
    text = "".join(chr(int(e.unicode, 16)) for e in entries if e.unicode)
    wf = waterfall_image(face, text)
    if wf is not None:
        wf.save(face.proofs / "waterfall.png")
        made.append("waterfall.png")

    fonts = sorted(p.name for p in face.dist.glob("*.otf"))
    src = data.get("source", {})
    parts = [f"<h1>{html.escape(data.get('title') or face.name)}</h1>"]
    if fonts:
        parts.append(f"<style>@font-face{{font-family:'Revival';src:url('../dist/{fonts[0]}')}}"
                     ".rv{font-family:'Revival';line-height:1;margin:.2em 0}</style>")
        for s in (48, 96, 160, 320):
            parts.append(f"<div class='rv' style='font-size:{s}px'>{html.escape(text)}</div>")
    parts.append("<h2>Proofs</h2>")
    for m in made:
        parts.append(f"<figure><img src='{m}' style='max-width:100%'><figcaption>{m}</figcaption></figure>")
    if diffs:
        parts.append("<h2>Trace comparison</h2><pre>" + html.escape(json.dumps(diffs, indent=2)) + "</pre>")
    parts.append("<h2>Provenance</h2><pre>" + html.escape(json.dumps(src, indent=2, default=str)) + "</pre>")
    (face.proofs / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Proof — " + html.escape(face.name) + "</title>"
        "<body style='font-family:system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem'>" + "\n".join(parts))
    made.append("index.html")
    face.log_event("proof", made=made)
    return {"face": face.name, "proofs": made}
