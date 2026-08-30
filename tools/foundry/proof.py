"""proof — render proofs into proofs/.

  <glyph>_overlay.png   scan (gray) + potrace (cyan) + arrow (magenta); black = all agree
  <glyph>_traces.png    scan | potrace | arrow, side by side
  cuts.png              every cut glyph at a common height, in manifest order
  line_<leaf>_<line>.png the specimen line as printed, and re-set in the compiled font
  waterfall.png         the compiled font at a range of sizes (FreeType via Pillow)
  face.json             everything the website needs: provenance, metrics, glyphs, attempts
  index.html            the above, browsable
"""

from __future__ import annotations

import html
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

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


def cuts_image(face: Face, entries, height: int = 220) -> Image.Image | None:
    tiles = []
    for e in entries:
        p = face.glyphs / f"{e.glyph}.png"
        if p.exists():
            im = Image.open(p)
            tiles.append((e.glyph, im.resize((max(1, int(im.width * height / im.height)), height))))
    if not tiles:
        return None
    gap = 24
    sheet = Image.new("L", (sum(t.width + gap for _, t in tiles) + gap, height + 50), 255)
    d = ImageDraw.Draw(sheet)
    x = gap
    for g, t in tiles:
        sheet.paste(t, (x, 30))
        d.text((x, 8), g, fill=0)
        x += t.width + gap
    return sheet


def _font_file(face: Face):
    fonts = sorted(face.dist.glob("*.otf")) + sorted(face.dist.glob("*.ttf"))
    return fonts[0] if fonts else None


def _coverage(font_path, text: str) -> tuple[list[str], list[str]]:
    cmap = TTFont(font_path).getBestCmap()
    chars = [c for c in text if not c.isspace()]
    missing = sorted({c for c in chars if ord(c) not in cmap})
    return chars, missing


def specimen_line_image(face: Face, sl: dict, font_path, width: int = 1600) -> tuple[Image.Image, dict]:
    """The line as printed (from the survey band) over the same text set in
    the compiled font at matching cap height. Characters the font doesn't
    have yet render as .notdef boxes — the proof says what's missing."""
    survey = json.loads((face.specimens / f"leaf{sl['leaf']:04d}_survey.json").read_text())
    band = next(b for b in survey["lines"] if b["band"] == sl["band"])
    page = Image.open(face.specimen_jp2(sl["leaf"])).convert("L")
    x0 = min(L["x"] for L in band["letters"]); x1 = max(L["x"] + L["w"] for L in band["letters"])
    margin = int(band["height"] * 0.15)
    crop = page.crop((max(0, x0 - margin), max(0, band["y0"] - margin),
                      min(page.width, x1 + margin), min(page.height, band["y1"] + margin)))
    scale = width / crop.width
    scan = crop.resize((width, int(crop.height * scale)))

    line_m = face.load().get("lines", {}).get(f"{sl['leaf']}:{sl['line']}", {})
    cap_px = line_m.get("cap_height_px", band["height"]) * scale
    upm_cap = face.load()["metrics"]["cap_height"] / face.load()["metrics"]["upm"]
    size = int(round(cap_px / upm_cap))
    f = ImageFont.truetype(str(font_path), size)
    l, t, r, b = f.getbbox(sl["text"])
    m = int(margin * scale)
    # the re-set line may run wider than the printed one (spacing is still
    # flat); widen the sheet rather than clip — the overrun is the proof
    text_w = max(width, r - l + 2 * m)
    text_im = Image.new("L", (text_w, b - t + 2 * m), 255)
    ImageDraw.Draw(text_im).text((m - l, m - t), sl["text"], font=f, fill=0)

    gap = 16
    sheet = Image.new("L", (text_w, scan.height + gap + text_im.height), 255)
    sheet.paste(scan, (0, 0))
    sheet.paste(text_im, (0, scan.height + gap))
    chars, missing = _coverage(font_path, sl["text"])
    return sheet, {"chars": len(chars), "missing": missing}


