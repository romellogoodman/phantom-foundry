"""cut — punchcutting: crop individual glyphs out of specimen scans.

The manifest gives a rough box per glyph (page pixel coords). cut binarizes
that region, flood-fills the ink component nearest the box center, adds any
other components stacked in the same columns (an i's dot), and tightens the
crop to that ink. Three files are kept per glyph:

  glyphs/<glyph>_raw.jpg   the untouched grayscale crop (the specimen)
  glyphs/<glyph>.png       the binarized, isolated glyph on white (the cut)
  glyphs/<glyph>.json      tight bbox in page coords, threshold, ink stats

`survey` is the step before the manifest: it finds the display lines on a
leaf and the letters on each line by ink projection, and draws a numbered
sheet so a person can name the boxes instead of measuring them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .face import Face, GlyphEntry, fname


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


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) index runs where flags is true."""
    out = []
    start = None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(flags)))
    return out


def stem_width_px(mask: np.ndarray, min_run: int = 3) -> int | None:
    """Rough stem width: for each row, the narrowest solid ink run (a vertical
    stem's cross-section beats a bar's full width); then the 25th percentile
    over rows, so bars, arms and the closed tops of round letters — rows
    with only wide runs — don't set the figure. Comparable across letters
    cut at the same size; a diagonal reads a little wide."""
    mins = []
    for row in mask:
        runs = [b - a for a, b in _runs(row) if b - a >= min_run]
        if runs:
            mins.append(min(runs))
    return int(np.percentile(mins, 25)) if mins else None


def stacked_piece(piece_y: tuple[int, int], main_y: tuple[int, int], piece_px: int, main_px: int,
                  min_fraction: float = 0.05) -> bool:
    """Does a second ink component belong to the glyph? Yes if it sits wholly
    above the main component (an i-dot, a detached accent) or is at least
    `min_fraction` of its ink (a broken stroke). A small mark beside or below
    the letter is a speck: nothing in the Latin alphabet hangs a dot under a
    letter, and a speck under the last line of a page is common."""
    a0, a1 = piece_y
    b0, b1 = main_y
    wholly_above = a1 <= b0
    return wholly_above or piece_px >= min_fraction * main_px


def _component(binary: np.ndarray, seed: tuple[int, int]) -> np.ndarray:
    """Boolean mask of the 4-connected ink component containing seed (x, y)."""
    # .copy(): fromarray images are read-only and floodfill would silently no-op
    im = Image.fromarray(np.where(binary, 0, 255).astype(np.uint8)).copy()
    ImageDraw.floodfill(im, seed, 128, thresh=0)
    return np.asarray(im) == 128


def load_page(face: Face, leaf: int) -> Image.Image:
    """The leaf as 8-bit grayscale. Decoding a 400 ppi JP2 takes about a
    second, so `cut` decodes each leaf once and hands it to every glyph."""
    return Image.open(face.specimen_jp2(leaf)).convert("L")


# `label` pads a survey box by this much above and below the letter's ink;
# a piece of ink that lies wholly inside that padding belongs to the line
# above or below (a footer under the last line), never to the letter.
LABEL_PAD_X, LABEL_PAD_Y = 3, 20


