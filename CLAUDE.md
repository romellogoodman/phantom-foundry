# Phantom Foundry

Phantom Foundry publishes **strikes**: faithful impressions of public domain type,
traced from scanned specimen books and ready to be justified by someone else. A
strike is one typeface as ONE book shows it; the same face in four catalogues is
four strikes (`<series>-<bookcode>`, e.g. `goudy-oldstyle-atf1917`). In code and
data a strike is still a **proto** (traced, machine-spaced) → **draft** (reviewed)
→ **release** (1.0: spaced, kerned, cleaned); most faces are meant to stay strikes.

Wherever the project describes itself, say exactly this about models, no more and
no less: coding agents built the pipeline; models read which letter is in a box
and read captions; no model draws a letterform — every outline is traced from a
printed page by potrace. The project's argument is "you can check our work", so
anything that makes the record less true than the work is the first bug to fix.

## Why

Revivals work from printed specimens, never digital fonts — typeface designs
aren't copyrightable in the US, but font software is. The process is the
research: traces, logs, and proofs are deliverables (research book + blog
series). What can't be made again is never discarded: the manifest, `face.yaml`,
readings, recipes, logs, Arrow casts, and any UFO a person has edited. What the
pipeline rebuilds byte-for-byte from those is kept for draft and release faces
but not committed for protos — `foundry build <face>` is the way back. The gap
between the historical scan and a tracer's interpretation is a subject, not a
defect; Quiver's Arrow model turned out to *depict* letters rather than trace
them, so potrace is the production tracer and Arrow is a research instrument.

## What

Pipeline of small CLIs named from foundry vocabulary; files are the only
interface between stages. One directory per typeface under `faces/` holds
that revival's complete record, from source scan to proof sheet.

```
one face:  fetch → survey → label ─┐
a book:    shelve → catalog → found → read | read-models → label --auto ─┴→ cut → cast → sort → construct → justify → matrix → proof
                                                            (= build)                              → showing
```

- `tools/foundry/` — the CLIs (Python). `agent_docs/architecture.md` explains
  each stage and the design principles. Read it before touching pipeline code.
- `faces/<name>/` — `face.yaml` (provenance, metrics, version, specimen lines),
  `glyphs/manifest.csv` (one row per cut: glyph, unicode, leaf, line, band, category,
  box), `construct.yaml` (recipes for letters the specimen doesn't show),
  `CHANGELOG.md`, and the stage outputs: specimens → glyphs → svg → ufo → dist → proofs, plus `log/`.
- `books/<archive_id>/` — a whole specimen book: `book.yaml`, per-leaf surveys,
  `catalog.json` (every display band with the size and series its caption names),
  `readings.json` (what each band says, by whom), `reader.jsonl` (every band the model readers were sent:
  both answers, agreed or not, cost). Scans, OCR, surveys and sheets are fetched or rebuilt, not committed.
  `books/README.md` + `books/selection.csv` record how the shelf was chosen; `books/name-audit.csv` the names OCR misread.
- `showing/` — one sheet across every face (`foundry showing`); the website's index reads it.
- `website/` — Vite + React site for finding a strike, seeing its source and taking it further. The built site
  reads fonts and proofs from the Cloudflare R2 bucket `phantom-foundry` (`scripts/publish-assets.py` uploads
  what changed; needs `wrangler login`); `npm run dev` reads `public/` after `scripts/sync-faces.sh`.

## How

- Python 3.12 via uv: `uv sync`. potrace via `brew install potrace`.
- Tests: `.venv/bin/pytest` (geometry, sort placement, construct, justify).
- Run a stage: `.venv/bin/foundry <stage> <face> [--glyph G]`; `foundry --help` lists them.
  Rebuild a face: `foundry build <face>` (cut → proof, skipping unchanged stages); every face:
  `foundry build --all -j 6`, then `foundry showing`. `--force` reruns everything.
- A book: `foundry shelve <archive_id>` (620 MB for BB&S No. 9), `foundry catalog <id>` (~5 min),
  `foundry series <id>` lists series worth founding, `foundry found <face> --book <id> --series "…"`,
  readings via `foundry read-models <id>` (two small vision models on OpenRouter, key in `.env`; a band is recorded
  only where both agree and the count fits the boxes; italic and script series are skipped — see
  `agent_docs/reader-bakeoff.md`) or by hand: `foundry read <id> --leaf L --band B --text "…" --by claude|human` / `--from file.json`,
  then `foundry label <face> --auto --min-tall 115` and `foundry build`. Reading syntax: one token per
  numbered box in the band crop (`books/<id>/sheets/leafNNNN_bB.png`): a character, `[fi]` for touching
  letters, `?` unreadable, `~` not a letter. OCR is a cross-check only; it never labels a glyph by itself.
- New face: `fetch`, then `survey --leaf N` (finds lines and letter boxes, writes
  a numbered sheet), then `label --band B --text "WORDS" --line <size>` per line,
  largest size first — the first showing of a letter gets the plain name, later
  sizes become `.six`/`.eight` alternates (unencoded).
- A founded proto commits only its record — `face.yaml`, `CHANGELOG.md`, `glyphs/manifest.csv`,
  `specimens/*.json`, the decisions' logs (`log/found|label|rename….jsonl`; not the per-build stage logs), `svg/arrow/` — and `found` writes a `.gitignore` in the face for the rest
  (cuts, potrace SVGs, UFO, `dist/`, `proofs/`). With the book shelved, `foundry build <face>` relinks
  the scans and rebuilds all of it identically. Delete that `.gitignore` when a face goes to draft:
  from then on its UFO is hand-edited and everything is committed. A fresh clone gets fonts and
  proofs back with `foundry shelve <archive_id>` then `foundry build --all -j 6`.
- UFO is the master source; `dist/` is compiled — never hand-edit it. Glyphs
  not in the manifest (constructed ones) survive `sort`; `justify` re-spaces everything.
- Constructed letters live in `construct.yaml` and are flagged everywhere
  (glyph lib, `face.json`, gray in `proofs/alphabet.png`). Never let one pass as traced.
  Faces founded from a book get no constructed letters at proto; that is a draft step.
- Review at scale starts at `showing/index.html` (faces that warned first) and each
  face's `proofs/checks.json`, not at a hundred alphabet sheets. A `label` warning (from `audit.py`) means a
  cut looks unlike its siblings or more like another letter: a wrong label on a good outline is the worst error.
- Captions come in two styles `catalog` can parse: the name in every caption (BB&S, MacKellar, Cleveland) and the
  name once in the page heading over bare "36 Point" captions (ATF, Keystone, Inland). Body-name sizes ("Great
  Primer") and other languages it cannot; `agent_docs/caption-reading-test.md` shows a vision model can.
  Known limits of `survey`: a band is a full-width ink row, so two-column pages merge two showings into one band,
  and a printed page border or a dark scan surround turns the whole page into one band (MacKellar, Page, Tubbs,
  the 800 ppi 18th-century scans).
- Releases: bump `version` in `face.yaml`, add to `CHANGELOG.md`, commit, tag
  `<face>/vX.Y.Z`. `.github/workflows/release.yml` rebuilds and attaches fonts on push of the tag.
- Arrow: called through Quiver's MCP server (`mcp__quiver__create_vectorization`,
  model `arrow-1.1`), then `foundry cast --engine arrow --from <svg>` to log it;
  every Arrow cast must also have the potrace trace of the same input.
  Credits are scarce — never call Arrow on an input you haven't looked at first.
- Scans (`specimens/*.jp2`) are not committed; `fetch` reproduces them from `face.yaml`.
