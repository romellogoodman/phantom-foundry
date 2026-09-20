# Phantom Foundry

An open-source font foundry reviving public domain typefaces from scanned
specimen books, with bespoke Python tooling. Fonts mature in versions like
software: **proto** (traced from the page, machine-spaced) → **draft**
(reviewed by a person) → **release** (1.0: spaced, kerned, cleaned).

Revivals work from printed specimens — Internet Archive scans of type
specimen books — never from digital fonts. Typeface designs aren't
copyrightable in the US, but font software is. Every glyph keeps its
provenance: the book, leaf, printed page, specimen line and pixel box it was
cut from ship inside the compiled font and beside it.

## Status

103 faces, all v0.x protos. 100 were founded from one book — Barnhart
Brothers & Spindler's *Book of Type Specimens* No. 9 (Chicago, 1907) — by the
book-scale pipeline; the rest, like `wood-266-class-l`, were labeled by hand.
A proto has only the letters its specimen shows. Kerning, constructed
letters for founded faces, and sizes under 30 pt are deferred.

Start at [`showing/index.html`](showing/index.html): one sheet across every
face, the ones that warned first.

## Pipeline

Small CLIs named from foundry vocabulary. Every stage reads plain files and
writes plain files, so the whole process is inspectable, resumable and
git-diffable — the process is the research, and its traces, logs and proofs
are deliverables.

```
one face:  fetch → survey → label ─┐
a book:    shelve → catalog → found → read → label --auto ─┴→ cut → cast → sort → construct → justify → matrix → proof
                                                            (= build)                              → showing
```

Two ways in, one way out:

- **One face** — `fetch` the scans, `survey` a leaf for its lines and letter
  boxes, `label` each line by hand.
- **A whole book** — `shelve` it, `catalog` every leaf (reading each
  showing's caption for its size and series), `found` faces from the series,
  `read` what each band says (a person or Claude; OCR is only a cross-check),
  then `label --auto`.

Both produce `glyphs/manifest.csv`, and `build` takes it from there:

| stage | does |
|---|---|
| `cut` | crop and binarize each letter from the scan |
| `cast` | trace it to outlines with potrace |
| `sort` | shared baseline and scale per specimen line; write the UFO |
| `construct` | build letters the specimen lacks from traced parts — always flagged |
| `justify` | sidebearings from ink profiles and the printed gaps |
| `matrix` | compile OTF/TTF with the provenance table embedded |
| `proof` | scan/trace overlays, alphabet sheet, re-set specimen lines, `checks.json` |

potrace is the production tracer. [Quiver AI's Arrow model](https://quiver.ai)
turned out to *depict* letters rather than trace them, so it is a research
instrument: every Arrow cast is paired with the potrace trace of the same
input, and the gap between them is a subject, not a defect.

See [agent_docs/architecture.md](agent_docs/architecture.md) for the full
design.

## Layout

- `tools/foundry/` — the CLIs
- `faces/<name>/` — one revival's complete record: `face.yaml`,
  `glyphs/manifest.csv`, then `svg/` → `ufo/` (the master source) → `dist/`
  (compiled fonts, never hand-edited) → `proofs/`, plus `log/` and `CHANGELOG.md`
- `books/<archive_id>/` — a shelved book: surveys, `catalog.json`,
  `readings.json` (scans and OCR are fetched, not committed)
- `showing/` — the sheet across every face
- `website/` — Vite + React specimen site with a type tester

## Usage

Python 3.12 via [uv](https://docs.astral.sh/uv/), plus potrace:

```sh
uv sync
brew install potrace

.venv/bin/foundry --help            # list the stages
.venv/bin/foundry build <face>      # cut → proof, skipping unchanged stages
.venv/bin/foundry build --all -j 6  # every face
.venv/bin/foundry showing           # refresh the rollup
.venv/bin/pytest
```

The website: `cd website && scripts/sync-faces.sh && npm run dev`.

Releases are tagged `<face>/vX.Y.Z`; a workflow rebuilds the face and
attaches its fonts.

## License

Fonts are licensed under the [SIL Open Font License](https://openfontlicense.org);
the tooling is MIT.
