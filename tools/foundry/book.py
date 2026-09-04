"""book — a whole specimen book on the shelf, and the faces founded from it.

One face at a time starts from a leaf someone chose. A hundred start from
the book: `shelve` fetches every leaf and the archive's OCR, `catalog`
surveys every leaf and reads the small caption printed above each showing
("42 Point Cadillac Condensed") to learn its size and series, `found`
starts a face from a series in the catalog, and `label --auto` fills its
manifest from *readings* — what each display band says, read from the band
crop by a person or by Claude and cross-checked against the OCR. The OCR
alone never labels a glyph: it misreads display type ("PROSPEROIS",
"Maciiine") in ways that pass a character count.

books/<archive_id>/
  book.yaml              item metadata, page count, when shelved
  jp2/                   every leaf (ignored; shelve reproduces it)
  ocr/                   the archive's DjVu XML, split per leaf (ignored)
  survey/leafNNNN.json   display bands + letter boxes per leaf (committed)
  sheets/                leafNNNN.png survey sheets, leafNNNN_bB.png band crops (ignored)
  catalog.json           every surveyed band with its caption, OCR text and series (committed)
  readings.json          what each band says, by whom (committed — it is the labeling record)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from multiprocessing import Pool
from pathlib import Path

import yaml
from PIL import Image

from .face import FACES_DIR, REPO_ROOT, Face
from .fetch import IA, download, item_metadata

BOOKS_DIR = REPO_ROOT / "books"


class Book:
    def __init__(self, archive_id: str):
        self.archive_id = archive_id
        self.dir = BOOKS_DIR / archive_id
        self.yaml_path = self.dir / "book.yaml"
        self.jp2_dir = self.dir / "jp2"
        self.ocr_dir = self.dir / "ocr"
        self.survey_dir = self.dir / "survey"
        self.sheets_dir = self.dir / "sheets"
        self.catalog_path = self.dir / "catalog.json"
        self.readings_path = self.dir / "readings.json"

    def load(self) -> dict:
        return yaml.safe_load(self.yaml_path.read_text()) if self.yaml_path.exists() else {}

    def save(self, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    def leaf_jp2(self, leaf: int) -> Path:
        return self.jp2_dir / f"{self.archive_id}_{leaf:04d}.jp2"

    def leaves(self) -> list[int]:
        return sorted(int(p.stem.rsplit("_", 1)[1]) for p in self.jp2_dir.glob("*.jp2"))

    def ocr_xml(self) -> Path:
        return self.ocr_dir / f"{self.archive_id}_djvu.xml"

    def leaf_ocr_path(self, leaf: int) -> Path:
        return self.ocr_dir / f"leaf{leaf:04d}.json"

    def survey_path(self, leaf: int) -> Path:
        return self.survey_dir / f"leaf{leaf:04d}.json"

    def sheet_path(self, leaf: int) -> Path:
        return self.sheets_dir / f"leaf{leaf:04d}.png"

    def crop_path(self, leaf: int, band: int) -> Path:
        return self.sheets_dir / f"leaf{leaf:04d}_b{band}.png"

    def catalog(self) -> dict:
        return json.loads(self.catalog_path.read_text()) if self.catalog_path.exists() else {}

    def readings(self) -> dict:
        return json.loads(self.readings_path.read_text()) if self.readings_path.exists() else {}

    def save_readings(self, r: dict) -> None:
        self.readings_path.write_text(json.dumps(dict(sorted(r.items(), key=_reading_key)), indent=1,
                                                 ensure_ascii=False))


def _reading_key(item):
    leaf, band = item[0].split(":")
    return int(leaf), int(band)


# -- shelve ---------------------------------------------------------------

def shelve(archive_id: str) -> dict:
    """Fetch the whole book: metadata, every leaf's JP2 (one zip), the OCR."""
    book = Book(archive_id)
    meta = item_metadata(archive_id)
    m = meta["metadata"]
    date = m.get("date")
    data = book.load()
    data.update({
        "archive_id": archive_id, "title": m.get("title"), "creator": m.get("creator"),
        "publisher": m.get("publisher"), "date": date[0] if isinstance(date, list) else date,
        "ppi": int(m["ppi"]) if m.get("ppi") else None, "url": f"{IA}/details/{archive_id}",
        "copyright_status": m.get("possible-copyright-status"), "contributor": m.get("contributor"),
        "imagecount": int(m["imagecount"]) if m.get("imagecount") else None,
        "shelved": time.strftime("%Y-%m-%d"),
    })
    book.save(data)

    n = len(book.leaves())
    if data["imagecount"] and n < data["imagecount"]:
        zip_path = book.dir / f"{archive_id}_jp2.zip"
        if not zip_path.exists():
            download(f"{IA}/download/{archive_id}/{archive_id}_jp2.zip", zip_path)
        book.jp2_dir.mkdir(exist_ok=True)
        subprocess.run(["unzip", "-q", "-j", "-o", str(zip_path), "-d", str(book.jp2_dir)], check=True)
        n = len(book.leaves())
    if not book.ocr_xml().exists():
        download(f"{IA}/download/{archive_id}/{archive_id}_djvu.xml", book.ocr_xml())
    split = split_ocr(book)
    return {"archive_id": archive_id, "leaves": n, "ocr_leaves": split, "dir": str(book.dir.relative_to(REPO_ROOT))}


