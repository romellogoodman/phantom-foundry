"""names — which founded series have a name the OCR probably misread?

A series is named by the OCR of a caption or page heading, so some names are
wrong ("Qoudy Italic", "Casloe Shaded"). Evidence is comparative: a word seen
once across the shelf that is one or two edits from a word seen in several
books is probably that word. Proposals only; the heading as read stays in
face.yaml (`series`) whatever a face is later called, because the misreading
is part of the provenance and `series` is the key into the book's catalog.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from .book import slug
from .face import FACES_DIR, REPO_ROOT

# ordinary words of type names that one book may use alone without being misread
COMMON = set("""old style oldstyle roman italic bold light heavy black condensed extended expanded extra wide title
text gothic antique latin script shaded open outline lining inline series face no new modern french german english
ionic doric celtic egyptian clarendon tuscan ornamented card circular engravers copperplate typewriter""".split())


def edits(a: str, b: str, cap: int = 2) -> int:
    """Levenshtein distance, given up on beyond `cap`."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def words(series: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z]+", series)]


def audit(faces_dir: Path = FACES_DIR) -> list[dict]:
    faces = []
    for fy in sorted(faces_dir.glob("*/face.yaml")):
        d = yaml.safe_load(fy.read_text()) or {}
        if d.get("series") and d.get("book"):
            faces.append({"name": d["name"], "series": d["series"], "book": d["book"]})
    books_of_word: dict[str, set] = defaultdict(set)
    for f in faces:
        for w in words(f["series"]):
            books_of_word[w.lower()].add(f["book"])
    series_books: dict[str, set] = defaultdict(set)
    for f in faces:
        series_books[f["series"].lower()].add(f["book"])
    known = {w for w, bs in books_of_word.items() if len(bs) >= 3 or w in COMMON}
    taken = Counter(f["name"] for f in faces)
    out = []
    for f in faces:
        fixed, evidence, worst = [], [], 0
        for w in words(f["series"]):
            lw = w.lower()
            if lw in known or len(lw) < 4 or len(books_of_word[lw]) >= 2:
                fixed.append(w)
                continue
            near = sorted(((edits(lw, k), -len(books_of_word[k]), k) for k in known if abs(len(k) - len(lw)) <= 2 and len(k) >= 4))
            near = [n for n in near if n[0] <= 2]
            if not near:
                fixed.append(w)
                continue
            d, nb, k = near[0]
            rivals = [n for n in near[1:] if n[0] == d]
            fixed.append(k.capitalize() if w[0].isupper() else k)
            evidence.append(f'"{w}" is in this book only; "{k}" is in {-nb} books, {d} edit{"s" if d > 1 else ""} away'
                            + (f' (also near: {", ".join(r[2] for r in rivals[:3])})' if rivals else ""))
            worst = max(worst, d + (1 if rivals else 0) + (1 if len(lw) < 6 else 0))
        if not evidence:
            continue
        proposed = re.sub(r"[A-Za-z]+", lambda m, it=iter(fixed): next(it), f["series"])
        code = f["name"].rsplit("-", 1)[-1]
        new_name = f"{slug(proposed)}-{code}" if f["name"].endswith(code) and "-" in f["name"] else slug(proposed)
        clash = new_name != f["name"] and (faces_dir / new_name).exists()
        out.append({"face": f["name"], "heading_as_read": f["series"], "proposed_title": proposed, "proposed_face": new_name,
                    "confidence": "doubtful" if worst > 1 or clash else "obvious",
                    "evidence": "; ".join(evidence) + ("; a face of that name exists in this book: the two are one face split by the misreading" if clash else "")})
    return out


def write(path: Path = REPO_ROOT / "books" / "name-audit.csv") -> dict:
    rows = audit()
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["face", "heading_as_read", "proposed_title", "proposed_face", "confidence", "evidence"])
        w.writeheader()
        w.writerows(rows)
    return {"suspect": len(rows), "obvious": sum(1 for r in rows if r["confidence"] == "obvious"), "file": str(path.relative_to(REPO_ROOT))}
