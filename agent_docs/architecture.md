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

Two ways in. One face at a time: `fetch` a leaf, `survey` it, `label` each
line by hand. A whole book: `shelve` it, `catalog` every leaf, `found` faces
from the catalog's series, fill their manifests from *readings*. Both end in
the same per-face stages, run by `build`.

```
Internet Archive
      │  shelve     the whole book: every leaf's JP2 + the archive's OCR → books/<id>/ (ignored)
      │  catalog    survey every leaf; read the caption over each showing ("42 Point Cadillac
      │             Condensed", "No. 266— Class L Fifteen Line") for its size and series;
      │             band crops with numbered boxes; page numbers from the folios → catalog.json
      │  found      start faces/<name>/ from a series: face.yaml with the book's provenance,
      │             the leaves linked (not copied), their surveys copied
      │  read       what a band says, read from its crop by a person or Claude — one token per
      │             box: a character, [fi] for touching letters, ? unreadable, ~ not a letter —
      │             → books/<id>/readings.json. The OCR is a cross-check, never a source: it
      │             misreads display type ("PROSPEROIS") in ways that pass a character count
      │  label --auto  manifest rows from the readings, largest size first
      ▼
      │  fetch      (one face) pull raw JP2 scans + metadata, record provenance in face.yaml
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
proofs/             QA output, checks.json, the publishable artifacts, and the website's data
      │  build      cut → cast → sort → construct → justify → matrix → proof, skipping stages
      │             whose inputs (by fingerprint) haven't changed; --all / --book in parallel
      │  showing    one sheet across every face — status, glyph counts, warnings — showing/
```

### Notes

- **Bands.** A metal-type showing prints each size as a line of CAPITALS
  over a line of Mixed case with figures. Both are one `line` (one scale,
  from the capitals) but two `band`s (two baselines). A size with no
  capitals takes its cap height from the tallest lowercase (ascenders).
- **Checks.** `proof` writes `checks.json`: trace-vs-scan overlap below a
  size-aware floor (95% at 300 px cap height, 90% at 30 pt), a capital more
  than 12% off its line's cap height (a misread box), more than four
  contours (specks), bands left unread, fewer than ten glyphs. `showing`
  puts the faces that warned first. Review starts there, not at a hundred
  alphabet sheets.
- **Scale.** Fonts are built with fontmake under `SOURCE_DATE_EPOCH` (HEAD's
  commit time) so an unchanged face rebuilds byte-identical; `build` skips
  unchanged stages; per-glyph overlay sheets are drawn only for faces with
  Arrow research; raw crops, survey sheets and line proofs are JPEG. A
  founded face costs about 7 MB on disk, 3–4 MB packed in git.
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
  tools/foundry/       # shelve catalog series found read label | fetch survey | cut cast diff frame
                       # sort construct justify matrix proof | build showing
  tests/
  books/
    <archive_id>/
      book.yaml        # item metadata, page count, when shelved
      jp2/ ocr/ sheets/   # every leaf, the OCR split per leaf, survey sheets + band crops (ignored)
      survey/          # leafNNNN.json: display bands + letter boxes per leaf
      catalog.json     # every band with its caption's size and series; series index
      readings.json    # what each band says, by whom — the labeling record
  showing/             # index.html + showing.json across every face
  faces/
    <face-name>/
      face.yaml        # source book, leaves + printed pages, PD basis, metrics, lines, version
      CHANGELOG.md
      construct.yaml   # recipes for letters the specimen doesn't show
      specimens/       # scans (ignored; linked from books/ or fetched) + survey sheet/JSON + labels.json
      glyphs/          # manifest.csv (glyph, unicode, leaf, line, band, category, box) + cuts + per-glyph JSON
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
- Constructed letters for founded faces: a proto built from the book has only
  what the page shows; constructing the rest is part of promoting a face to draft.
- Variable fonts / interpolation. Deskewing slightly rotated scans (the
  six-line baseline drifts ~9 units across the page).
- Sizes under 30 pt (about 115 px cap height at 400 ppi): the survey finds them,
  the catalog lists them, `label --auto --min-tall` leaves them out.