def split_ocr(book: Book, force: bool = False) -> int:
    """The archive's DjVu XML (one file, tens of MB) → ocr/leafNNNN.json per
    leaf: lines of words with boxes in the leaf's own pixel coordinates —
    the same coordinates survey uses, so OCR words and letter boxes overlay."""
    if not force and any(book.ocr_dir.glob("leaf*.json")):
        return len(list(book.ocr_dir.glob("leaf*.json")))
    count = 0
    for _, el in ET.iterparse(str(book.ocr_xml()), events=("end",)):
        if el.tag != "OBJECT":
            continue
        leaf = None
        for par in el.findall("PARAM"):
            if par.get("name") == "PAGE":
                leaf = int(re.search(r"_(\d{4})\.djvu", par.get("value")).group(1))
        lines = []
        for line in el.iter("LINE"):
            words = []
            for w in line.findall("WORD"):
                c = [int(v) for v in w.get("coords").split(",")]
                x0, y1, x1, y0 = c[:4]                     # DjVu: left, bottom, right, top
                words.append({"text": (w.text or "").strip(), "box": [x0, y0, x1, y1]})
            words = [w for w in words if w["text"]]
            if words:
                lines.append({"x0": min(w["box"][0] for w in words), "y0": min(w["box"][1] for w in words),
                              "x1": max(w["box"][2] for w in words), "y1": max(w["box"][3] for w in words),
                              "text": " ".join(w["text"] for w in words), "words": words})
        rec = {"leaf": leaf, "size": [int(el.get("width")), int(el.get("height"))], "lines": lines}
        book.leaf_ocr_path(leaf).write_text(json.dumps(rec, ensure_ascii=False))
        count += 1
        el.clear()
    return count


def leaf_ocr(book: Book, leaf: int) -> dict:
    p = book.leaf_ocr_path(leaf)
    return json.loads(p.read_text()) if p.exists() else {"leaf": leaf, "size": None, "lines": []}


# -- reading the page furniture -----------------------------------------------

# "4 A 7a 42 Point …", "16A 10 Point …" (caps only), "42 Point …": the font scheme is optional
CAPTION_POINT = re.compile(r"^(?:\d+\s*A\s*(?:\d+\s*a\s*)?)?(\d{1,3})\s*[- ]?\s*Point\b\s*(.*)$", re.I)
# wood type: "No. 266— Class L . Fifteen Line, 12c per letter" — the series first, the size as a word
CAPTION_WOOD = re.compile(r"^(No[.,]?\s*\d+)\s*[—–-]*\s*(Class\s+[A-Z])?\s*\.?\s*([A-Za-z]+)[- ]Line\b", re.I)
_NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_NUMBER_WORDS.update({"twentyfour": 24, "thirty": 30, "forty": 40, "pour": 4, "flve": 5, "slx": 6, "elght": 8})
_JUNK = re.compile(r"[^A-Za-z&.-]")          # an OCR'd weight ("lO'A", "13%", "Slxb lbs.") or price
_ABBR = {"cond": "Condensed", "ext": "Extended", "exp": "Expanded", "ital": "Italic", "it": "Italic",
         "ex": "Extra", "med": "Medium", "lt": "Light", "hvy": "Heavy", "bd": "Bold", "cap": "Caps",
         "comp": "Compressed", "compr": "Compressed"}
