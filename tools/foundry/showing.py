"""showing — one sheet across every face: a type founder's showing.

showing/showing.json  every face's summary (from proofs/face.json + checks.json)
showing/index.html    the faces in a table: name, status, glyphs, sizes, warnings,
                      the alphabet proof — sorted so the ones that warned come first
"""

from __future__ import annotations

import html
import json
import time

from .build import all_faces
from .face import FACES_DIR, REPO_ROOT, Face

SHOWING_DIR = REPO_ROOT / "showing"


def summary(face: Face) -> dict | None:
    fj = face.proofs / "face.json"
    if not fj.exists():
        return None
    d = json.loads(fj.read_text())
    ck = face.proofs / "checks.json"
    checks = json.loads(ck.read_text()) if ck.exists() else {"status": "unknown", "warnings": 0, "infos": 0, "items": []}
    glyphs = d.get("glyphs", [])
    encoded = [g for g in glyphs if g.get("encoded") and g.get("name") != "space"]
    src = d.get("source", {})
    sizes = sorted({(g.get("line") or "").split(":")[-1] for g in glyphs if g.get("line")} - {""})
    covered = [l for l in d.get("specimen_lines", []) if l.get("proof") and not l.get("missing")]
    return {
        "name": d["name"], "family": d.get("family"), "title": d.get("title"), "series": d.get("series"),
        "version": d.get("version"), "status": d.get("status"), "book": d.get("book") or src.get("archive_id"),
        "leaves": src.get("leaves", []), "pages": [d.get("leaf_pages", {}).get(str(l)) or d.get("leaf_pages", {}).get(l)
                                                  for l in src.get("leaves", [])],
        "encoded": len(encoded), "traced": sum(1 for g in encoded if not g.get("constructed")),
        "constructed": sum(1 for g in encoded if g.get("constructed")),
        "alternates": sum(1 for g in glyphs if g.get("alternate_of")),
        "caps": sum(1 for g in encoded if g.get("category") == "cap"),
        "lower": sum(1 for g in encoded if g.get("category") == "lower"),
        "figures": sum(1 for g in encoded if g.get("category") == "figure"),
        "sizes": sizes, "lines": len(d.get("specimen_lines", [])),
        "sample": max((l["text"] for l in covered), key=len, default=None),
        "line_proof": covered[0]["proof"] if covered else None,
        "fonts": d.get("fonts", []),
        "checks": {"status": checks["status"], "warnings": checks.get("warnings", 0), "infos": checks.get("infos", 0),
                   "items": checks.get("items", [])},
        "readers": sorted({l.get("by") or "human" for l in d.get("specimen_lines", [])}),
    }


def showing(book: str | None = None) -> dict:
    SHOWING_DIR.mkdir(exist_ok=True)
    rows = [s for s in (summary(Face(n)) for n in all_faces(book)) if s]
    rows.sort(key=lambda r: (r["checks"]["status"] != "warn", -r["checks"]["warnings"], r["name"]))
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "faces": len(rows),
           "warned": sum(1 for r in rows if r["checks"]["status"] == "warn"),
           "encoded_glyphs": sum(r["encoded"] for r in rows), "faces_list": rows}
    (SHOWING_DIR / "showing.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    parts = [f"<h1>Phantom Foundry — showing <small>{out['faces']} faces · {out['encoded_glyphs']} encoded glyphs · "
             f"{out['warned']} with warnings · {out['generated']}</small></h1>",
             "<table><thead><tr><th>face</th><th>status</th><th>glyphs</th><th>A/a/1</th><th>sizes</th><th>pages</th>"
             "<th>warnings</th><th>alphabet</th></tr></thead><tbody>"]
    for r in rows:
        warn_notes = "<br>".join(html.escape(f"{i.get('glyph') or i.get('line') or i.get('leaf', '')}: {i['check']} {i.get('value', '')}")
                                 for i in r["checks"]["items"] if i["level"] == "warn")[:2000]
        pages = ", ".join(str(p) for p in r["pages"] if p) or ", ".join(f"leaf {l}" for l in r["leaves"])
        parts.append(
            f"<tr class='{r['checks']['status']}'><td><a href='../faces/{r['name']}/proofs/index.html'>{html.escape(r['name'])}</a>"
            f"<br><small>{html.escape(r['title'] or '')} · v{r['version']} {r['status']}</small></td>"
            f"<td>{r['checks']['status']}</td><td>{r['encoded']}</td><td>{r['caps']}/{r['lower']}/{r['figures']}</td>"
            f"<td>{html.escape(' '.join(r['sizes']))}</td><td>{html.escape(pages)}</td><td><small>{warn_notes}</small></td>"
            f"<td><img src='../faces/{r['name']}/proofs/alphabet.png' loading='lazy' style='height:70px'></td></tr>")
    parts.append("</tbody></table>")
    (SHOWING_DIR / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Phantom Foundry — showing</title>"
        "<style>body{font-family:system-ui;margin:2rem}table{border-collapse:collapse;font-size:13px}"
        "td,th{border-bottom:1px solid #ddd;padding:6px 8px;vertical-align:top;text-align:left}tr.warn td{background:#fff6e5}"
        "small{color:#666}</style><body>" + "\n".join(parts))
    return {k: out[k] for k in ("faces", "warned", "encoded_glyphs")} | {"showing": "showing/index.html"}
