"""proof — render proofs into proofs/.

  <glyph>_overlay.png   scan (gray) + potrace (cyan) + arrow (magenta); black = all agree
  <glyph>_traces.png    scan | potrace | arrow, side by side
  cuts.png              every cut glyph at a common height, in manifest order
  line_<leaf>_<line>_b<band>.jpg  the specimen line as printed, and re-set in the compiled font
  waterfall.png         the compiled font at a range of sizes (FreeType via Pillow)
  checks.json           automatic warnings: low trace overlap, specks, a capital off its
                        line's cap height, too many contours, unread bands, too few glyphs
  face.json             everything the website needs: provenance, metrics, glyphs, attempts, checks
  index.html            the above, browsable
"""

from __future__ import annotations

import html
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

from .cast import _fit_to_box
from .face import Face, fname
from .outline import bbox_of_mask, rasterize, svg_to_path


def _masks(face: Face, glyph: str):
    """Ink masks of the cut and of each trace, in the cut's pixel frame. The
    potrace trace is of this very PNG, so it maps by document size — fitting
    it to the ink's bbox would stretch a trace that dropped a speck. Arrow
    draws in its own frame and is bbox-fitted, as `diff` does."""
    from .sort import svg_doc_size
    scan = np.asarray(Image.open(face.glyphs / f"{fname(glyph)}.png").convert("L")) < 128
    size = (scan.shape[1], scan.shape[0])
    bbox = bbox_of_mask(scan)
    out = {"scan": scan}
    for engine, d in (("potrace", face.svg_potrace), ("arrow", face.svg_arrow)):
        svg = d / f"{fname(glyph)}.svg"
        if svg.exists():
            path = svg_to_path(svg)
            if engine == "potrace":
                dw, dh = svg_doc_size(svg)
                out[engine] = rasterize(path, size, (size[0] / dw, size[1] / dh, 0, 0))
            else:
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
        p = face.glyphs / f"{fname(e.glyph)}.png"
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


def alphabet_image(face: Face, font_path, size: int = 200) -> Image.Image | None:
    """Every encoded glyph in code-point order, each labeled with where it came
    from: the specimen line it was traced from, or `constructed`."""
    import ufoLib2
    from .sort import ufo_path
    if not ufo_path(face).exists():
        return None
    font = ufoLib2.Font.open(ufo_path(face))
    encoded = sorted((g.unicodes[0], g.name) for g in font if g.unicodes and g.name not in ("space",))
    if not encoded:
        return None
    f = ImageFont.truetype(str(font_path), size)
    gap, label_h = 30, 26
    cells = []
    for cp, name in encoded:
        g = font[name]
        lib = g.lib.get("com.phantomfoundry.sort", {})
        con = g.lib.get("com.phantomfoundry.construct")
        label = "constructed" if con else lib.get("line", "").split(":")[-1] or "traced"
        w = max(f.getlength(chr(cp)), 60)
        cells.append((chr(cp), label, int(w), bool(con)))
    per_row = 9
    rows = [cells[i:i + per_row] for i in range(0, len(cells), per_row)]
    row_h = int(size * 1.15) + label_h + gap
    W = max(sum(c[2] + gap for c in r) for r in rows) + gap
    im = Image.new("RGB", (W, len(rows) * row_h + gap), "white")
    d = ImageDraw.Draw(im)
    asc = int(size * 0.98)
    for ri, r in enumerate(rows):
        x = gap
        y = gap + ri * row_h
        for ch, label, w, con in r:
            d.text((x, y), ch, font=f, fill=(120, 120, 120) if con else "black")
            d.text((x, y + asc + 8), label, fill=(200, 0, 100) if con else (120, 120, 120))
            x += w + gap
    return im


def _iou(a, b) -> float | None:
    union = (a | b).sum()
    return float((a & b).sum() / union) if union else None