def cut_glyph(face: Face, entry: GlyphEntry, pad_frac: float = 0.06, stack_slack: float = 0.15,
              page: Image.Image | None = None) -> dict:
    if page is None:
        page = load_page(face, entry.leaf)
    box = (entry.x, entry.y, entry.x + entry.w, entry.y + entry.h)
    raw = page.crop(box)
    raw.save(face.glyphs / f"{fname(entry.glyph)}_raw.jpg", quality=90)   # the specimen crop; JPEG at scale

    t = otsu_threshold(raw)
    binary = np.asarray(raw) < t                      # True = ink
    bin_im = Image.fromarray(np.where(binary, 0, 255).astype(np.uint8)).copy()
    seed = find_seed(bin_im, raw.width // 2, raw.height // 2)
    main = _component(binary, seed)
    ys, xs = np.nonzero(main)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    slack = int(round((x1 - x0) * stack_slack))
    lo, hi = max(0, x0 - slack), min(raw.width, x1 + slack)

    # Other components in the main component's columns may belong to the same
    # glyph. A dot sits above or below its stem (no vertical overlap); a broken
    # stroke is a substantial piece. A small mark beside the letter is a paper
    # speck: recorded, not cut. See stacked_piece().
    component = main.copy()
    extras, specks = [], []
    my0, my1 = int(ys.min()), int(ys.max()) + 1
    remaining = binary & ~component
    remaining[:, :lo] = False
    remaining[:, hi:] = False
    while remaining.any():
        y, x = map(int, np.argwhere(remaining)[0])
        comp = _component(binary, (x, y))
        remaining &= ~comp
        cys, cxs = np.nonzero(comp)
        if cxs.min() < lo or cxs.max() >= hi:
            continue                                  # a neighbor poking into the box, not ours
        rec = {"box": [int(cxs.min()) + entry.x, int(cys.min()) + entry.y,
                       int(cxs.max()) + 1 + entry.x, int(cys.max()) + 1 + entry.y],
               "pixels": int(comp.sum())}
        inside_pad = cys.max() < LABEL_PAD_Y or cys.min() >= raw.height - LABEL_PAD_Y
        if inside_pad:
            continue                                  # the neighboring line's ink, not ours
        if stacked_piece((int(cys.min()), int(cys.max()) + 1), (my0, my1), rec["pixels"], int(main.sum())):
            extras.append(rec)
            component |= comp
        else:
            specks.append(rec)

    ys, xs = np.nonzero(component)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    pad = int(round((y1 - y0) * pad_frac))
    mask = component[y0:y1, x0:x1]
    out_w, out_h = mask.shape[1] + 2 * pad, mask.shape[0] + 2 * pad
    cut = np.full((out_h, out_w), 255, dtype=np.uint8)
    cut[pad:pad + mask.shape[0], pad:pad + mask.shape[1]][mask] = 0
    Image.fromarray(cut).save(face.glyphs / f"{fname(entry.glyph)}.png")

    info = {
        "glyph": entry.glyph, "unicode": entry.unicode, "leaf": entry.leaf,
        "line": entry.line, "band": entry.band, "category": entry.category,
        "rough_box": list(box),
        "tight_box_page": [entry.x + x0, entry.y + y0, entry.x + x1, entry.y + y1],
        "pad": pad, "cut_size": [out_w, out_h],
        "threshold": t, "seed": [entry.x + seed[0], entry.y + seed[1]],
        "components": 1 + len(extras), "extra_components": extras, "specks": specks,
        "ink_pixels": int(mask.sum()), "ink_height_px": y1 - y0, "ink_width_px": x1 - x0,
        "stem_px": stem_width_px(mask),
    }
    (face.glyphs / f"{fname(entry.glyph)}.json").write_text(json.dumps(info, indent=2))
    face.log_event("cut", **info)
    return info


def cut(face: Face, glyphs: list[str] | None = None) -> dict:
    face.ensure_layout()
    entries = face.read_manifest()
    if glyphs:
        entries = [e for e in entries if e.glyph in glyphs]
    pages: dict[int, Image.Image] = {}
    out = []
    for e in entries:
        if e.leaf not in pages:
            pages[e.leaf] = load_page(face, e.leaf)
        out.append(cut_glyph(face, e, page=pages[e.leaf]))
    return {"face": face.name, "cut": out}


def survey_page(page: Image.Image, min_line_height: int = 150, min_letter_width: int = 12,
                min_row_ink: int = 3) -> dict:
    """Find display lines and letter boxes on a page by ink projection.

    Rows with ink form bands; bands at least `min_line_height` tall are
    display lines (captions and running heads fall below it). Within a band,
    columns with ink form letters, split at the blank columns between them.
    Pure geometry: the same function surveys one leaf for a face and every
    leaf of a book for the catalog.
    """
    t = otsu_threshold(page)
    ink = np.asarray(page) < t
    row_ink = ink.sum(axis=1)
    bands = [(a, b) for a, b in _runs(row_ink >= min_row_ink) if b - a >= min_line_height]

    lines = []
    n = 0
    for i, (y0, y1) in enumerate(bands):
        cols = ink[y0:y1].sum(axis=0)
        letters = []
        for x0, x1 in _runs(cols > 0):
            if x1 - x0 < min_letter_width:
                continue
            sub = ink[y0:y1, x0:x1]
            rows = np.nonzero(sub.any(axis=1))[0]
            n += 1
            letters.append({"n": n, "x": int(x0), "y": int(y0 + rows.min()),
                            "w": int(x1 - x0), "h": int(rows.max() - rows.min() + 1),
                            "ink": int(sub.sum())})
        lines.append({"band": i + 1, "y0": int(y0), "y1": int(y1), "height": int(y1 - y0),
                      "letters": letters})
    return {"threshold": t, "page_size": list(page.size), "lines": lines}


def survey_sheet(page: Image.Image, lines: list[dict], width: int = 1400) -> Image.Image:
    """The page at reduced size with every band and numbered letter box drawn."""
    scale = width / page.width
    sheet = page.convert("RGB").resize((width, int(page.height * scale)))
    d = ImageDraw.Draw(sheet)
    for ln in lines:
        d.rectangle((0, ln["y0"] * scale, sheet.width - 1, ln["y1"] * scale), outline=(0, 150, 210), width=2)
        for L in ln["letters"]:
            bx = (L["x"] * scale, L["y"] * scale, (L["x"] + L["w"]) * scale, (L["y"] + L["h"]) * scale)
            d.rectangle(bx, outline=(225, 0, 130), width=2)
            d.text((bx[0] + 3, bx[1] + 3), str(L["n"]), fill=(225, 0, 130))
    return sheet


def band_crop(page: Image.Image, band: dict, width: int = 1600, margin_frac: float = 0.25) -> Image.Image:
    """One band, cropped with a margin, letter boxes numbered 1..n left to
    right — the picture a reader (a person or Claude) turns into text, one
    character per box."""
    L = band["letters"]
    if not L:
        return Image.new("RGB", (10, 10), "white")
    m = int(band["height"] * margin_frac)
    x0 = max(0, min(b["x"] for b in L) - m); x1 = min(page.width, max(b["x"] + b["w"] for b in L) + m)
    y0 = max(0, band["y0"] - m); y1 = min(page.height, band["y1"] + m)
    crop = page.crop((x0, y0, x1, y1)).convert("RGB")
    scale = min(1.0, width / crop.width)
    if scale < 1.0:
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)))
    d = ImageDraw.Draw(crop)
    for i, b in enumerate(L, 1):
        bx = ((b["x"] - x0) * scale, (b["y"] - y0) * scale, (b["x"] + b["w"] - x0) * scale, (b["y"] + b["h"] - y0) * scale)
        d.rectangle(bx, outline=(225, 0, 130), width=1)
        d.text((bx[0] + 2, bx[3] + 2), str(i), fill=(225, 0, 130))
    return crop


