"""fetch — pull raw page scans from an Internet Archive item.

Downloads the single-page processed JP2 for each requested leaf (never the
compressed PDF render), writes a small JPEG preview, and records provenance
in face.yaml.
"""

from __future__ import annotations

from pathlib import Path

import requests
from PIL import Image

from .face import Face

IA = "https://archive.org"


def item_metadata(archive_id: str) -> dict:
    r = requests.get(f"{IA}/metadata/{archive_id}", timeout=60)
    r.raise_for_status()
    return r.json()


def leaf_jp2_url(archive_id: str, leaf: int) -> str:
    return (f"{IA}/download/{archive_id}/{archive_id}_jp2.zip/"
            f"{archive_id}_jp2%2F{archive_id}_{leaf:04d}.jp2")


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    return dest


def fetch(face: Face, archive_id: str, leaves: list[int], preview_width: int = 1200) -> dict:
    face.ensure_layout()
    meta = item_metadata(archive_id)
    m = meta["metadata"]
    data = face.load()
    date = m.get("date")
    if isinstance(date, list):
        date = date[0]
    src = data.get("source", {})
    src.update({
        "archive_id": archive_id,
        "title": m.get("title"),
        "creator": m.get("creator"),
        "publisher": m.get("publisher"),
        "date": date,
        "ppi": int(m["ppi"]) if m.get("ppi") else None,
        "url": f"{IA}/details/{archive_id}",
        "copyright_status": m.get("possible-copyright-status"),
        "contributor": m.get("contributor"),
    })
    src["leaves"] = sorted(set(src.get("leaves", [])) | set(leaves))
    data["source"] = src
    data.setdefault("metrics", {"upm": 1000, "cap_height": 700})
    face.save(data)

    fetched = []
    for leaf in leaves:
        jp2 = face.specimen_jp2(leaf)
        if not jp2.exists():
            download(leaf_jp2_url(archive_id, leaf), jp2)
        im = Image.open(jp2)
        w, h = im.size
        prev = im.convert("RGB")
        prev.thumbnail((preview_width, preview_width * 4))
        prev.save(face.specimen_preview(leaf), quality=80)
        fetched.append({"leaf": leaf, "path": str(jp2), "size": [w, h]})
        face.log_event("fetch", archive_id=archive_id, leaf=leaf, url=leaf_jp2_url(archive_id, leaf),
                       size=[w, h], ppi=src.get("ppi"))
    return {"face": face.name, "archive_id": archive_id, "fetched": fetched}
