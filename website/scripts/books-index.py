#!/usr/bin/env python3
"""Every specimen book on the shelf, for the site's process page: what it is, where the scan
lives, how much large type the survey found in it, and how many faces it has given so far.
Reads ../books/*/book.yaml, catalog.json and ../faces/*/face.yaml; writes public/proofs/books.json."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "website" / "public" / "proofs" / "books.json"


def first(v):
    return v[0] if isinstance(v, list) and v else v


# the archive's creator field is uneven ("Daystrom, inc" is American Type Founders' later owner)
ISSUERS = [
    (r"american type|daystrom", "American Type Founders"), (r"barnhart", "Barnhart Brothers & Spindler"),
    (r"mackellar", "MacKellar, Smiths & Jordan"), (r"bruce", "George Bruce's Son & Co."),
    (r"keystone", "Keystone Type Foundry"), (r"inland", "Inland Type Foundry"), (r"farmer", "Farmer, Little & Co."),
    (r"cleveland", "Cleveland Type Foundry"), (r"boston type", "Boston Type Foundry"),
    (r"allison|franklin type", "Franklin Type Foundry"), (r"palmer", "Palmer & Rey"),
    (r"cincinnati", "Cincinnati Type Foundry"), (r"wm\.? h\.? page|page & co", "Wm. H. Page & Co."),
    (r"h\.? ?w\.? caslon", "H. W. Caslon & Co."), (r"miller", "Miller & Richard"),
    (r"stephenson", "Stephenson, Blake & Co."), (r"deberny", "Deberny & Cie"), (r"bauer", "Bauersche Giesserei"),
    (r"ensched", "Joh. Enschedé en Zonen"), (r"krebs", "Benjamin Krebs Nachfolger"),
]


def issuer(b):
    blob = " ".join(str(first(b.get(k)) or "") for k in ("creator", "publisher", "title")).lower()
    for pattern, name in ISSUERS:
        if re.search(pattern, blob):
            return name
    raw = str(first(b.get("creator")) or first(b.get("publisher")) or "")
    return re.sub(r",? ?(\(?firm\)?|type[- ]?founders?\b.*|\[from old catalog\]|creator)$", "", raw, flags=re.I).strip(" ,.")


def main():
    founded, built = {}, {}
    for fy in (ROOT / "faces").glob("*/face.yaml"):
        d = yaml.safe_load(fy.read_text()) or {}
        bid = d.get("book") or (d.get("source") or {}).get("archive_id")
        if not bid:
            continue
        founded[bid] = founded.get(bid, 0) + 1
    showing = ROOT / "showing" / "showing.json"          # a strike counts when the site lists it
    for f in json.loads(showing.read_text())["faces_list"] if showing.exists() else []:
        if not f.get("suspect"):
            built[f["book"]] = built.get(f["book"], 0) + 1
    books = []
    for by in sorted((ROOT / "books").glob("*/book.yaml")):
        b = yaml.safe_load(by.read_text()) or {}
        bid = b.get("archive_id") or by.parent.name
        year = re.search(r"1[4-9]\d\d", str(b.get("date") or ""))
        rec = {
            "id": bid,
            "title": re.split(r"[.:;]", str(b.get("title") or bid))[0].strip()[:90],
            "issuer": issuer(b),
            "year": int(year.group()) if year else None,
            "ppi": b.get("ppi"),
            "leaves": b.get("imagecount"),
            "url": b.get("url"),
            "contributor": b.get("contributor"),
            "faces": built.get(bid, 0),
            "founded": founded.get(bid, 0),
        }
        cp = by.parent / "catalog.json"
        if cp.exists():
            c = json.loads(cp.read_text())
            bands = [x for leaf in c["leaves"].values() for x in leaf["bands"]]
            rec["lines"] = sum(1 for x in bands if x["tall_px"] >= 115 and x["n"] >= 3)
            rec["named"] = sum(1 for x in bands if x["tall_px"] >= 115 and x["n"] >= 3 and x.get("series"))
            rec["series"] = len(c.get("series", {}))
        books.append(rec)
    books.sort(key=lambda r: (-(r["faces"]), -(r.get("named") or 0), -(r.get("lines") or 0), r["year"] or 0))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"books": books}, indent=1, ensure_ascii=False))
    print(f"{len(books)} books, {sum(r['faces'] for r in books)} faces built → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
