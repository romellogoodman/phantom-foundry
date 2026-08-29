# Phantom Foundry

Open-source font foundry reviving public domain typefaces from scanned
specimen books, using Quiver AI's Arrow model (image → SVG) and bespoke
Python tooling.

## Why

Revivals work from printed specimens, never digital fonts — typeface designs
aren't copyrightable in the US, but font software is. The pipeline doubles as
design research: the gap between the historical scan and Arrow's
interpretation is the subject, not a defect. Traces, logs, and proofs are
deliverables (research book + blog series), so never discard intermediate
artifacts to "clean up."

## What

Six-stage pipeline, each a small CLI named from foundry vocabulary:
`fetch → cut → cast → sort → matrix → proof`. Files are the only interface
between stages. One directory per typeface under `faces/` holds that
revival's complete record, from source scan to proof sheet.

- `tools/` — the six pipeline CLIs (Python)
- `faces/<name>/` — per-face working dirs (specimens → glyphs → svg → ufo → dist → proofs)
- `agent_docs/architecture.md` — pipeline stages, repo layout, design principles. Read before touching pipeline code.

## How

- Python: fontTools / fontmake / ufoLib2 for font work; potrace for control traces.
- UFO is the master source format. `dist/` holds compiled build artifacts — never hand-edit them.
- Arrow is called through Quiver's MCP server. Every Arrow cast must also run
  the potrace control trace on the same input — it's the research instrument,
  not optional QA.
- Setup: `uv sync` (Python 3.12 via uv; potrace via `brew install potrace`).
- Tests: `.venv/bin/pytest` — geometry tests for outline parsing and sort normalization.
- Run a stage: `.venv/bin/foundry <stage> <face> [--glyph G]`; `foundry --help` lists all six.
  Rebuild a face end to end: `cut → cast → sort → matrix → proof` (fetch once).
- Arrow casts: the agent calls `mcp__quiver__create_vectorization` (model `arrow-1.1`)
  with the cut PNG, polls `get_task`, saves the SVG, then `foundry cast --engine arrow --from <svg>`.
  Credits are scarce — never call Arrow on an input you haven't looked at first.
