# Phantom Foundry

Phantom Foundry publishes strikes: faithful impressions of public domain type,
ready to be justified.

In a type foundry a strike was the raw impression of a punch in copper, before
anyone justified it into a working matrix. Foundries sold strikes to one
another to be finished elsewhere. That is what this project makes: one typeface
as one specimen book shows it, traced from the scanned page, spaced by machine,
with only the letters that page prints, and with the book, leaf, line and pixel
box of every letter carried inside the font and beside it. The same typeface in
four catalogues is four strikes. The foundry's job ends at the handoff; someone
else takes a strike further.

**What models do here, and don't.** Coding agents built the pipeline. Models
read which letter is in a box and read captions. No model draws a letterform:
every outline is traced from a printed page by potrace. Who read each line is
recorded with the reading, and the tests behind the choice of readers are in
[agent_docs/reader-bakeoff.md](agent_docs/reader-bakeoff.md).

Strikes are made from print (Internet Archive scans of type specimen books),
never from digital fonts. Typeface designs aren't copyrightable in the US, but
font software is. Everything is public so the work can be checked: the tools
(MIT), the record behind each letter, and the fonts (SIL Open Font License).

## Status

<!-- status:start -->
1,063 strikes from 21 specimen books (1889–1930: American Type Founders, Barnhart Brothers &
Spindler, Keystone, Inland, Boston, A. D. Farmer, Cleveland, Stephenson Blake, Miller & Richard, H. W.
Caslon), 27,591 letters in all, every one traced from the page. All are v0.x and unreviewed.
A strike has only the letters its page shows: the median is 26 letters, and many are capitals only.

- 154 books are shelved (chosen as recorded in [`books/`](books/README.md)); 82 are catalogued; 21 have
  given strikes. The rest wait on captions the tools can't parse yet (body-name sizes, German, French) or on
  two known limits of the page survey (two-column pages; pages with a printed border or a dark scan surround).
- The first 103 faces (BB&S No. 9, 1907) were read by Claude. The rest were read by two small vision
  models that must agree (`foundry read-models`): 7,899 lines sent, 5,740 agreed. 331 founded faces have no
  agreed reading yet, italics and scripts among them, and are not built.
- `proof` audits labels by shape. 116 built faces fail it badly enough to be held back as suspect: mostly
  a running head taken for a typeface name, so the "face" mixes designs.
- 149 names the OCR misread were read again from the page image and corrected; 193 more are doubtful
  and listed in [`books/name-audit.csv`](books/name-audit.csv). The OCR's reading stays in each `face.yaml`.
- Kerning, constructed letters, sizes under 30 pt and GitHub releases for the new strikes are deferred.
<!-- status:end -->

Start at [`showing/index.html`](showing/index.html): one sheet across every
strike, the ones that warned first. The site is
[phantom-foundry.romellogoodman.com](https://phantom-foundry.romellogoodman.com).

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
  `read` what each band says (a person, Claude, or two small vision models
  that must agree; OCR is only a cross-check), then `label --auto`.

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
- `faces/<name>/` — one strike's record: `face.yaml`, `glyphs/manifest.csv`,
  `specimens/*.json`, `log/` and `CHANGELOG.md` are committed; the cuts, `svg/`,
  `ufo/`, `dist/` and `proofs/` are rebuilt from them by `foundry build`
  (and kept in git once a person starts editing a face)
- `books/<archive_id>/` — a shelved book: `book.yaml`, `catalog.json`,
  `readings.json` (scans, OCR and surveys are fetched or rebuilt);
  [`books/README.md`](books/README.md) and `books/selection.csv` record how the
  books were chosen
- `showing/` — the sheet across every strike
- `website/` — Vite + React site: find a strike, see its source, take it further.
  Fonts and proofs are served from a Cloudflare R2 bucket (`website/scripts/publish-assets.py`)

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
