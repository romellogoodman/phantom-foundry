"""matrix — assemble the UFO's metadata and compile dist/ with fontmake.

Provenance goes into the font itself (name table description + copyright),
so a shipped file can always be traced back to its specimen book and leaf.
Fonts are licensed under the SIL Open Font License; the tooling is MIT.
"""

from __future__ import annotations

import json
import subprocess
import sys

import ufoLib2
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable

from .face import Face
from .sort import ufo_path

OFL_URL = "https://openfontlicense.org"
OFL_SHORT = ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
             "This license is available with a FAQ at: https://openfontlicense.org")


def family_name(face: Face, data: dict) -> str:
    return data.get("family_name") or " ".join(w.capitalize() for w in face.name.split("-"))


def ensure_boilerplate_glyphs(font: ufoLib2.Font, upm: int, cap: int) -> None:
    if ".notdef" not in font:
        g = font.newGlyph(".notdef")
        g.width = int(upm * 0.5)
        pen = g.getPen()
        m = int(upm * 0.05)
        for x0, y0, x1, y1 in ((m, 0, g.width - m, cap), (2 * m, m, g.width - 2 * m, cap - m)):
            pen.moveTo((x0, y0)); pen.lineTo((x1, y0)); pen.lineTo((x1, y1)); pen.lineTo((x0, y1)); pen.closePath()
    if "space" not in font:
        g = font.newGlyph("space")
        g.unicodes = [0x20]
        g.width = int(upm * 0.25)


def provenance(face: Face, data: dict, font: ufoLib2.Font) -> dict:
    """Where every glyph came from, small enough to ship inside the font."""
    src = data.get("source", {})
    pages = data.get("leaf_pages", {})
    manifest = {e.glyph: e for e in face.read_manifest()}
    lines = {(l["leaf"], l["line"]): l["text"] for l in data.get("specimen_lines", [])}
    glyphs = {}
    for g in font:
        if g.name in (".notdef", "space"):
            continue
        srt = g.lib.get("com.phantomfoundry.sort", {})
        con = g.lib.get("com.phantomfoundry.construct")
        rec = {"unicode": f"U+{g.unicodes[0]:04X}" if g.unicodes else None}
        if con:
            rec.update(origin="constructed", built_from=con.get("from", []), note=con.get("note", ""))
        elif g.name in manifest:
            e = manifest[g.name]
            info = face.glyph_info(g.name)
            rec.update(origin="traced", engine=srt.get("engine"), leaf=e.leaf, page=pages.get(e.leaf),
                       line=e.line, printed_in=lines.get((e.leaf, e.line)),
                       box_px=info["tight_box_page"], trace_sha256=srt.get("source_sha256"))
        else:
            rec["origin"] = "unknown"
        glyphs[g.name] = rec
    return {
        "generator": "phantom-foundry", "face": face.name, "version": data.get("version"),
        "status": data.get("status"),
        "source": {k: src.get(k) for k in ("title", "publisher", "date", "archive_id", "url", "ppi",
                                            "copyright_status", "leaves")},
        "leaf_pages": pages, "specimen_lines": data.get("specimen_lines", []),
        "coordinates": "box_px is [x0, y0, x1, y1] on the archive.org leaf at the stated ppi",
        "glyphs": glyphs,
    }


PHFD = "PHFD"   # Phantom Foundry provenance: a JSON blob, read with `ttx -t PHFD font.otf`


def embed_provenance(font_path, prov: dict) -> None:
    tt = TTFont(font_path)
    table = DefaultTable(PHFD)
    table.data = json.dumps(prov, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    tt[PHFD] = table
    tt.save(font_path)


def matrix(face: Face, formats: list[str]) -> dict:
    data = face.load()
    metrics = data["metrics"]
    upm, cap = metrics["upm"], metrics["cap_height"]
    src = data.get("source", {})
    font = ufoLib2.Font.open(ufo_path(face))
    info = font.info
    fam = family_name(face, data)
    info.familyName = fam
    info.styleName = "Regular"
    info.unitsPerEm = upm
    info.capHeight = cap
    info.xHeight = metrics.get("x_height", int(cap * 0.72))
    info.ascender = metrics.get("ascender", int(cap * 1.1))
    info.descender = metrics.get("descender", -int(cap * 0.3))
    ver = str(data.get("version", "0.1.0")).split(".")
    info.versionMajor, info.versionMinor = int(ver[0]), int(ver[1]) if len(ver) > 1 else 0
    info.openTypeNameVersion = f"Version {data.get('version', '0.1.0')} ({data.get('status', 'draft')})"
    info.openTypeNameManufacturer = "Phantom Foundry"
    info.openTypeNameManufacturerURL = "https://github.com/romellogoodman/phantom-foundry"
    info.openTypeNameDesigner = "Phantom Foundry (revival)"
    info.openTypeNameLicense = OFL_SHORT
    info.openTypeNameLicenseURL = OFL_URL
    pages = data.get("leaf_pages", {})
    leaves = ", ".join(f"leaf {l}" + (f" (p. {pages[l]})" if l in pages else "") for l in src.get("leaves", []))
    info.openTypeNameDescription = (
        f"Revival of {data.get('title') or fam} from '{src.get('title', '?')[:80]}' "
        f"({src.get('publisher')}, {src.get('date')}), {leaves}, "
        f"Internet Archive item {src.get('archive_id')} ({src.get('copyright_status')}). "
        f"Traced from the printed specimen, never from digital font software; "
        f"letters the specimen does not show are constructed from traced parts and flagged as such "
        f"in the PHFD table. Version {data.get('version', '0.1.0')} ({data.get('status', 'draft')}).")
    have = {u for g in font for u in g.unicodes}
    covered = [l["text"] for l in data.get("specimen_lines", [])
               if all(ord(c) in have for c in l["text"] if not c.isspace())]
    info.openTypeNameSampleText = max(covered, key=len) if covered else None
    info.copyright = (f"Source specimen public domain. Font software (c) {fam} contributors, "
                      f"SIL Open Font License 1.1.")
    ensure_boilerplate_glyphs(font, upm, cap)
    font.save(ufo_path(face), overwrite=True)

    face.dist.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "fontmake", "-u", str(ufo_path(face)), "-o", *formats,
           "--output-dir", str(face.dist), "--verbose", "WARNING"]
    subprocess.run(cmd, check=True)
    built = sorted(p.name for p in face.dist.iterdir() if p.suffix in (".otf", ".ttf"))
    prov = provenance(face, data, font)
    for name in built:
        embed_provenance(face.dist / name, prov)
    (face.dist / f"{face.name}-provenance.json").write_text(json.dumps(prov, indent=2))
    ver = subprocess.run([sys.executable, "-m", "fontmake", "--version"], capture_output=True, text=True).stdout.strip()
    rec = {"family": fam, "version": data.get("version", "0.1.0"), "status": data.get("status", "draft"),
           "formats": formats, "built": built, "glyphs": sorted(font.keys()), "fontmake": ver}
    face.log_event("matrix", **rec)
    return {"face": face.name, **rec}