# showings that are not letters, whatever their caption says
NOT_TYPE = re.compile(r"border|ornament|\brule|dash|initial|brass|corner|combination|bracket|\bcuts?\b|piece|"
                      r"decorat|\bsigns?\b|fraction|quotation|leader|spaces|quads|slug|metal|machin|electro|"
                      r"logotype|monogram|check|ticket|card\b|stamp|furniture|\bsets?\b|advertis|^No\.? \S+$", re.I)
_NOTES = re.compile(r"\((?:cast|on|point|uniform|line|body|set|standard|\s)+\)", re.I)


def parse_caption(text: str) -> dict | None:
    """'4 A 7a 42 Point Cadillac Condensed 8¾ lbs., $5.25' → 42 pt, series
    'Cadillac Condensed', line name '42pt'. Wood type: 'No. 266— Class L .
    Fifteen Line, 12c per letter' → 15 line, 'No. 266 Class L', 'fifteen'."""
    t = _NOTES.sub(" ", text.strip())
    m = CAPTION_POINT.match(t)
    if m:
        size = int(m.group(1))
        toks = m.group(2).split()
        if "lbs" in " ".join(toks).lower():                     # drop the weight that precedes "lbs"
            i = next(i for i, tok in enumerate(toks) if "lbs" in tok.lower())
            toks = toks[:max(0, i - 1)]
        words = []
        for i, tok in enumerate(toks):
            if re.fullmatch(r"No[.,]?", tok) and i + 1 < len(toks) and re.fullmatch(r"\d{1,4}|I?[Il1]{2,4}", toks[i + 1]):
                num = re.sub(r"[Il]", "1", toks[i + 1])       # OCR reads "111" as "Ill"
                words += ["No.", num]                         # a numbered series: "Topic No. 5"
                break
            if _JUNK.search(tok) or "lbs" in tok.lower():
                break
            tok = _ABBR.get(tok.rstrip(".,;:").lower(), tok.strip(".,;:"))
            if tok:
                words.append(tok)
        series = re.sub(r"\s+Series$", "", " ".join(words), flags=re.I).strip()
        if len(series) < 3 or not re.search(r"[A-Za-z]{3}", series):
            return None
        return {"size": size, "unit": "pt", "series": _title(series), "line": f"{size}pt"}
    m = CAPTION_WOOD.match(t)
    if m:
        word = m.group(3).lower()
        if word not in _NUMBER_WORDS:
            return None
        num = re.sub(r"\D", "", m.group(1))
        series = f"No. {num}" + (f" {_title(m.group(2))}" if m.group(2) else "")
        size = _NUMBER_WORDS[word]
        canonical = next(w for w, n in _NUMBER_WORDS.items() if n == size)   # "pour" → "four"
        return {"size": size, "unit": "line", "series": series, "line": canonical}
    return None


def _title(s: str) -> str:
    keep = {"No.", "of", "and", "the"}
    out = []
    for w in s.split():
        out.append(w if w in keep or (len(w) > 1 and w[1:].islower() and w[0].isupper()) else w.capitalize())
    return " ".join(out)


def leaf_furniture(ocr: dict) -> dict:
    """The printed page number (folio) in the foot, the series heading at
    the head, and every caption on the leaf with its position."""
    size = ocr.get("size") or [0, 0]
    H = size[1] or 1
    folio, heading, captions = None, None, []
    blockers = []          # caption-like lines, parsed or not: a showing boundary
    heads = []
    lines = list(ocr["lines"])
    # wood type sometimes prints the series and the size on two short lines:
    # "No. 155— Class O" over "Three Line, 6c per letter" — read them as one
    joined = []
    skip = False
    for i, ln in enumerate(lines):
        if skip:
            skip = False
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if (nxt and re.match(r"^No[.,]?\s*\d+", ln["text"]) and not re.search(r"\bLine\b", ln["text"])
                and re.match(r"^[A-Za-z]+[- ]Line\b", nxt["text"])
                and abs((nxt["y0"] + nxt["y1"]) / 2 - (ln["y0"] + ln["y1"]) / 2) <= 150):
            joined.append({**ln, "text": ln["text"] + " " + nxt["text"], "y1": nxt["y1"]})
            skip = True
        else:
            joined.append(ln)
    for ln in joined:
        if ln["y0"] > 0.9 * H:
            for w in ln["words"]:
                if re.fullmatch(r"\d{1,4}", w["text"]):
                    folio = int(w["text"])
        elif ln["y1"] < 0.12 * H:
            words = [w["text"] for w in ln["words"] if re.fullmatch(r"[A-Za-z][A-Za-z'&.-]*", w["text"])]
            if words:
                heads.append((ln["y1"] - ln["y0"], " ".join(words)))
        cap = parse_caption(ln["text"])
        if cap:
            captions.append({**cap, "y0": ln["y0"], "y1": ln["y1"], "text": ln["text"]})
        elif re.search(r"\bPoint\b|\bLine,|lbs|\$\d|^\d+\s*A\s+\d+", ln["text"]):
            blockers.append({"y0": ln["y0"], "y1": ln["y1"], "text": ln["text"]})
    if heads:
        heading = _title(max(heads)[1])
    return {"page": folio, "heading": heading, "captions": sorted(captions, key=lambda c: c["y0"]),
            "blockers": blockers}