def survey(face: Face, leaf: int, min_line_height: int = 150, min_letter_width: int = 12,
           min_row_ink: int = 3) -> dict:
    """Survey one fetched leaf of a face. Writes specimens/leaf<N>_survey.json
    and a numbered sheet PNG; the numbers are what `label` turns into manifest rows."""
    face.ensure_layout()
    page = load_page(face, leaf)
    rec = survey_page(page, min_line_height, min_letter_width, min_row_ink)
    sheet_path = face.specimens / f"leaf{leaf:04d}_survey.png"
    survey_sheet(page, rec["lines"]).save(sheet_path)
    rec = {"leaf": leaf, **rec, "sheet": str(sheet_path.relative_to(face.dir))}
    (face.specimens / f"leaf{leaf:04d}_survey.json").write_text(json.dumps(rec, indent=2))
    face.log_event("survey", leaf=leaf, threshold=rec["threshold"], bands=len(rec["lines"]),
                   letters=sum(len(ln["letters"]) for ln in rec["lines"]))
    return rec


# Glyph naming for non-letters (AGL names); letters are named by themselves.
_NAMES = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
          "6": "six", "7": "seven", "8": "eight", "9": "nine", "&": "ampersand",
          ".": "period", ",": "comma", "-": "hyphen", "'": "quotesingle", "!": "exclam",
          "?": "question", ":": "colon", ";": "semicolon", "$": "dollar"}


def category_of(ch: str) -> str:
    if ch.isupper():
        return "cap"
    if ch.islower():
        return "lower"
    if ch.isdigit():
        return "figure"
    return "punct"


def reading_tokens(text: str) -> list[str]:
    """One token per survey box. A letter is itself; `[fi]` is one box that
    holds several touching letters; `?` an unreadable box; `~` a box that is
    not a letter (a speck, a rule end). Spaces separate words and have no box."""
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif c == "[":
            j = text.index("]", i)
            out.append(text[i:j + 1])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return out


def printed_text(reading: str) -> str:
    """The reading as the words on the page: brackets opened, skips dropped."""
    return re.sub(r"[\[\]~]", "", reading)


def label(face: Face, leaf: int, band: int, text: str, line: str,
          pad_x: int = LABEL_PAD_X, pad_y: int = LABEL_PAD_Y, by: str = "human") -> dict:
    """Turn one surveyed band into manifest rows by reading `text` across it.

    Boxes are taken left to right; spaces in `text` have no box. The first
    time a character is labeled it gets the plain glyph name; a later one is
    an alternate named <glyph>.<line>, then <glyph>.<line>_2, ... — so label
    the largest size first and the default glyph comes from the best scan.
    A box already covered by a manifest row keeps that row unchanged.
    `by` records who read the line: human, ocr, claude, or claude+ocr (both agreed).
    """
    survey_path = face.specimens / f"leaf{leaf:04d}_survey.json"
    if not survey_path.exists():
        raise FileNotFoundError(f"run `foundry survey --leaf {leaf}` first ({survey_path})")
    rec = json.loads(survey_path.read_text())
    ln = next((x for x in rec["lines"] if x["band"] == band), None)
    if ln is None:
        raise ValueError(f"leaf {leaf} has no band {band}")
    chars = reading_tokens(text)
    if len(chars) != len(ln["letters"]):
        raise ValueError(f"band {band} has {len(ln['letters'])} boxes but {text!r} has {len(chars)} characters")
    pw, ph = rec["page_size"]

    entries = face.read_manifest()
    names = {e.glyph for e in entries}
    added, kept = [], []
    for ch, L in zip(chars, ln["letters"]):
        if len(ch) != 1 or ch in "?~":
            continue                                  # not one letter in this box: no glyph from it
        # same glyph if each box holds the other's center (a hand-drawn rough box
        # can be wide enough to swallow a neighbor; its center still says which)
        cx, cy = L["x"] + L["w"] / 2, L["y"] + L["h"] / 2
        existing = next((e for e in entries if e.leaf == leaf and e.x <= cx < e.x + e.w
                         and e.y <= cy < e.y + e.h
                         and L["x"] <= e.x + e.w / 2 < L["x"] + L["w"]
                         and L["y"] <= e.y + e.h / 2 < L["y"] + L["h"]), None)
        if existing is not None:
            existing.line = existing.line or line
            existing.category = existing.category or category_of(ch)
            kept.append(existing.glyph)
            continue
        base = _NAMES.get(ch, ch)
        name = base
        if name in names:
            name = f"{base}.{line}"
            k = 2
            while name in names:
                name = f"{base}.{line}_{k}"
                k += 1
        x0, y0 = max(0, L["x"] - pad_x), max(0, L["y"] - pad_y)
        x1, y1 = min(pw, L["x"] + L["w"] + pad_x), min(ph, L["y"] + L["h"] + pad_y)
        e = GlyphEntry(name, f"{ord(ch):04X}" if name == base else "", leaf, x0, y0, x1 - x0, y1 - y0,
                       f"survey #{L['n']}, {text!r}", line, category_of(ch), str(band))
        entries.append(e)
        names.add(name)
        added.append(name)
    face.write_manifest(entries)
    data = face.load()
    sl = data.setdefault("specimen_lines", [])
    if not any(x.get("leaf") == leaf and x.get("band") == band for x in sl):
        sl.append({"leaf": leaf, "line": line, "text": text, "band": band, "by": by})
        face.save(data)
    out = {"leaf": leaf, "band": band, "line": line, "text": text, "by": by, "added": added, "kept": kept}
    face.log_event("label", **out)
    return out