def waterfall_image(face: Face, text: str, sizes=(36, 48, 72, 96, 144, 220)) -> Image.Image | None:
    font = _font_file(face)
    if font is None:
        return None
    lines = []
    for s in sizes:
        f = ImageFont.truetype(str(font), s)
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


def arrow_attempts(face: Face, glyph: str | None = None) -> list[dict]:
    """Every Arrow attempt from the cast log, joined to the last diff record
    computed while it was the current cast (cast entries are ordered; a
    task_id can be ingested twice, which is one attempt)."""
    casts = [c for c in face.read_log("cast") if c.get("engine") == "arrow" and (glyph is None or c["glyph"] == glyph)]
    diffs = face.read_log("diff")
    attempts, seen = [], {}
    for c in casts:
        tid = c.get("task_id") or c["ts"]
        if tid in seen:
            seen[tid].update({k: c[k] for k in ("attempt", "kept_as") if k in c})
            continue
        seen[tid] = {"glyph": c["glyph"], "attempt": c.get("attempt"), "model": c.get("model"), "task_id": tid,
                     "creation_id": c.get("creation_id"), "input": c.get("input"), "input_sha256": c.get("input_sha256"),
                     "kept_as": c.get("kept_as"), "viewbox": c.get("viewbox"), "contours": c.get("contours"),
                     "points": c.get("points"), "ts": c["ts"]}
        attempts.append(seen[tid])
    for i, a in enumerate(attempts):
        t0 = a["ts"]
        t1 = attempts[i + 1]["ts"] if i + 1 < len(attempts) else "9999"
        window = [d for d in diffs if d["glyph"] == a["glyph"] and t0 <= d["ts"] < t1]
        if window:
            d = window[-1]
            a["iou_scan"] = d.get("arrow_iou_scan")
            a["best_region_iou_scan"] = d.get("arrow_best_region_iou_scan")
            a["regions"] = d.get("arrow_regions")
            a["potrace_iou_scan"] = d.get("potrace_iou_scan")
    return attempts


def face_json(face: Face, data: dict, entries, made: list[str], line_proofs: list[dict]) -> dict:
    from .matrix import family_name
    from .sort import ufo_path
    import ufoLib2
    font = ufoLib2.Font.open(ufo_path(face)) if ufo_path(face).exists() else None
    glyphs = []
    manifest_names = {e.glyph: e for e in entries}
    if font is not None:
        for name in sorted(font.keys()):
            g = font[name]
            lib = g.lib.get("com.phantomfoundry.sort", {})
            con = g.lib.get("com.phantomfoundry.construct", {})
            e = manifest_names.get(name)
            base = name.split(".")[0]
            rec = {"name": name, "unicode": f"{g.unicodes[0]:04X}" if g.unicodes else None,
                   "char": chr(g.unicodes[0]) if g.unicodes else None,
                   "encoded": bool(g.unicodes), "alternate_of": base if "." in name and base in font else None,
                   "width": g.width, "category": e.category if e else lib.get("category") or con.get("category"),
                   "line": e.line if e else None, "engine": lib.get("engine"),
                   "constructed": bool(con), "construct": con or None,
                   "stem_units": lib.get("stem_units"), "dropped_contours": lib.get("dropped_contours")}
            dj = face.proofs / f"{name}_diff.json"
            if dj.exists():
                rec["diff"] = json.loads(dj.read_text())
            if e:
                info = face.glyph_info(name)
                rec["cut"] = {k: info[k] for k in ("tight_box_page", "ink_height_px", "ink_width_px", "stem_px", "components")}
            glyphs.append(rec)
    return {
        "name": face.name, "family": family_name(face, data), "version": data.get("version"),
        "status": data.get("status"), "title": data.get("title"),
        "source": data.get("source", {}), "metrics": data.get("metrics", {}), "lines": data.get("lines", {}),
        "specimen_lines": line_proofs, "glyphs": glyphs,
        "arrow_attempts": arrow_attempts(face),
        "fonts": sorted(p.name for p in face.dist.glob("*.[ot]tf")),
        "proofs": made,
    }