def band_ocr_text(ocr: dict, band: dict) -> str | None:
    """The OCR words that sit on this band (vertical center inside it and at
    least a third of its height), left to right. Small captions that share
    rows with a display line are excluded by the height rule."""
    y0, y1, h = band["y0"], band["y1"], band["height"]
    words = []
    for ln in ocr["lines"]:
        for w in ln["words"]:
            bx0, by0, bx1, by1 = w["box"]
            cy = (by0 + by1) / 2
            if y0 <= cy <= y1 and (by1 - by0) >= 0.33 * h:
                words.append((bx0, w["text"]))
    if not words:
        return None
    return " ".join(t for _, t in sorted(words))


def assign_captions(bands: list[dict], captions: list[dict], max_per_caption: int = 3,
                    first_gap: int = 320, blockers: list[dict] | None = None) -> None:
    """Each band takes the nearest caption above it, if that caption can
    still claim it: at most `max_per_caption` bands per caption, the first
    within `first_gap` px of the caption, each following close on the last,
    at least two boxes, no taller than the size allows (a boxed showing
    card or a border between showings is not a line of the face), letters
    about as tall as the caption's first band (a showing is one size), and
    no caption-like line in between — the OCR loses a caption's size digits
    now and then, and the bands under it must not fall to the caption above."""
    for b in bands:
        b["size"] = b["unit"] = b["series"] = b["line"] = None
    claimed: dict[int, list[dict]] = {}
    blockers = blockers or []
    for b in bands:
        above = [c for c in captions if c["y1"] <= b["y0"]]
        if not above or b["n"] < 2:
            continue
        cap = above[-1]
        ci = captions.index(cap)
        mine = claimed.setdefault(ci, [])
        if len(mine) >= max_per_caption:
            continue
        prev = mine[-1] if mine else None
        gap = b["y0"] - (prev["y1"] if prev else cap["y1"])
        limit = first_gap if prev is None else int(1.2 * prev["height"]) + 120
        max_h = 8 * cap["size"] if cap["unit"] == "pt" else 100 * cap["size"]
        if gap > limit or b["height"] > max_h:
            continue
        if mine and not (0.7 * mine[0]["tall_px"] <= b["tall_px"] <= 1.3 * mine[0]["tall_px"]):
            continue
        blocked = any(bl["y0"] > cap["y1"] + 40 and bl["y1"] < b["y0"] for bl in blockers)
        if blocked:
            continue
        b["size"], b["unit"], b["series"], b["line"] = cap["size"], cap["unit"], cap["series"], cap["line"]
        mine.append(b)


STANDARD_PT = [6, 8, 10, 12, 14, 16, 18, 20, 24, 30, 36, 42, 48, 54, 60, 66, 72, 84, 96, 108, 120, 144]