def run_checks(face: Face, data: dict, entries, glyph_iou: dict, font) -> dict:
    """What a person would look for on the proof sheet, as pass/warn flags,
    so a hundred faces can be reviewed by reading the ones that warned."""
    items = []
    lines = data.get("lines", {})
    for e in entries:
        if not (face.glyphs / f"{fname(e.glyph)}.json").exists():
            continue
        info = face.glyph_info(e.glyph)
        iou = glyph_iou.get(e.glyph)
        # a trace's edge rounding costs a fixed band of pixels, so overlap falls
        # with size: 95% is right for a 400 px wood letter, 90% for a 30 pt cut
        cap_px = (lines.get(e.group) or {}).get("cap_height_px") or info["ink_height_px"]
        floor = 0.95 if cap_px >= 300 else 0.93 if cap_px >= 200 else 0.90
        if iou is not None and iou < floor:
            items.append({"level": "warn", "check": "trace_iou", "glyph": e.glyph, "value": round(iou, 3),
                          "note": f"potrace trace overlaps the scan by less than {int(floor * 100)}% (cap {int(cap_px)} px)"})
        if info.get("specks"):
            items.append({"level": "info", "check": "specks", "glyph": e.glyph, "value": len(info["specks"]),
                          "note": "marks beside the letter were recorded, not cut"})
        if info.get("components", 1) > 1 and e.category != "lower":
            items.append({"level": "info", "check": "pieces", "glyph": e.glyph, "value": info["components"],
                          "note": "the cut joined more than one ink component"})
        m = lines.get(e.group)
        if m and e.category == "cap" and e.glyph.split(".")[0] not in ("Q", "J"):
            dev = abs(info["ink_height_px"] - m["cap_height_px"]) / m["cap_height_px"]
            if dev > 0.12:
                items.append({"level": "warn", "check": "cap_height", "glyph": e.glyph, "value": round(dev, 3),
                              "note": "capital's ink height is off its line's cap height by more than 12% (misread box?)"})
        if font is not None and e.glyph in font:
            g = font[e.glyph]
            if len(g) > 4:
                items.append({"level": "warn", "check": "contours", "glyph": e.glyph, "value": len(g),
                              "note": "more than four contours; specks or a broken trace"})
            if g.width <= 0:
                items.append({"level": "warn", "check": "width", "glyph": e.glyph, "value": g.width, "note": "non-positive advance"})
    for key, m in lines.items():
        if m.get("cap_source") == "ascenders":
            items.append({"level": "info", "check": "cap_from_ascenders", "line": key,
                          "note": "no capitals at this size; cap height taken from the tallest lowercase"})
    labels = face.specimens / "labels.json"
    if labels.exists():
        for sk in json.loads(labels.read_text()).get("skipped", []):
            items.append({"level": "info" if "not type" in sk["why"] else "warn", "check": "unlabeled_band",
                          "leaf": sk["leaf"], "band": sk["band"], "note": sk["why"]})
    encoded = sum(1 for g in font if g.unicodes and g.name != "space") if font is not None else 0
    if encoded < 10:
        items.append({"level": "warn", "check": "few_glyphs", "value": encoded, "note": "fewer than ten encoded glyphs"})
    warns = sum(1 for i in items if i["level"] == "warn")
    return {"status": "warn" if warns else "ok", "warnings": warns,
            "infos": sum(1 for i in items if i["level"] == "info"), "encoded": encoded, "items": items}


def _font_file(face: Face):
    fonts = sorted(face.dist.glob("*.otf")) + sorted(face.dist.glob("*.ttf"))
    return fonts[0] if fonts else None


def _coverage(font_path, text: str) -> tuple[list[str], list[str]]:
    cmap = TTFont(font_path).getBestCmap()
    chars = [c for c in text if not c.isspace()]
    missing = sorted({c for c in chars if ord(c) not in cmap})
    return chars, missing


def specimen_line_image(face: Face, sl: dict, font_path, width: int = 1400) -> tuple[Image.Image, dict]:
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
    from .cut import printed_text
    text = printed_text(sl["text"])
    f = ImageFont.truetype(str(font_path), size)
    l, t, r, b = f.getbbox(text)
    m = int(margin * scale)
    # the re-set line may run wider than the printed one (spacing is still
    # flat); widen the sheet rather than clip — the overrun is the proof
    text_w = max(width, r - l + 2 * m)
    text_im = Image.new("L", (text_w, b - t + 2 * m), 255)
    ImageDraw.Draw(text_im).text((m - l, m - t), text, font=f, fill=0)

    gap = 16
    sheet = Image.new("L", (text_w, scan.height + gap + text_im.height), 255)
    sheet.paste(scan, (0, 0))
    sheet.paste(text_im, (0, scan.height + gap))
    chars, missing = _coverage(font_path, text)
    return sheet, {"chars": len(chars), "missing": missing, "printed": text}


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
    def current(rel):
        """Logged paths predate the UFO-style file names; point at the file that exists now."""
        if not rel or (face.dir / rel).exists():
            return rel
        parts = rel.split("/")
        base = parts[-1]
        stem = base.split("-")[0].split(".")[0]          # 'R' of 'R-01-....svg', 'R.png', 'R-sq768-m20.png'
        alt = "/".join(parts[:-1] + [fname(stem) + base[len(stem):]])
        return alt if (face.dir / alt).exists() else rel

    for a in attempts:
        a["input"], a["kept_as"] = current(a.get("input")), current(a.get("kept_as"))
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
            dj = face.proofs / f"{fname(name)}_diff.json"
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


