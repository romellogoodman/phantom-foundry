"""build — run a face through cut → cast → sort → construct → justify → matrix → proof.

Incremental: each stage records a fingerprint of what it read, and a stage
is skipped when that fingerprint is unchanged and nothing upstream ran.
So `build --all` over a hundred faces touches only the ones whose manifest,
scans, recipes or metrics changed, and a no-op run leaves git clean.
`--force` runs everything. Faces build in parallel, one process each.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .face import FACES_DIR, Face

STAGES = ["cut", "cast", "sort", "construct", "justify", "matrix", "proof"]


def _h(paths: list[Path], extra: str = "") -> str:
    h = hashlib.sha256(extra.encode())
    for p in sorted(paths):
        if p.is_symlink() or p.is_file():
            st = p.stat()
            h.update(f"{p.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:16]


def _section(face: Face, *keys: str) -> str:
    data = face.load()
    return json.dumps({k: data.get(k) for k in keys}, sort_keys=True, default=str)


def fingerprints(face: Face) -> dict[str, str]:
    """What each stage reads, as one short hash per stage."""
    data = face.load()
    leaves = data.get("source", {}).get("leaves", [])
    return {
        "cut": _h([face.manifest_path] + [face.specimen_jp2(l) for l in leaves]),
        "cast": _h(list(face.glyphs.glob("*.png"))),
        "sort": _h(list(face.svg_potrace.glob("*.svg")) + list(face.glyphs.glob("*.json")) + [face.manifest_path],
                   _section(face, "metrics")),
        "construct": _h([face.dir / "construct.yaml"]),
        "justify": _h([], _section(face, "metrics")),
        "matrix": _h([face.yaml_path]),
        "proof": _h([face.yaml_path]),
    }


def build(face: Face, stages: list[str] | None = None, force: bool = False) -> dict:
    stamp_path = face.log / "build.json"
    stamps = json.loads(stamp_path.read_text()) if stamp_path.exists() else {}
    ran, skipped = [], []
    upstream = False
    t0 = time.time()
    for stage in stages or STAGES:
        if stage == "construct" and not (face.dir / "construct.yaml").exists():
            continue
        fp = fingerprints(face)[stage]
        outputs_exist = _outputs_exist(face, stage)
        if not force and not upstream and stamps.get(stage, {}).get("inputs") == fp and outputs_exist:
            skipped.append(stage)
            continue
        _run_stage(face, stage)
        # fingerprint after the run: a stage that writes into its own inputs
        # (sort and justify record metrics in face.yaml) is then at rest
        stamps[stage] = {"inputs": fingerprints(face)[stage], "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        ran.append(stage)
        upstream = True
    face.log.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(json.dumps(stamps, indent=1))
    return {"face": face.name, "ran": ran, "skipped": skipped, "seconds": round(time.time() - t0, 1)}


def _outputs_exist(face: Face, stage: str) -> bool:
    from .sort import ufo_path
    if stage == "cut":
        return any(face.glyphs.glob("*.png"))
    if stage == "cast":
        return any(face.svg_potrace.glob("*.svg"))
    if stage in ("sort", "construct", "justify"):
        return ufo_path(face).exists()
    if stage == "matrix":
        return any(face.dist.glob("*.otf"))
    if stage == "proof":
        return (face.proofs / "face.json").exists()
    return True


def _run_stage(face: Face, stage: str) -> None:
    if stage == "cut":
        from .cut import cut; cut(face)
    elif stage == "cast":
        from .cast import cast_potrace; cast_potrace(face)
    elif stage == "sort":
        from .sort import sort; sort(face)
    elif stage == "construct":
        from .construct import construct; construct(face)
    elif stage == "justify":
        from .justify import justify; justify(face)
    elif stage == "matrix":
        from .matrix import matrix; matrix(face, ["otf", "ttf"])
    elif stage == "proof":
        from .proof import proof; proof(face)


def _build_subprocess(name: str, force: bool) -> dict:
    cmd = [sys.executable, "-m", "foundry.cli", "build", name] + (["--force"] if force else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"face": name, "error": (r.stderr or r.stdout).strip()[-2000:]}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"face": name, "error": r.stdout[-2000:]}


def build_many(names: list[str], jobs: int = 4, force: bool = False) -> dict:
    results = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(_build_subprocess, n, force): n for n in names}
        for f in as_completed(futs):
            results.append(f.result())
    results.sort(key=lambda r: r["face"])
    errors = [r for r in results if r.get("error")]
    return {"faces": len(names), "built": sum(1 for r in results if r.get("ran")),
            "unchanged": sum(1 for r in results if r.get("ran") == []), "errors": errors,
            "results": results}


def all_faces(book: str | None = None) -> list[str]:
    import yaml
    out = []
    for p in sorted(FACES_DIR.glob("*/face.yaml")):
        if book:
            d = yaml.safe_load(p.read_text()) or {}
            if d.get("book") != book and d.get("source", {}).get("archive_id") != book:
                continue
        out.append(p.parent.name)
    return out
