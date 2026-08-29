# Phantom Foundry — Architecture

An open-source font foundry reviving public domain typefaces from scanned
specimen books, using Quiver AI's Arrow model (image → SVG) and bespoke tooling.

## Design principles

1. **Files as interface.** Every stage reads plain files and writes plain files.
   No database, no hidden state. The whole pipeline is inspectable, resumable,
   and git-diffable — which matters because the process *is* the research.
2. **Idempotent, per-glyph re-runnable.** `cast A` re-traces one letter without
   touching the rest of the face.
3. **Provenance all the way down.** Every glyph can name its book, page, and
   scan. That provenance ships in the final font's metadata.
4. **Dual-trace always.** Every Arrow cast runs a potrace control trace
   alongside it. The deterministic trace is the research instrument that makes
   Arrow's opinions visible (trace vs. redraw).
5. **Human gates between stages, not inside them.** Each stage runs to
   completion machine-fast; review happens on its output before the next stage.

## Pipeline

Six stages, named from foundry vocabulary. Each is a small CLI; a coding agent
drives them (and calls Arrow via Quiver's MCP server), but every tool is also
usable by hand.

```
Internet Archive
      │  fetch      pull raw JP2 scans + metadata, record provenance
      ▼
specimens/          source pages
      │  cut        punchcutting: crop individual letters from pages
      ▼
glyphs/             one image per letter + manifest
      │  cast       vectorize via Arrow (MCP) — plus potrace control trace
      ▼
svg/                raw traces from both engines + deviation metrics
      │  sort       normalize: shared UPM, baselines, winding, counters
      ▼
ufo/                clean, metric-aligned glyph sources
      │  matrix     assemble: UFO → fontmake → OTF/TTF, metadata, license
      ▼
dist/               shippable font files
      │  proof      render specimen sheets, waterfalls, scan overlays
      ▼
proofs/             QA output and the publishable artifacts
```

### Stage notes

- **fetch** — given an archive.org item ID, download the raw JP2/original
  scans (never the compressed PDF renders), stash metadata and the public
  domain claim in `face.yaml`.
- **cut** — extraction is the messiest human step. Start manual/CV-assisted
  (threshold + connected components, or a simple crop UI); output is one PNG
  per glyph with a manifest row (face, page, source coordinates, nominal size).
- **cast** — the Arrow call, one glyph at a time, through the MCP server.
  Always also runs potrace on the same input. Emits both SVGs plus a diff
  metric so systematic deviation (Arrow's "taste") accumulates as data.
- **sort** — scale to UPM 1000, align baselines, normalize path direction and
  winding so counters punch correctly, merge to single filled outlines, emit a
  metrics report (x-height, cap height, detected stem widths).
- **matrix** — build a UFO as the interchange format (text-based, diffable,
  editable in Glyphs/RoboFont when hand-correction is needed), then compile
  with fontTools/fontmake. Initial auto-sidebearings; kerning is a later,
  human pass. License: OFL. Provenance goes in the name table.
- **proof** — waterfall sheets, pangrams, and the signature artifact: the
  original specimen page re-set in the revived digital font, overlaid on the
  scan. HTML first, print-ready PDF second.

## Repo layout

```
phantom-foundry/
  CLAUDE.md
  agent_docs/
  tools/               # fetch, cut, cast, sort, matrix, proof
  faces/
    <face-name>/
      face.yaml        # source book, pages, PD basis, status
      specimens/       # fetched page scans (or crops)
      glyphs/          # cut letter images + manifest
      svg/
        arrow/         # Arrow casts
        potrace/       # control traces
      ufo/
      dist/            # compiled OTF/TTF + license
      proofs/
      log/             # cast runs: model version, params, decisions
```

One directory per revived face; the directory *is* the record of the revival.

## Tech choices (provisional)

- **Python** for the tools — fontTools, fontmake, ufoLib2, potrace bindings,
  Pillow/OpenCV all live there. Font tooling's center of gravity is Python.
- **Arrow via Quiver's MCP server**, orchestrated by a coding agent; tools
  print machine-readable output so the agent can chain them.
- **UFO** as the master source format; compiled binaries are build artifacts.

## Explicitly deferred

- Variable fonts / multi-weight interpolation (compatibilization lives in
  `sort` when the time comes; UFO + designspace already leave the door open).
- Kerning beyond auto-spacing.
- Full character sets — first faces target caps + figures from display faces.