def proof(face: Face, glyph_sheets: bool | None = None) -> dict:
    """Render the proofs. Per-glyph overlay/traces sheets are drawn for every
    glyph only when asked, or when the face has Arrow research to compare;
    a hundred faces' worth of them would be bulk, and the trace-vs-scan
    overlap they show is computed for the checks regardless."""
    face.ensure_layout()
    data = face.load()
    entries = face.read_manifest()
    made = []
    glyph_iou = {}
    if glyph_sheets is None:
        glyph_sheets = any(face.svg_arrow.glob("*.svg"))
    for e in entries:
        if not (face.glyphs / f"{fname(e.glyph)}.png").exists():
            continue
        masks = _masks(face, e.glyph)
        if "potrace" in masks:
            glyph_iou[e.glyph] = _iou(masks["scan"], masks["potrace"])
        if not (glyph_sheets or "arrow" in masks):
            continue
        overlay_image(masks).save(face.proofs / f"{fname(e.glyph)}_overlay.png")
        traces_image(masks).save(face.proofs / f"{fname(e.glyph)}_traces.png")
        made += [f"{fname(e.glyph)}_overlay.png", f"{fname(e.glyph)}_traces.png"]
    cs = cuts_image(face, entries)
    if cs is not None:
        cs.save(face.proofs / "cuts.png")
        made.append("cuts.png")

    font_path = _font_file(face)
    if font_path is not None:
        ab = alphabet_image(face, font_path)
        if ab is not None:
            ab.save(face.proofs / "alphabet.png")
            made.append("alphabet.png")
    line_proofs = []
    for sl in data.get("specimen_lines", []):
        rec = dict(sl)
        if font_path is not None and (face.specimens / f"leaf{sl['leaf']:04d}_survey.json").exists():
            im, cov = specimen_line_image(face, sl, font_path)
            name = f"line_{sl['leaf']}_{sl['line']}" + (f"_b{sl['band']}" if "band" in sl else "") + ".jpg"
            im.convert("L").save(face.proofs / name, quality=85)
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
    import ufoLib2
    from .sort import ufo_path
    ufo_font = ufoLib2.Font.open(ufo_path(face)) if ufo_path(face).exists() else None
    checks = run_checks(face, data, entries, glyph_iou, ufo_font)
    (face.proofs / "checks.json").write_text(json.dumps(checks, indent=2))
    made.append("checks.json")
    for g in fj["glyphs"]:
        if g["name"] in glyph_iou:
            g["trace_iou"] = round(glyph_iou[g["name"]], 4)
    fj["checks"] = {k: checks[k] for k in ("status", "warnings", "infos", "encoded")}
    fj["series"] = data.get("series")
    fj["book"] = data.get("book")
    fj["leaf_pages"] = data.get("leaf_pages", {})
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
    if "alphabet.png" in made:
        parts.append("<h2>Alphabet</h2><p>Gray letters are constructed, not traced.</p><img src='alphabet.png' style='max-width:100%'>")
    parts.append("<h2>Cuts</h2><img src='cuts.png' style='max-width:100%'>")
    parts.append("<h2>Traces</h2>")
    for m in made:
        if m.endswith("_overlay.png"):
            parts.append(f"<figure style='display:inline-block'><img src='{m}' style='height:220px'><figcaption>{m}</figcaption></figure>")
    parts.append(f"<h2>Checks — {checks['status']}</h2><p>{checks['warnings']} warnings, {checks['infos']} notes.</p><pre>"
                 + html.escape(json.dumps(checks["items"], indent=1)) + "</pre>")
    if fj["arrow_attempts"]:
        parts.append("<h2>Arrow attempts</h2><pre>" + html.escape(json.dumps(fj["arrow_attempts"], indent=2)) + "</pre>")
    parts.append("<h2>Lines</h2><pre>" + html.escape(json.dumps(fj["lines"], indent=2)) + "</pre>")
    parts.append("<h2>Provenance</h2><pre>" + html.escape(json.dumps(src, indent=2, default=str)) + "</pre>")
    (face.proofs / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Proof — " + html.escape(face.name) + "</title>"
        "<body style='font-family:system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem'>" + "\n".join(parts))
    made.append("index.html")
    face.log_event("proof", made=made, checks={k: checks[k] for k in ("status", "warnings", "infos")},
                   specimen_lines=[{k: r.get(k) for k in ("line", "text", "missing")} for r in line_proofs])
    return {"face": face.name, "proofs": made, "specimen_lines": line_proofs, "checks": fj["checks"]}
