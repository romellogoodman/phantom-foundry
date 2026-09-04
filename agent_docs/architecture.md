# Phantom Foundry — Architecture

An open-source font foundry reviving public domain typefaces from scanned
specimen books, with bespoke tooling. Each font is an artifact that carries
its own provenance, and matures in versions like software.

## Design principles

1. **Files as interface.** Every stage reads plain files and writes plain files.
   No database, no hidden state. The whole pipeline is inspectable, resumable,
   and git-diffable — which matters because the process *is* the research.
2. **Idempotent, per-glyph re-runnable.** `cast -g A` re-traces one letter without
   touching the rest of the face. Glyphs the manifest doesn't know about
   (constructed ones) survive a re-run of `sort`.
3. **Provenance all the way down.** Every glyph names its book, leaf, printed
   page, specimen line, and pixel box — or, if constructed, the traced glyphs
   it was built from. That record ships inside the compiled font (`PHFD` table)
   and beside it (`dist/<face>-provenance.json`, `proofs/face.json`).
4. **Dual-trace when Arrow is used.** potrace is the production tracer: it is
   deterministic, free, and matched the scan at 99%. Quiver's Arrow model
   composes a picture of the letter rather than tracing its edge; when it is
   called, the potrace trace of the same input is the control that makes its
   opinions visible. Credits are scarce; Arrow is a research instrument now.
5. **Human gates between stages, not inside them.** Each stage runs to
   completion machine-fast; review happens on its output before the next stage.
6. **Honest about what's made up.** Letters the specimen never shows are
   constructed from traced parts by explicit recipes, flagged in the glyph lib,
   the provenance table, and the proofs. A constructed Z never passes for a traced one.

## Pipeline

```
Internet Archive
      │  fetch      pull raw JP2 scans + metadata, record provenance in face.yaml
      ▼
specimens/          source pages (not committed; fetch reproduces them)
      │  survey     ink projections find the display lines and letter boxes on a leaf;
      │             writes a numbered sheet + JSON
      │  label      read a line's text across its boxes → manifest rows
      │             (largest size first; later sizes become .six/.eight alternates)
      ▼
glyphs/manifest.csv one row per cut: glyph, unicode, leaf, line, category, box
      │  cut        crop, binarize, flood-fill the letter (+ stacked parts like an i-dot),
      │             tight box in page coords, stem width
      ▼
glyphs/             one PNG (+ raw crop, + JSON record) per letter
      │  cast       potrace control trace; `--engine arrow` ingests an SVG the agent
      │             fetched via Quiver MCP, logging ids + input checksum; `diff` scores them
      ▼
svg/                traces from both engines + deviation metrics
      │  sort       glyphs from one specimen line share its baseline and scale (median of
      │             its caps); map SVG → page px → font units, fix winding, write UFO
      │  construct  recipes in construct.yaml build the letters the specimen lacks
      │  justify    sidebearings from each side's ink profile; target from the printed gaps
      ▼
ufo/                the master source (text, diffable, editable in a font editor)
      │  matrix     name table (provenance, OFL), .notdef/space, fontmake → OTF/TTF,
      │             PHFD provenance table embedded
      ▼
dist/               shippable fonts + provenance.json
      │  proof      scan/trace overlays, cut sheet, alphabet (constructed in gray),
      │             each specimen line re-set in the font over the printed line, face.json
      ▼
proofs/             QA output, the publishable artifacts, and the website's data
```

### Notes

- **Sizes.** Wood type specimens show one design at several sizes, each a
  separate set of blocks. The manifest's `line` names the size; `sort` gives
  each line its own scale so every size lands on the same cap height. The
  default glyph for a letter comes from the largest size it appears at. The
  four sizes of No. 266 differ measurably (stem 13.9% → 16.2% of cap height
  from fifteen-line to five-line) — a finding, kept as data in `face.yaml` `lines`.
- **Spacing.** Wood type is set solid, so the gap between two printed letters
  is the sum of their blocks' shoulders. `survey` measures those gaps; `justify`
  takes its target from them (`face.yaml` `metrics.spacing`). Kerning is a human pass.
- **Alternates.** Same-letter cuts from other sizes are kept as unencoded
  glyphs (`E.six`, `E.eight_2`). Free research data; exposable as a stylistic set later.

## Maturity and releases

`face.yaml` carries `version` and `status`:

- `0.x` **proto** — automatic: traced + constructed, machine-spaced, print noise intact.
- **draft** — a person has reviewed cuts and spacing.
- `1.0` **release** — spaced, kerned, cleaned, tested, full set from the specimen.

`CHANGELOG.md` per face records what changed. Tag `<face>/vX.Y.Z`; the
release workflow rebuilds the face and attaches fonts and proofs. One
monorepo for now; a face that reaches 1.0 can be split out for Google Fonts.

## Repo layout

```
phantom-foundry/
  CLAUDE.md
  agent_docs/
  tools/foundry/       # fetch survey label cut cast diff frame sort construct justify matrix proof
  tests/
  faces/
    <face-name>/
      face.yaml        # source book, leaves + printed pages, PD basis, metrics, lines, version
      CHANGELOG.md
      construct.yaml   # recipes for letters the specimen doesn't show
      specimens/       # fetched scans (ignored) + survey sheet/JSON (committed)
      glyphs/          # manifest.csv + cut PNGs + per-glyph JSON
      svg/arrow/ svg/potrace/
      ufo/  dist/  proofs/  log/
  website/             # Vite + React; type tester; reads proofs/face.json
  .github/workflows/release.yml
```

## Tech choices

- **Python** — fontTools, fontmake, ufoLib2, skia-pathops, svgelements, Pillow, numpy.
- **potrace** for production traces; **Arrow via Quiver's MCP server** for research.
- **UFO** as the master source format; compiled binaries are build artifacts.

## Explicitly deferred

- Kerning (human pass), lowercase and figures for wood-266-class-l (rows are one
  `label` away; `sort` already handles categories and x-height).
- Variable fonts / interpolation. Deskewing slightly rotated scans (the
  six-line baseline drifts ~9 units across the page).
- Automating `label` from the book's OCR text, for a rough-proto pass over
  every usable face in the book.