def infer_sizes(bands: list[dict], min_tall: int = 100) -> None:
    """A band no caption claimed, on a leaf whose showings are one series,
    is sized from its letters: its tallest boxes against the nearest claimed
    band's, times that band's size, snapped to the standard point sizes.
    That recovers a showing whose caption the OCR mangled ("Point Lining
    Facade Condensed" with the 84 gone). Marked `inferred` so the record says so."""
    claimed = [b for b in bands if b.get("series") and b.get("unit") == "pt"]
    if not claimed or len({b["series"] for b in claimed}) != 1:
        return
    series = claimed[0]["series"]
    first_y = min(b["y0"] for b in claimed)
    tallest = max(b["tall_px"] for b in claimed)
    for b in bands:
        if b.get("series") or b["n"] < 2 or b["tall_px"] < min_tall or b["y0"] < first_y:
            continue
        if b["tall_px"] > 1.25 * tallest:
            continue          # far bigger than anything captioned here: another showing, not a lost caption
        ref = min(claimed, key=lambda c: abs(c["y0"] - b["y0"]))
        est = b["tall_px"] / ref["tall_px"] * ref["size"]
        size = min(STANDARD_PT, key=lambda z: abs(z - est))
        if abs(size - est) / est > 0.12 or b["height"] > 8 * size:
            continue
        b["size"], b["unit"], b["series"], b["line"] = size, "pt", series, f"{size}pt"
        b["inferred"] = True


# -- catalog ------------------------------------------------------------------

