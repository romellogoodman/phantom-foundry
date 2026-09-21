# Can a cheap vision model catalogue specimen-book captions the regex parser can't read?

Model: `deepseek/deepseek-v4.1-flash` via OpenRouter, `reasoning: {"enabled": false}`, temperature 0.
Input per page: the survey sheet PNG (downscaled to 1800px long edge) + small-caption OCR lines
(position as % of page) + band list (y-range %, letter count, `tall_px`). Output: one JSON object
per band — `{"band", "is_type", "series", "size", "unit", "size_name"}`. Script and cache live in
this directory (`orclient.py`, `context.py`, `prompt.py`, `run.py`, `score.py`); nothing in the repo
was modified and no `foundry` stage was run.

**Total spend: $0.233 of the $3.00 ceiling** (tracked from OpenRouter's own `usage.cost`, persisted
across every run in `budget_state.json`). 384 uncached model calls total across prompt iteration,
the BB&S sample, and five hard-book panels.

## Verdict

Yes, for series names — 95.3% exact / 96.5% fuzzy match against the ~1,400 bands the existing regex
parser already gets right, and it fills in most of what the parser leaves blank. Sizes are noisier
(92.8%), mostly from one specific, structural cause (below), not model misreading. On the five books
the regex genuinely cannot read at all (pre-1886 body-name and non-English captions), by-eye review
across 60 leaves found the model transcribing "Great Primer Gothic Condensed No. 3", "Corps 24
(Doppelcicero)", and "Trente-Six Deberny Romain" correctly essentially every time it had a real
caption to read, and correctly saying "not type" on price lists, border-ornament plates, and a
handwritten cataloguer's note. It should replace the regex captions for these five books, gated by
the guardrails below — the one real, recurring failure mode is structural (see "Bands that mix two
showings"), not a language or vision problem, and no guardrail fixes it without upstream changes.

## The two-column / merged-band problem (its own section, as requested)

The band finder (`survey_page` in `tools/foundry/cut.py`) detects display lines by full-page-width
ink projection: any row with ink anywhere across the page becomes one "band," and letters inside it
are boxed left-to-right regardless of column. On a single-column book (BB&S, most of the time) this
is fine. On the double-column books that make up most of the hard panel, it is not: a row that is
visually two independent showings side by side — different series, different sizes, different
captions — is detected and numbered as **one band**. The model is asked for one answer per band, so
on a genuinely mixed band there is no correct single answer; at best it can pick the dominant column
(most of the band's boxes) as instructed, and it does so inconsistently when the two columns are
close in size.

Confirmed by eye on:
- `bookoftypespecim00barnrich` leaf 138, band 3: "TENNYSON 8" (left column, 20pt) merged with
  "3 MIRRORS" (right column, 24pt) into one band; truth (parser, arbitrarily) says 20pt, model said
  30pt — neither reading is really "the" band's size, because the band isn't one showing.
- `bookoftypespecim00barnrich` leaf 223, band 3: same pattern, truth 24pt vs. model 18pt.
- `fifteenthbookofs00cincrich` leaf 62, band 1: "PUBLISHING COMPANIES" (left, Great Primer Gothic
  Condensed No. 3) merged with "STEEPLE BUILDER" (right, Pica Concave) — model correctly picked the
  dominant left column (more boxes).
- `fifteenthbookofs00cincrich` leaf 61: a dense two-column grid where the model picks the *left*
  column's caption for band 2 ("Two-Line Pica") but the *right* column's for band 3 ("Pica"/"Gothic
  Condensed No. 5") — same page, same rule applied, opposite column chosen, because the box-count
  balance between columns flips row to row.

This is the single largest source of size mismatches in the BB&S table below (essentially all 4
size misses in the 13-leaf prompt-iteration sample traced to it), and it will affect any book with
side-by-side showings regardless of model quality. **A real fix is upstream**: split a band at the
x-gap between columns before cataloguing, or have the box-finder flag a band as `multi_column` when
its letters cluster into two x-ranges with a gap. Short of that, a downstream guardrail (below) can
only detect the ambiguity, not resolve it.

A related but distinct issue, seen once (Cincinnati leaf 61, band 1): the row finder can also merge
two *vertically* stacked captions of different point sizes into one band when the line-gap between
them is small (adjacent short captions like 6pt/8pt rows collapsing together with a 24pt row). Same
root cause (full-width row-ink projection with no caption-aware segmentation), same non-fix at the
prompt level.

## BB&S sample (`bookoftypespecim00barnrich`)

The book has only **289** leaves with at least one parser-assigned band (not ~300) — I ran all of
them rather than sampling, so this is the full population, not a sample.

| metric | value |
|---|---|
| leaves | 289 |
| known bands (parser assigned a series) | 1,384 |
| unknown bands (parser left null) | 562 |
| **series exact match** (normalized case/punctuation/"No." spacing) | **95.3%** |
| **series fuzzy match** (edit distance ≤2) | **96.5%** |
| **size match** (unit + value both equal) | **92.8%** |
| no prediction on a known band | 2.2% |
| model answered *something* on an unknown band | 82.9% (466/562) |
| cost, this run | $0.147 (289 calls, $0.00051/leaf median) |
| wall time, this run | 179.3s at concurrency 10 (289/289, 0 errors) |

The "invented on unknown" rate (82.9%) is by design, not a flaw — the task specifies these bands as
*unknown, not negative*: the parser left them blank because its regexes didn't match, not because
there's no real caption there. By eye (20 sampled, listed selection below; full list reproducible
via `pick_invented.py bbs_full_out.json 20 11`), the overwhelming majority are genuine parser misses
that the model filled in correctly:

- leaf 226 band 2, leaf 433 band 9: both bands sit under a caption the parser should have linked but
  didn't (multi-line "Lining French Clarendon"/"Plymouth Italic" showings that exceed the parser's
  `max_per_caption` or gap-distance limits); the model's answer matches the caption exactly.
- leaf 348 band 1, leaf 785 bands 1-2: two real model errors, both instructive. Leaf 785 is a price
  table ("ACCENT FONTS FOR JOB TYPE") and an ornament-corner catalog page — not a specimen showing at
  all — but the model treated the page's own section heading as if it were a face name being shown
  ("Accent Fonts for Job Type" / "Job Type Accents" as `series`). Leaf 348 band 1 is a stray
  artifact band (`tall_px=2038`, `n=2` — essentially the whole page height, almost certainly a
  margin/border detection glitch, not a real display line); the model still guessed the page's
  obvious dominant series ("Engravers Roman Condensed") rather than declining. Both are the same
  underlying failure: when a band isn't really a showing, the model would rather guess the page's
  contextually-obvious series than say "no caption governs this," even though the prompt tells it to
  use null when it can't find one.

## Hard-book panel (12 leaves each, by eye)

Two of the six requested books were still mid-catalogue when I first checked and became ready
during an overnight re-catalogue run; I re-checked and both now have `catalog.json` + `sheets/` and
are included below. `ldpd_18607454_000` (Wm. H. Page wood type, 1859) still has neither — skipped.

| book | leaves | bands | is_type=true | series filled | cost |
|---|---|---|---|---|---|
| Cincinnati 1882 (`fifteenthbookofs00cincrich`) | 12 | 55 | 40 | 32 | $0.0105 |
| Palmer & Rey 1884 (`newspecimenbook00palmrich`) | 12 | 54 | 49 | 45 | $0.0063 |
| Bauer 1900, German (`hauptprobeingedr00baue`) | 12 | 44 | 29 | 23 | $0.0161 |
| Bruce 1882 (`specimensofprint00geor`) | 12 | 69 | 63 | 52 | $0.0080 |
| Deberny 1886, French (`lelivrettypograp00fond`) | 12 | 78 | 58 | 57 | $0.0050 |

None of these books have any parser-assigned bands to score against (0/464, 0/687, 0/985, 0/3167,
0/2920 respectively, confirmed against `catalog.json` before running) — every one of these numbers
is currently zero from the regex parser. Judgement below is entirely by eye, sheet against output.

### Cincinnati 1882 — `fifteenthbookofs00cincrich`
Correctly rejected a handwritten cataloguer's flyleaf note ("1882 Collated... Chas J. Furber...
Covington, Ky", leaf 5, all 4 bands `is_type=false`) and a printing-supplies price list (leaf 11, all
7 bands `is_type=false` — "CUTS", "GALLEYS", "HAND PRESSES" etc.). Got body-name captions right where
bands weren't column-merged, e.g. leaf 76: "Antique Extended No. 4" across Nonpareil / Brevier / Pica
/ Two-Line Brevier / Double Small Pica / Double English / Double Paragon, all 7 bands consistent with
one running caption sequence. Main mistake type: the two-column merge problem above (leaf 61, leaf
138-equivalent pattern). Example outputs with caption as printed:
- leaf 76, band 3: page heading "ANTIQUE EXTENDED No. 4", caption "PICA" → predicted
  `series="Antique Extended No. 4"`, `size_name="Pica"`, `unit="body-name"` — correct.
- leaf 47, band 1: caption "AGATE TITLE NO. 1" → `series="Agate Title No. 1"`, `size_name="Agate Title No. 1"` (duplicated into both fields — harmless but redundant; a guardrail should dedupe when series and size_name are identical).
- leaf 5 (handwritten note): all bands `is_type=false` — correct, no type at all on the page.
- leaf 11 (price list): all bands `is_type=false` — correct.
- leaf 61, band 3: merged-band ambiguity (see above) — right column's "Gothic Condensed No. 5" /
  "Pica" chosen over left column's "Gothic Extra Condensed No. 2" / "Two-Line Pica"; defensible but
  not verifiably "the" answer since the band mixes both.

### Palmer & Rey 1884 — `newspecimenbook00palmrich`
Correctly recovered page-heading-governed sequences on a two-column page (leaf 124): predicted
series alternate `Linear`/`Normanesque` down the left/right columns and later `Record`/`Circlet` —
both pairs of names are printed as bold column headers on the page and the model matched them
exactly, correctly using column position rather than pure y-proximity. Leaf 9 (front matter/title
verso) correctly got all 3 bands `is_type=false`. Example outputs:
- leaf 67, bands 1-9: one caption family "Clarendon Compressed" repeated across Double Great
  Primer / Double Paragon / Four-Line Pica sizes (3 bands each) — caption printed as "CLARENDON
  COMPRESSED. DOUBLE GREAT-PRIMER. 6A. $3.25" etc.; matched throughout.
- leaf 124, band 5-8: "Record"/"Circlet" alternation, matching the printed column headers "RECORD."
  and "CIRCLET." exactly.
- leaf 91: 2 bands `is_type=false`, 3 `is_type=true` with series null — plausible mixed content
  (partially ornament, partially unreadable caption), not independently verified pixel-by-pixel.

### Bauer 1900 (German) — `hauptprobeingedr00baue`
Strongest result of the five. Leaf 52, fully verified pixel-by-pixel against the sheet: 5 of 6 bands
exactly correct against printed captions —
- "Nr. 2215. Corps 14 (Mittel)" → `series="Kleukens-Antiqua"` (from the page's running head), `size=14, unit=pt, size_name="Mittel"` — correct.
- "Nr. 2217a. Corps 24 (Doppelcicero)" → `size=24, size_name="Doppelcicero"` — correct.
- "Nr. 2218. Corps 28 (Doppelmittel)" → `size=28, size_name="Doppelmittel"` — correct.
- "Nr. 2219. Corps 36 (3 Cicero)" → `size=36, size_name="3 Cicero"` — correct.
- "Nr. 2220. Corps 48 (4 Cicero)" → `size=48, size_name="4 Cicero"` — correct.
- One band (a decorative bordered mock-advertisement, "MAX FUHRMANN * DRESDEN-A. ... FABRIK
  KÜNSTLICHER BLUMEN") was called `is_type=false` — defensible (it's dominated by an ornamental
  border and a tree-of-flowers illustration) but arguable, since the headline words are set in the
  face being shown.
Leaf 15 (a prose page explaining the German point system, tables of body-name/point equivalences,
no captions at all) got `is_type=true, series=null` on all 6 bands — correctly found no caption
governs any of it, though the underlying issue is that this is a body-text reference page the
survey tool mis-detected as containing "bands" at all (paragraph blocks with small line-gaps
collapsed into tall merged "bands" — a leaf-selection artifact of my `tall_px>=115` heuristic
picking up justified body text, not a model failure).

### Bruce 1882 — `specimensofprint00geor`
Leaf 278, fully re-verified against exact band y-positions from `catalog.json` (not just visual
guessing): **all 7 bands correct** — "TWO-LINE NONPAREIL ORNAMENTED, No. 1,030" → matched; "TWO-LINE
PICA ORNAMENTED, No. 1,031" → matched; "TWO-LINE ENGLISH ORNAMENTED, No. 1,031" (2 bands, one per
printed line) → both matched; "TWO-LINE GREAT-PRIMER ORNAMENTED, No. 1,031" (2 bands) → both
matched; final band is the type foundry's footer imprint line, correctly left `series=null`. This
book's captions are dense (numbered "Ornamented No. N" families across many body-name sizes) and the
model tracked the running numbered-series convention correctly across repeats.

### Deberny 1886 (French) — `lelivrettypograp00fond`
Leaf 148: perfect match — "TRENTE-SIX DEBERNY ROMAIN (N° 18)" (5 bands) → `series="Deberny Romain",
size=36, unit=pt, size_name="Trente-Six"`; "TRENTE-SIX DEBERNY ITALIQUE (N° 18)" (3 bands) →
`series="Deberny Italique"`, same size — matched on all 8 bands. Note the model's own inference:
"Trente-Six" literally is French for "thirty-six," so it filled both `size=36 unit=pt` (usable
downstream like any other point size) *and* `size_name="Trente-Six"` (the words as printed) —
exactly the dual representation a French-language founder's catalogue needs, without being told to
do this specifically. Leaf 528 ("BORDURES Corps 12", an ornament-border plate, 10 bands) → all 10
`is_type=false` — correct, no letterforms on the page at all.

## Cost and time projection to 32,000 pages

Measured, not estimated: the BB&S production run (289 leaves, concurrency 10, `reasoning: off`) cost
**$0.1468** and took **179.3s wall time**, 0 errors. Across all 384 uncached calls made in this task
(iteration + BB&S + 5 hard-book panels — a broad mix of page complexity), mean cost/call was
**$0.00061**, median **$0.00053**, mean latency **6.2s**, p90 **8.2s**.

- **Cost for 32,000 pages**: 32,000 × $0.00051 (BB&S-run actual) ≈ **$16** (range $17-20 using the
  broader mean/median across all page types tested, which included denser hard-book pages).
- **Time for 32,000 pages**: at the same concurrency 10 sustained in the BB&S run (1.61 leaves/sec),
  32,000 pages ≈ **5.5 hours** wall time. Concurrency was not stress-tested above 10 in this task
  (budget/scope), but scales roughly linearly with available worker threads until OpenRouter rate
  limits bite; at concurrency 30 that's plausibly ~1.8 hours, subject to verification before
  committing to a real run.

## Guardrails recommended before wiring this into `catalog`

1. **Require the series string to appear in the page's own OCR text** (fuzzy, edit-distance
   tolerant, case-insensitive) before accepting it — catches the leaf 785/leaf 348 failure mode
   (inventing a series from a page heading or a stray band with no real caption) at near-zero cost,
   since both bogus answers *did* echo text from elsewhere on the page but a stricter check tied to
   the OCR line nearest that specific band would reject them.
2. **Require size consistency with `tall_px`**: reject (or flag) a `unit: "pt"` answer whose implied
   cap height ratio to the nearest captioned/known size on the same page is off by more than ~20%
   (mirrors the existing `infer_sizes` snap-to-standard-sizes logic in `book.py`, which already does
   this for the regex path).
3. **Flag column-mixed bands before or after the model call**: compute the x-distribution of a
   band's boxes; if they cluster into two well-separated x-ranges (a gap wider than ~2 average
   letter widths), mark the band `ambiguous_column=true` in the output rather than trusting a single
   series/size answer — this is the fix for the single largest recurring error class found here, and
   it doesn't require the model to get anything right, just for downstream code not to trust an
   inherently double-valued band.
4. **Dedupe `series`/`size_name` when identical** (seen on Cincinnati leaf 47: both fields got
   "Agate Title No. 1") — cosmetic, cheap to fix downstream.
5. Keep `reasoning: {"enabled": false}` — confirmed throughout this task: with it on, prior testing
   (this task's provided reference client) showed ~7,500 hidden tokens and $0.0087 per call vs. the
   $0.0005 median observed here; effort tuning alone did not fix it, only `enabled: false` did.

## Final prompt (v5, locked)

The complete, versioned prompt template lives in `prompt.py` (`PROMPT_VERSION = "v5"`) in this
directory — reproduced here as the shipped artifact:

```
You are cataloguing one page ("leaf") from a scanned 19th/early-20th-century type specimen book. A tool has already found every line of large DISPLAY type on the page ("bands") and drawn a numbered box around each letter-shape in each band; the image shows the whole page with those bands outlined in blue and numbered in the page's reading order (top to bottom), and every letter boxed in pink with a small number under it (ignore the letter numbers — you only need to identify the BAND numbers, printed to the left of each blue box, and the text inside).

Your job: for every band number listed below, say what typeface SERIES and SIZE its small printed CAPTION says it is a showing of — the caption is small print (not boxed), usually 1-3 lines placed just above the band, giving the size, the series name, and often a font scheme (e.g. "7 A 14 a") and a weight/price. Specimen books use several caption styles; you may see any of these on this page:

1. Point size + name in every caption: "42 Point Cadillac Condensed" -> size 42, unit "pt", series "Cadillac Condensed".
2. A heading naming the series once at the top of the page or column (e.g. "NIAGARA SERIES", "Florentine Heavyface", or a two-column page where each column has its own heading), with each caption below giving only the bare size: "36 Point", "24 Point No. 70" -> unit "pt", series comes from the heading that governs that band, not from the caption itself.
3. Traditional body-name sizing (common before ~1886, and in wood type): a size name instead of, or in addition to, a point number: "Great Primer Gothic", "Double Pica Antique", "Two-Line Pica Ornamented No. 7", "No. 266 -- Class L, Fifteen Line". Here put the size name as printed (e.g. "Great Primer", "Double Pica", "Two-Line Pica", "Fifteen Line") in size_name, and the remaining words as series (e.g. "Gothic", "Antique", "Ornamented No. 7", "No. 266 Class L"). If a number of "lines" is given (wood type: "Three Line", "Ten Line Antique Extended"), also set unit "line" and size to that line count as a number (three -> 3, ten -> 10); otherwise set unit "body-name" and leave size NULL -- do NOT convert a body name to a modern point-size guess (a historical body's point size varied by foundry and era; a guess will be wrong more often than a blank). size is only ever a point number (unit "pt") or a line count (unit "line"), never a number you inferred from a body name.
4. Non-English books name sizes by their own tradition: German by body name (Nonpareille, Petit, Korpus/Corpus, Cicero, Mittel, Tertia, Text, Doppelmittel, often with "Kegel" or a point number after ~1900) or by Didot point ("Kegel 36"); French by "Corps N" (N = the point size in the old Didot/Fournier system -- treat like unit "pt", size N); Dutch/Flemish by body name (Mediaan, Descendiaan, Text, Kanon, Kolonel, "Dubbelde" = "double" as a prefix). Put the size word(s) as printed in size_name (and size + unit "pt" too if a numeric point size is also given), and the face name in series, translating nothing -- keep series and size_name in the book's own language and spelling.

Rules:
- Borders, ornaments, rules, dashes, brass rule, cuts, initials, monograms, logotypes, fractions, braces, corner pieces, or printing-machinery illustrations are NOT type, even if a band's boxes landed on them. Mark those bands is_type=false and leave series/size/size_name null.
- A caption usually governs the 1-3 bands immediately below it, up to the next caption or heading. On a two-column page, match each band to the caption in ITS OWN column (use the x-position of the band's boxes and the caption's x-position in the image and in the small_lines list below) -- do not let a left-column band take a right-column caption just because it happens to be a little higher on the page, or vice versa.
- Some bands are numbered as ONE band by the box-finding tool even though they visually span two side-by-side showings in different columns (the tool boxes a full page-width strip of ink as one band). If that happens here, answer with the series/size of whichever showing occupies MOST of that band's boxes, and do not try to split one band number into two answers.
- Occasionally a band is the running head, a page number, or other page furniture that slipped into the display-line finder; if a band's text is clearly not a specimen showing (e.g. it repeats the book's own running title), still decide is_type based on whether it is actually printed type (yes) vs. a photographed illustration (no) -- furniture set in type is still is_type=true, just give its best-guess series/size or null if you cannot tell.
- If you cannot find any caption that plausibly governs a band, set series, size, unit, and size_name to null but still set is_type (true if it looks like real type, false if it's clearly ornament/rule/junk).
- series: transcribe as printed, correcting obvious single-character OCR noise you can see directly in the image, in title case (capitalize each main word, keep "No." as "No."). size_name: as printed (e.g. "Great Primer", "Two-Line Pica", "Tertia"), title case.
- Specimen books abbreviate constantly in small caption print. Expand an abbreviation to its full word whenever you're confident what it stands for, in both series and size_name: "Cond./Condens." -> "Condensed", "Ext." -> "Extended", "Exp." -> "Expanded", "Ital./It." -> "Italic", "Ex." -> "Extra", "Med." -> "Medium", "Lt." -> "Light", "Hvy." -> "Heavy", "Bd." -> "Bold", "Compr./Comp." -> "Compressed", "Gt. Prim./Gt. Primer" -> "Great Primer", "Para." -> "Paragon", "2-Line/2-L./2 L." -> "Two-Line", "3-Line/3-L." -> "Three-Line", "4-Line/4-L." -> "Four-Line", "5-Line/5-L." -> "Five-Line", "Dbl./Dble." -> "Double". If an abbreviation is unfamiliar or ambiguous, keep it as printed rather than guess.

Page context (machine-measured, not always reliable -- the image is the ground truth):
- Page height: {H} px. All y/x positions below are given as a PERCENT of page height/width, top-left origin, matching how they'd appear in the image.
- small_lines: every small (non-display) line of OCR text on the page -- captions, headings, prices, weights, running heads, folios -- with its position. OCR is noisy (it garbles display type worse than small type, and drops punctuation), so read the caption for yourself in the image wherever small_lines looks wrong; use it mainly to know WHERE on the page the captions are and roughly what they say.
{small_lines JSON: text, y0_pct, y1_pct, x0_pct, x1_pct per caption-sized OCR line}
- bands: every band the box-finder found, with its vertical extent and letter count.
{bands JSON: band, y0_pct, y1_pct, n, tall_px per band}

Respond with a JSON object of exactly this shape and nothing else (no markdown fences, no commentary): {"bands": [{"band": <int>, "is_type": <bool>, "series": <string or null>, "size": <number or null>, "unit": "pt" | "line" | "body-name" | null, "size_name": <string or null>}, ...]} -- one entry for EVERY band number listed above, in the same order.
```

(Verbatim from `prompt.py`; `{H}`, the `small_lines` list, and the `bands` list are filled in per-leaf by `build_prompt()`.)

Iteration history: v3 (initial, from the 4 caption styles + is_type/mixed-band rules) scored
100%/100%/93.7% (series exact/fuzzy/size) on the 13-leaf BB&S pilot; v4 added abbreviation expansion
("Cond." → "Condensed" etc.) to match the parser's own naming convention, which introduced a
regression where the model started guessing modern point-size equivalents for body-name-only
captions (e.g. inventing `size=18` for "Great Primer"); v5 explicitly forbids that guess and locks
`size: null` for `unit: "body-name"`, recovering to 100%/100%/96.8% on the same pilot and confirmed
clean on the hard-book spot checks (Bauer leaf 52, Deberny leaf 148 above).
