"""matrix — assemble the UFO's metadata and compile dist/ with fontmake.

Provenance goes into the font itself (name table description + copyright),
so a shipped file can always be traced back to its specimen book and leaf.
Fonts are licensed under the SIL Open Font License; the tooling is MIT.
"""

from __future__ import annotations

import subprocess
import sys

import ufoLib2

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
    info.versionMajor, info.versionMinor = 0, 1
    info.openTypeNameManufacturer = "Phantom Foundry"
    info.openTypeNameManufacturerURL = "https://github.com/romellogoodman/phantom-foundry"
    info.openTypeNameDesigner = "Phantom Foundry (revival)"
    info.openTypeNameLicense = OFL_SHORT
    info.openTypeNameLicenseURL = OFL_URL
    info.openTypeNameDescription = (
        f"Revival of {data.get('title') or fam} from '{src.get('title', '?')[:80]}' "
        f"({src.get('publisher')}, {src.get('date')}), leaves {src.get('leaves')}, "
        f"Internet Archive item {src.get('archive_id')} ({src.get('copyright_status')}). "
        f"Traced from the printed specimen, never from digital font software.")
    info.copyright = (f"Source specimen public domain. Font software (c) {fam} contributors, "
                      f"SIL Open Font License 1.1.")
    ensure_boilerplate_glyphs(font, upm, cap)
    font.save(ufo_path(face), overwrite=True)

    face.dist.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "fontmake", "-u", str(ufo_path(face)), "-o", *formats,
           "--output-dir", str(face.dist), "--verbose", "WARNING"]
    subprocess.run(cmd, check=True)
    built = sorted(p.name for p in face.dist.iterdir() if p.suffix in (".otf", ".ttf"))
    ver = subprocess.run([sys.executable, "-m", "fontmake", "--version"], capture_output=True, text=True).stdout.strip()
    rec = {"family": fam, "formats": formats, "built": built, "glyphs": sorted(font.keys()),
           "fontmake": ver}
    face.log_event("matrix", **rec)
    return {"face": face.name, **rec}
