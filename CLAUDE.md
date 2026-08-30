# Phantom Foundry

Open-source font foundry reviving public domain typefaces from scanned
specimen books, with bespoke Python tooling. Fonts mature in versions like
software: **proto** (traced + constructed, machine-spaced) → **draft** (reviewed)
→ **release** (1.0: spaced, kerned, cleaned).

## Why

Revivals work from printed specimens, never digital fonts — typeface designs
aren't copyrightable in the US, but font software is. The process is the
research: traces, logs, and proofs are deliverables (research book + blog
series), so never discard intermediate artifacts to "clean up." The gap
between the historical scan and a tracer's interpretation is a subject, not a
defect; Quiver's Arrow model turned out to *depict* letters rather than trace
them, so potrace is the production tracer and Arrow is a research instrument.

## What

Pipeline of small CLIs named from foundry vocabulary; files are the only
interface between stages. One directory per typeface under `faces/` holds
that revival's complete record, from source scan to proof sheet.

```
fetch → survey → label → cut → cast → sort → construct → justify → matrix → proof
```

- `tools/foundry/` — the CLIs (Python). `agent_docs/architecture.md` explains
  each stage and the design principles. Read it before touching pipeline code.
- `faces/<name>/` — `face.yaml` (provenance, metrics, version, specimen lines),
  `glyphs/manifest.csv` (one row per cut: glyph, unicode, leaf, line, category,
  box), `construct.yaml` (recipes for letters the specimen doesn't show),
  `CHANGELOG.md`, and the stage outputs: specimens → glyphs → svg → ufo → dist → proofs, plus `log/`.
- `website/` — Vite + React specimen site with a type tester; reads each
  face's `proofs/face.json`. `scripts/sync-faces.sh` mirrors faces into `public/`.

## How

- Python 3.12 via uv: `uv sync`. potrace via `brew install potrace`.
- Tests: `.venv/bin/pytest` (geometry, sort placement, construct, justify).
- Run a stage: `.venv/bin/foundry <stage> <face> [--glyph G]`; `foundry --help` lists them.
  Rebuild a face: `cut → cast → sort → construct → justify → matrix → proof` (fetch/survey/label once).
- New face: `fetch`, then `survey --leaf N` (finds lines and letter boxes, writes
  a numbered sheet), then `label --band B --text "WORDS" --line <size>` per line,
  largest size first — the first showing of a letter gets the plain name, later
  sizes become `.six`/`.eight` alternates (unencoded).
- UFO is the master source; `dist/` is compiled — never hand-edit it. Glyphs
  not in the manifest (constructed ones) survive `sort`; `justify` re-spaces everything.
- Constructed letters live in `construct.yaml` and are flagged everywhere
  (glyph lib, `face.json`, gray in `proofs/alphabet.png`). Never let one pass as traced.
- Releases: bump `version` in `face.yaml`, add to `CHANGELOG.md`, commit, tag
  `<face>/vX.Y.Z`. `.github/workflows/release.yml` rebuilds and attaches fonts on push of the tag.
- Arrow: called through Quiver's MCP server (`mcp__quiver__create_vectorization`,
  model `arrow-1.1`), then `foundry cast --engine arrow --from <svg>` to log it;
  every Arrow cast must also have the potrace trace of the same input.
  Credits are scarce — never call Arrow on an input you haven't looked at first.
- Scans (`specimens/*.jp2`) are not committed; `fetch` reproduces them from `face.yaml`.
