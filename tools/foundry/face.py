"""A face directory: the complete record of one revival.

faces/<name>/
  face.yaml      source book, leaves, public-domain basis, metrics, status
  specimens/     fetched page scans (jp2) + small jpg previews (+ survey sheets)
  glyphs/        manifest.csv + one cut PNG per glyph
  svg/arrow/     Arrow casts        svg/potrace/  control traces
  ufo/           normalized glyph sources (UFO)
  dist/          compiled OTF/TTF
  proofs/        specimen sheets, overlays
  log/           one JSON line per cast run
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from fontTools.misc.filenames import userNameToFileName

REPO_ROOT = Path(__file__).resolve().parents[2]


def fname(glyph: str) -> str:
    """Filesystem-safe stem for a glyph's per-glyph files, by the UFO convention
    (`I` → `I_`, `E.six` → `E_.six`) so `I` and `i` never share a file on a
    case-insensitive disk. Same stem the UFO uses for the .glif."""
    return userNameToFileName(glyph)
FACES_DIR = REPO_ROOT / "faces"

# A manifest row is one cut: which letter, where on which page, and how it
# sits in the specimen. `line` names the specimen line (wood type is shown
# per size: "five", "eight", "fifteen"); glyphs from the same leaf+line share
# a baseline and a scale in `sort`. `category` says how the glyph relates to
# that baseline: cap | figure | lower | punct. `band` is the survey band the
# cut came from: a size shown as two lines (CAPITALS / Mixed case 78) is one
# `line` with one scale but two bands with two baselines.
MANIFEST_FIELDS = ["glyph", "unicode", "leaf", "line", "band", "category", "x", "y", "w", "h", "notes"]
CATEGORIES = ("cap", "figure", "lower", "punct")


@dataclass
class GlyphEntry:
    glyph: str
    unicode: str
    leaf: int
    x: int
    y: int
    w: int
    h: int
    notes: str = ""
    line: str = ""
    category: str = "cap"
    band: str = ""

    @property
    def group(self) -> str:
        """Key shared by every glyph printed at the same size on a leaf (one scale)."""
        return f"{self.leaf}:{self.line or 'line'}"

    @property
    def baseline_group(self) -> str:
        """Key shared by every glyph printed on the same band (one baseline)."""
        return f"{self.group}:{self.band}"

    @property
    def char(self) -> str | None:
        return chr(int(self.unicode, 16)) if self.unicode else None


class Face:
    def __init__(self, name: str):
        self.name = name
        self.dir = FACES_DIR / name
        self.yaml_path = self.dir / "face.yaml"
        self.specimens = self.dir / "specimens"
        self.glyphs = self.dir / "glyphs"
        self.svg_arrow = self.dir / "svg" / "arrow"
        self.svg_potrace = self.dir / "svg" / "potrace"
        self.ufo = self.dir / "ufo"
        self.dist = self.dir / "dist"
        self.proofs = self.dir / "proofs"
        self.log = self.dir / "log"
        self.manifest_path = self.glyphs / "manifest.csv"

    # -- layout ---------------------------------------------------------
    def ensure_layout(self) -> None:
        for d in (self.specimens, self.glyphs, self.svg_arrow, self.svg_potrace,
                  self.ufo, self.dist, self.proofs, self.log):
            d.mkdir(parents=True, exist_ok=True)

    # -- face.yaml ------------------------------------------------------
    def load(self) -> dict:
        if not self.yaml_path.exists():
            return {"name": self.name, "status": "proto",
                    "metrics": {"upm": 1000, "cap_height": 700}}
        return yaml.safe_load(self.yaml_path.read_text()) or {}

    def save(self, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    # -- specimens ------------------------------------------------------
    def specimen_jp2(self, leaf: int) -> Path:
        return self.specimens / f"leaf{leaf:04d}.jp2"

    def specimen_preview(self, leaf: int) -> Path:
        return self.specimens / f"leaf{leaf:04d}_preview.jpg"

    # -- glyph records --------------------------------------------------
    def glyph_info(self, glyph: str) -> dict:
        """The cut's record (tight box, ink stats) written by `cut`."""
        p = self.glyphs / f"{fname(glyph)}.json"
        if not p.exists():
            raise FileNotFoundError(f"{glyph} has not been cut yet ({p})")
        return json.loads(p.read_text())

    # -- manifest -------------------------------------------------------
    def read_manifest(self) -> list[GlyphEntry]:
        if not self.manifest_path.exists():
            return []
        with self.manifest_path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        out = []
        for r in rows:
            cat = (r.get("category") or "cap").strip()
            if cat not in CATEGORIES:
                raise ValueError(f"manifest: glyph {r['glyph']!r} has unknown category {cat!r}; "
                                 f"expected one of {CATEGORIES}")
            out.append(GlyphEntry(r["glyph"], (r.get("unicode") or "").strip(), int(r["leaf"]),
                                  int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"]),
                                  r.get("notes") or "", (r.get("line") or "").strip(), cat,
                                  (r.get("band") or "").strip()))
        return out

    def write_manifest(self, entries: list[GlyphEntry]) -> None:
        self.glyphs.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
            w.writeheader()
            for e in entries:
                w.writerow({k: getattr(e, k) for k in MANIFEST_FIELDS})

    def manifest_entry(self, glyph: str) -> GlyphEntry:
        for e in self.read_manifest():
            if e.glyph == glyph:
                return e
        raise KeyError(f"glyph {glyph!r} not in {self.manifest_path}")

    # -- log ------------------------------------------------------------
    def log_event(self, stage: str, **fields) -> None:
        self.log.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "stage": stage, **fields}
        with (self.log / f"{stage}.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def read_log(self, stage: str) -> list[dict]:
        p = self.log / f"{stage}.jsonl"
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