def _tall_px(letters: list[dict]) -> int:
    """A size proxy for a band: the median height of its tallest half of
    boxes (caps and ascenders), so a mixed-case line isn't read at x-height."""
    if not letters:
        return 0
    hs = sorted((L["h"] for L in letters), reverse=True)
    top = hs[:max(1, len(hs) // 2)]
    return int(top[len(top) // 2])


def catalog_leaf(archive_id: str, leaf: int, min_line_height: int = 120, force: bool = False,
                 crops: bool = True) -> dict:
    from .cut import band_crop, survey_page, survey_sheet
    book = Book(archive_id)
    book.survey_dir.mkdir(parents=True, exist_ok=True)
    book.sheets_dir.mkdir(parents=True, exist_ok=True)
    sp = book.survey_path(leaf)
    page = None
    if sp.exists() and not force:
        rec = json.loads(sp.read_text())
    else:
        page = Image.open(book.leaf_jp2(leaf)).convert("L")
        rec = survey_page(page, min_line_height)
        rec = {"leaf": leaf, **rec, "sheet": str(book.sheet_path(leaf).relative_to(book.dir))}
        survey_sheet(page, rec["lines"]).save(book.sheet_path(leaf))
        sp.write_text(json.dumps(rec, indent=1))
    ocr = leaf_ocr(book, leaf)
    furniture = leaf_furniture(ocr)
    bands = []
    for ln in rec["lines"]:
        if not ln["letters"]:
            continue
        b = {"band": ln["band"], "y0": ln["y0"], "y1": ln["y1"], "height": ln["height"],
             "n": len(ln["letters"]), "tall_px": _tall_px(ln["letters"]),
             "ocr": band_ocr_text(ocr, ln)}
        chars = [c for c in (b["ocr"] or "") if not c.isspace()]
        b["ocr_match"] = bool(chars) and len(chars) == b["n"]
        bands.append(b)
    assign_captions(bands, furniture["captions"], blockers=furniture.get("blockers"))
    infer_sizes(bands)
    if crops:
        for b in bands:
            cp = book.crop_path(leaf, b["band"])
            if force or not cp.exists():
                if page is None:
                    page = Image.open(book.leaf_jp2(leaf)).convert("L")
                ln = next(x for x in rec["lines"] if x["band"] == b["band"])
                band_crop(page, ln).save(cp)
            b["crop"] = str(cp.relative_to(book.dir))
    return {"leaf": leaf, "page": furniture["page"], "heading": furniture["heading"],
            "captions": [{k: c[k] for k in ("size", "unit", "series", "line", "y0")} for c in furniture["captions"]],
            "bands": bands}


def _catalog_leaf_star(args):
    try:
        return catalog_leaf(*args)
    except Exception as e:                                   # one bad leaf must not sink the book
        return {"leaf": args[1], "error": f"{type(e).__name__}: {e}", "bands": [], "captions": []}


def catalog(archive_id: str, leaves: list[int] | None = None, min_line_height: int = 120,
            workers: int = 0, force: bool = False) -> dict:
    """Survey every leaf (or the given ones) and index every display band by
    the series its caption names. Writes catalog.json; earlier leaves are
    kept when a subset is re-run."""
    book = Book(archive_id)
    leaves = leaves or book.leaves()
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    jobs = [(archive_id, lf, min_line_height, force) for lf in leaves]
    if workers > 1 and len(jobs) > 1:
        with Pool(workers) as pool:
            recs = pool.map(_catalog_leaf_star, jobs, chunksize=4)
    else:
        recs = [_catalog_leaf_star(j) for j in jobs]
    cat = book.catalog() if book.catalog_path.exists() else {}
    per_leaf = {int(k): v for k, v in cat.get("leaves", {}).items()}
    for r in recs:
        per_leaf[r["leaf"]] = r
    series: dict[str, dict] = {}
    for lf, r in sorted(per_leaf.items()):
        for b in r.get("bands", []):
            if not b.get("series"):
                continue
            s = series.setdefault(b["series"], {"slug": slug(b["series"]), "leaves": [], "pages": [],
                                                 "sizes": [], "unit": b["unit"], "bands": [], "max_tall_px": 0,
                                                 "boxes": 0})
            if lf not in s["leaves"]:
                s["leaves"].append(lf)
                if r.get("page") is not None:
                    s["pages"].append(r["page"])
            if b["size"] not in s["sizes"]:
                s["sizes"].append(b["size"])
            s["bands"].append([lf, b["band"]])
            s["max_tall_px"] = max(s["max_tall_px"], b["tall_px"])
            s["boxes"] += b["n"]
    merged = merge_lookalikes(series, per_leaf)
    for s in series.values():
        s["sizes"].sort(reverse=True)
        s["not_type"] = bool(NOT_TYPE.search(s["series"] if "series" in s else ""))
    for name, s in series.items():
        s["not_type"] = bool(NOT_TYPE.search(name))
    infer_pages(per_leaf)
    for s in series.values():
        s["pages"] = sorted({per_leaf[lf]["page"] for lf in s["leaves"] if per_leaf[lf].get("page")})
    out = {"archive_id": archive_id, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "merged": merged,
           "min_line_height": min_line_height, "leaves": {str(k): v for k, v in sorted(per_leaf.items())},
           "series": dict(sorted(series.items()))}
    book.catalog_path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    errors = [r for r in recs if r.get("error")]
    return {"archive_id": archive_id, "leaves": len(leaves), "bands": sum(len(r.get("bands", [])) for r in recs),
            "series": len(series), "errors": errors[:10], "catalog": str(book.catalog_path.relative_to(REPO_ROOT))}


def merge_lookalikes(series: dict, per_leaf: dict, ratio: float = 0.9) -> list[dict]:
    """OCR spells a series two ways ("Old Roman Condevsed"): a name that
    nearly matches a bigger one, on the same or a neighboring leaf, is that
    one. The bands are relabeled; the merge is recorded."""
    from difflib import SequenceMatcher
    merged = []
    for small in sorted(list(series), key=lambda n: series[n]["boxes"]):
        if small not in series:
            continue
        for big in sorted(series, key=lambda n: -series[n]["boxes"]):
            if big == small or series[big]["boxes"] <= series[small]["boxes"]:
                continue
            near = any(abs(a - b) <= 2 for a in series[small]["leaves"] for b in series[big]["leaves"])
            same_number = re.findall(r"\d+", small) == re.findall(r"\d+", big)   # No. 614 is not No. 615
            if near and same_number and SequenceMatcher(None, small.lower(), big.lower()).ratio() >= ratio:
                clean = re.compile(r"^[A-Za-z0-9 .]+$")
                if clean.match(small) and not clean.match(big):
                    big, small = small, big                   # keep the name without OCR junk
                for lf, band in series[small]["bands"]:
                    for b in per_leaf[lf]["bands"]:
                        if b["band"] == band:
                            b["series"] = big
                sb, ss = series[big], series[small]
                sb["bands"] += ss["bands"]; sb["boxes"] += ss["boxes"]
                sb["leaves"] = sorted(set(sb["leaves"]) | set(ss["leaves"]))
                sb["sizes"] = sorted(set(sb["sizes"]) | set(ss["sizes"]), reverse=True)
                sb["max_tall_px"] = max(sb["max_tall_px"], ss["max_tall_px"])
                sb.setdefault("merged_from", []).append(small)
                merged.append({"from": small, "into": big})
                del series[small]
                break
    return merged


def infer_pages(per_leaf: dict, window: int = 12) -> None:
    """The printed page number, from the OCR'd folio where the leaf-to-folio
    offset agrees with its neighbors, else from that local offset — a folio
    the OCR misread as 898 on leaf 416 becomes 398 like the leaves around it."""
    offsets = {lf: lf - r["page"] for lf, r in per_leaf.items() if r.get("page")}
    for lf, r in per_leaf.items():
        r["folio_ocr"] = r.get("page")
        near = [o for l2, o in offsets.items() if abs(l2 - lf) <= window]
        if len(near) < 3:
            continue
        mode = max(set(near), key=near.count)
        if near.count(mode) >= 3:
            r["page"] = lf - mode


def slug(series: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", series.lower()).strip("-")
    return re.sub(r"^no-", "no", s)


def candidates(book: Book, min_tall_px: int = 140, min_boxes: int = 8) -> list[dict]:
    """Series worth founding: at least one band whose tallest boxes reach
    `min_tall_px` (36 pt caps at 400 ppi are about 140 px) and enough letters."""
    cat = book.catalog()
    out = []
    for name, s in cat.get("series", {}).items():
        if s["max_tall_px"] >= min_tall_px and s["boxes"] >= min_boxes and not s.get("not_type"):
            out.append({"series": name, **s})
    return sorted(out, key=lambda s: (-s["max_tall_px"], s["series"]))


# -- readings -------------------------------------------------------------------

def read(book: Book, leaf: int, band: int, text: str, by: str = "human", note: str = "", line: str = "") -> dict:
    """Record what a band says. `text` has one character per numbered box,
    spaces between words; an empty text says the band is not type. `line`
    overrides the caption's size name when the reader knows better."""
    r = book.readings()
    rec = {"text": text, "by": by, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if note:
        rec["note"] = note
    if line:
        rec["line"] = line
    r[f"{leaf}:{band}"] = rec
    book.save_readings(r)
    return {f"{leaf}:{band}": rec}


def import_readings(book: Book, path: Path, by: str = "claude") -> dict:
    """Bulk-add readings from a JSON list of {leaf, band, text, note?}."""
    items = json.loads(Path(path).read_text())
    r = book.readings()
    n = 0
    for it in items:
        rec = {"text": it["text"], "by": it.get("by", by), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if it.get("note"):
            rec["note"] = it["note"]
        if it.get("line"):
            rec["line"] = it["line"]      # a reader's override of the caption's size (two columns in one band)
        r[f"{int(it['leaf'])}:{int(it['band'])}"] = rec
        n += 1
    book.save_readings(r)
    return {"imported": n, "total": len(r)}


def _norm(s: str | None) -> str:
    return "".join(c for c in (s or "") if not c.isspace())


# -- found ------------------------------------------------------------------------

def found(name: str, book: Book, series: str, title: str | None = None, leaves: list[int] | None = None) -> dict:
    """Start a face from a series in the catalog: face.yaml with the book's
    provenance and the leaves the series is shown on, the leaves linked into
    specimens/ (never copied — the book is the store), their surveys copied."""
    from .cut import survey_sheet
    cat = book.catalog()
    s = cat["series"].get(series)
    if s is None:
        raise KeyError(f"series {series!r} is not in {book.catalog_path}")
    leaves = leaves or s["leaves"]
    face = Face(name)
    if face.yaml_path.exists():
        raise FileExistsError(f"{face.yaml_path} exists; founding never overwrites a face")
    face.ensure_layout()
    b = book.load()
    data = {
        "name": name,
        "title": title or series,
        "series": series,
        "status": "proto",
        "version": "0.1.0",
        "book": book.archive_id,
        "source": {k: b.get(k) for k in ("archive_id", "title", "creator", "publisher", "date", "ppi", "url",
                                          "copyright_status", "contributor")},
        "leaf_pages": {},
        "metrics": {"upm": 1000, "cap_height": 700, "sidebearing": 40, "min_contour_area": 0},
    }
    data["source"]["leaves"] = sorted(leaves)
    for lf in leaves:
        r = cat["leaves"].get(str(lf), {})
        if r.get("page") is not None:
            data["leaf_pages"][lf] = r["page"]
        target = face.specimen_jp2(lf)
        if not target.exists():
            target.symlink_to(os.path.relpath(book.leaf_jp2(lf), target.parent))
        sv = json.loads(book.survey_path(lf).read_text())
        sheet_rel = f"specimens/leaf{lf:04d}_survey.jpg"
        sv["sheet"] = sheet_rel
        (face.specimens / f"leaf{lf:04d}_survey.json").write_text(json.dumps(sv, indent=2))
        page = Image.open(book.leaf_jp2(lf)).convert("L")
        survey_sheet(page, sv["lines"]).save(face.dir / sheet_rel, quality=85)   # doubles as the preview
    face.save(data)
    pages = ", ".join(f"leaf {lf}" + (f" (p. {data['leaf_pages'][lf]})" if lf in data["leaf_pages"] else "")
                      for lf in sorted(leaves))
    (face.dir / "CHANGELOG.md").write_text(
        f"# {data['title']} — changelog\n\n"
        f"Revival of {b.get('publisher')} **{series}** from *{(b.get('title') or '').split('.')[0]}* "
        f"({b.get('date')}), {pages} — archive.org `{book.archive_id}`, {b.get('ppi')} ppi, public domain.\n\n"
        f"Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → "
        f"**release** (1.0: spaced, kerned, cleaned, tested).\n\n"
        f"## 0.1.0 — {time.strftime('%Y-%m-%d')} · proto\n\n"
        f"- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.\n"
        f"  Letters read from the page by Claude and cross-checked against the archive's OCR; no constructed letters.\n")
    face.log_event("found", book=book.archive_id, series=series, leaves=sorted(leaves))
    return {"face": name, "series": series, "leaves": sorted(leaves), "pages": data["leaf_pages"]}


# -- label from readings ------------------------------------------------------------

def label_auto(face: Face, book: Book, min_tall_px: int = 0, trust_ocr: bool = False) -> dict:
    """Fill the manifest from readings. Every band of the face's series on
    its leaves, largest size first (so the default glyph comes from the
    biggest cut); a band with no reading is left for one, unless
    `trust_ocr` and its OCR text fits the boxes exactly."""
    from .cut import label
    cat = book.catalog()
    data = face.load()
    series = data.get("series")
    readings = book.readings()
    todo = []
    for lf in data["source"]["leaves"]:
        r = cat["leaves"].get(str(lf), {})
        for b in r.get("bands", []):
            if series and b.get("series") != series:
                continue
            if not series and not b.get("series"):
                continue
            if b["tall_px"] < min_tall_px:
                continue
            todo.append((lf, b))
    todo.sort(key=lambda t: (-(t[1]["size"] or 0), t[0], t[1]["band"]))
    labeled, skipped, already = [], [], []
    done = {(sl.get("leaf"), sl.get("band")) for sl in data.get("specimen_lines", [])}
    for lf, b in todo:
        key = f"{lf}:{b['band']}"
        if (lf, b["band"]) in done:
            already.append({"leaf": lf, "band": b["band"]})     # labeled by hand or on an earlier run
            continue
        rd = readings.get(key)
        text, by = None, None
        if rd is not None:
            if not rd["text"].strip():
                skipped.append({"leaf": lf, "band": b["band"], "why": "reading says: not type"})
                continue
            text = rd["text"]
            by = rd["by"]
            if b.get("ocr") and _norm(b["ocr"]) == _norm(text) and by != "human":
                by = f"{by}+ocr"
        elif trust_ocr and b.get("ocr_match"):
            text, by = b["ocr"], "ocr"
        if text is None:
            skipped.append({"leaf": lf, "band": b["band"], "why": "no reading", "ocr": b.get("ocr"), "n": b["n"]})
            continue
        from .cut import reading_tokens
        n_chars = len(reading_tokens(text))
        if n_chars != b["n"]:
            skipped.append({"leaf": lf, "band": b["band"], "why": f"reading has {n_chars} characters, band has {b['n']} boxes",
                            "text": text})
            continue
        line = (rd or {}).get("line") or b.get("line") or f"b{b['band']}"
        out = label(face, lf, b["band"], text, line, by=by)
        labeled.append({"leaf": lf, "band": b["band"], "line": line, "text": text, "by": by,
                        "added": len(out["added"]), "kept": len(out["kept"])})
    rec = {"face": face.name, "labeled": labeled, "already": already, "skipped": skipped}
    (face.specimens / "labels.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec
