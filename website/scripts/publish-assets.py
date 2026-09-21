#!/usr/bin/env python3
"""Publish what the site shows to the foundry's R2 bucket: every built face's fonts and proofs,
the index and the book list, under the same paths sync-faces.sh uses in public/.
Unchanged files are skipped (sha1 kept in .r2-manifest.json, ignored by git). Needs `wrangler login`.

  scripts/publish-assets.py            upload what changed
  scripts/publish-assets.py --dry      say what would go
"""
import hashlib
import json
import mimetypes
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
BUCKET = "phantom-foundry"
MANIFEST = SITE / ".r2-manifest.json"
TYPES = {".otf": "font/otf", ".ttf": "font/ttf", ".json": "application/json", ".svg": "image/svg+xml"}
# fonts and proofs of a version never change; the index and lists do
CACHE = {"index.json": "public, max-age=300", "books.json": "public, max-age=300"}


def wanted():
    """(key in the bucket, local file) for everything the site reads."""
    for face in sorted((ROOT / "faces").iterdir()):
        proofs = face / "proofs"
        if not (proofs / "face.json").exists():
            continue
        for f in sorted((face / "dist").glob("*.[ot]tf")):
            yield f"fonts/{f.name}", f
        for f in sorted(proofs.iterdir()):
            if f.suffix in (".png", ".jpg", ".json"):
                yield f"proofs/{face.name}/proofs/{f.name}", f
        if any((face / "svg" / "arrow").glob("*.svg")):          # Arrow research: the page links cuts and traces
            for sub in ("glyphs", "svg"):
                for f in sorted((face / sub).rglob("*")):
                    if f.is_file():
                        yield f"proofs/{face.name}/{f.relative_to(face)}", f
    yield "proofs/index.json", ROOT / "showing" / "showing.json"
    yield "proofs/books.json", SITE / "public" / "proofs" / "books.json"


def put(job):
    key, path = job
    ctype = TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    cache = CACHE.get(key.removeprefix("proofs/"), "public, max-age=86400")
    cmd = ["npx", "--no-install", "wrangler", "r2", "object", "put", f"{BUCKET}/{key}", "--file", str(path),
           "--content-type", ctype, "--cache-control", cache, "--remote"]
    for _ in range(3):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            return key, None
    return key, (r.stderr or r.stdout)[-300:]


def main():
    seen = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    jobs, sums = [], {}
    for key, path in wanted():
        if not path.exists():
            continue
        sums[key] = hashlib.sha1(path.read_bytes()).hexdigest()
        if seen.get(key) != sums[key]:
            jobs.append((key, path))
    size = sum(p.stat().st_size for _, p in jobs)
    print(f"{len(sums)} files the site reads; {len(jobs)} new or changed ({size / 1e6:.0f} MB)")
    if "--dry" in sys.argv or not jobs:
        return
    failed = 0
    with ThreadPoolExecutor(8) as pool:
        for n, (key, err) in enumerate(pool.map(put, jobs), 1):
            if err:
                failed += 1
                print("FAILED", key, err.replace("\n", " ")[-200:])
            else:
                seen[key] = sums[key]
            if n % 200 == 0:
                MANIFEST.write_text(json.dumps(seen))
                print(f"  {n}/{len(jobs)}", flush=True)
    MANIFEST.write_text(json.dumps(seen))
    print(f"uploaded {len(jobs) - failed}, failed {failed}")


if __name__ == "__main__":
    main()
