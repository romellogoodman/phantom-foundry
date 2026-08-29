"""A face directory: the complete record of one revival.

faces/<name>/
  face.yaml      source book, leaves, public-domain basis, metrics, status
  specimens/     fetched page scans (jp2) + small jpg previews
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

REPO_ROOT = Path(__file__).resolve().parents[2]
FACES_DIR = REPO_ROOT / "faces"

MANIFEST_FIELDS = ["glyph", "unicode", "leaf", "x", "y", "w", "h", "notes"]


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
            return {"name": self.name, "status": "draft",
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

    # -- manifest -------------------------------------------------------
    def read_manifest(self) -> list[GlyphEntry]:
        if not self.manifest_path.exists():
            return []
        with self.manifest_path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        return [GlyphEntry(r["glyph"], r.get("unicode", ""), int(r["leaf"]),
                           int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"]),
                           r.get("notes", "")) for r in rows]

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