def proof(face: Face) -> dict:
    face.ensure_layout()
    data = face.load()
    entries = face.read_manifest()
    made = []
    for e in entries:
        if not (face.glyphs / f"{e.glyph}.png").exists():
            continue
        masks = _masks(face, e.glyph)
        overlay_image(masks).save(face.proofs / f"{e.glyph}_overlay.png")
        traces_image(masks).save(face.proofs / f"{e.glyph}_traces.png")
        made += [f"{e.glyph}_overlay.png", f"{e.glyph}_traces.png"]
    cs = cuts_image(face, entries)
    if cs is not None:
        cs.save(face.proofs / "cuts.png")
        made.append("cuts.png")

    font_path = _font_file(face)
    line_proofs = []
    for sl in data.get("specimen_lines", []):
        rec = dict(sl)
        if font_path is not None and (face.specimens / f"leaf{sl['leaf']:04d}_survey.json").exists():
            im, cov = specimen_line_image(face, sl, font_path)
            name = f"line_{sl['leaf']}_{sl['line']}.png"
            im.save(face.proofs / name)
            made.append(name)
            rec.update(cov, proof=name)
        line_proofs.append(rec)
    covered = [r["text"] for r in line_proofs if r.get("missing") == []]
    wf_text = max(covered, key=len) if covered else "".join(e.char for e in entries if e.char)
    wf = waterfall_image(face, wf_text)
    if wf is not None:
        wf.save(face.proofs / "waterfall.png")
        made.append("waterfall.png")

    fj = face_json(face, data, entries, made, line_proofs)
    (face.proofs / "face.json").write_text(json.dumps(fj, indent=2, default=str))
    made.append("face.json")

    src = data.get("source", {})
    parts = [f"<h1>{html.escape(fj['family'])} <small>v{fj['version']} · {fj['status']}</small></h1>"]
    if fj["fonts"]:
        parts.append(f"<style>@font-face{{font-family:'Revival';src:url('../dist/{fj['fonts'][0]}')}}"
                     ".rv{font-family:'Revival';line-height:1;margin:.2em 0}</style>")
        for s in (48, 96, 160, 320):
            parts.append(f"<div class='rv' style='font-size:{s}px'>{html.escape(wf_text)}</div>")
    parts.append("<h2>Specimen lines</h2>")
    for r in line_proofs:
        if r.get("proof"):
            note = "complete" if not r["missing"] else "missing " + " ".join(r["missing"])
            parts.append(f"<figure><img src='{r['proof']}' style='max-width:100%'>"
                         f"<figcaption>{html.escape(r['text'])} — {r['line']}-line — {note}</figcaption></figure>")
    parts.append("<h2>Cuts</h2><img src='cuts.png' style='max-width:100%'>")
    parts.append("<h2>Traces</h2>")
    for m in made:
        if m.endswith("_overlay.png"):
            parts.append(f"<figure style='display:inline-block'><img src='{m}' style='height:220px'><figcaption>{m}</figcaption></figure>")
    parts.append("<h2>Arrow attempts</h2><pre>" + html.escape(json.dumps(fj["arrow_attempts"], indent=2)) + "</pre>")
    parts.append("<h2>Lines</h2><pre>" + html.escape(json.dumps(fj["lines"], indent=2)) + "</pre>")
    parts.append("<h2>Provenance</h2><pre>" + html.escape(json.dumps(src, indent=2, default=str)) + "</pre>")
    (face.proofs / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Proof — " + html.escape(face.name) + "</title>"
        "<body style='font-family:system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem'>" + "\n".join(parts))
    made.append("index.html")
    face.log_event("proof", made=made, specimen_lines=[{k: r.get(k) for k in ("line", "text", "missing")} for r in line_proofs])
    return {"face": face.name, "proofs": made, "specimen_lines": line_proofs}
