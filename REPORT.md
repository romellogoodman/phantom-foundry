# Report: the shelf run, 20–21 September 2026

## What surprised me

1. **The label audit found errors in readings we had accepted, and found fake
   faces.** Built to catch the odd wrong letter, it flagged 71 of 12,262 cuts in
   the 103 BB&S faces; the ones I checked by eye are real. A reading that merges
   the wrong boxes slides every label after it (German Title Condensed, leaf 620
   band 8: an h filed as r; Adstyle Italic, leaf 537 band 3: an e filed as t). On
   the new books it fired 4,982 times, almost all in 116 faces, because those are
   not faces: ATF's running head "Copper Alloy Type" was taken for a series, so
   one "face" holds letters of dozens of designs. They are built, marked
   `suspect` in the showing, and kept off the site.
2. **One fault silences about 5,000 pages.** `survey` calls any row with ink
   part of a line. A printed page border (every MacKellar book, Page 1859) or a
   dark scan surround (Tubbs, the 800 ppi 18th-century scans, microfilm, New
   England 1875) puts ink in every row, so the whole page is one "line". It is
   not a resolution problem.
3. **Cheap models are good readers only in pairs, and only with DeepSeek's
   reasoning off.** By default it spent 7,543 hidden tokens and 52 s on one line;
   `effort: low` returns nothing at all. Off: 3 s and $0.0002, same accuracy.
4. **Word frequency is not evidence for a name.** It wanted Cushing → "Gushing",
   because the same misreading repeats across ATF editions. Reading the name from
   the page image settled it for $0.37.
5. **My own label step failed silently** (macOS `xargs -I` drops commands over
   255 bytes), and the model readings had no word spaces, which `justify` needs
   to measure printed gaps. Both caught before anything was published.

## What changed (commits on main, oldest first)

- `336620c` `b6228fc` Protos commit their record, not their outputs; `build` relinks scans. History rewritten, 322 → 125 MB.
- `d2bc1a8` `catalog` reads heading-style pages (ATF, Keystone, Inland): the 1917 supplement went 0 → 33 series.
- `232c071` `1c2659c` Website: strikes framing, a finding tool over every book, a "How it's made" page with the shelf; fonts and proofs served from the R2 bucket `phantom-foundry`.
- `1a3bcaa` `3d396f1` `271f8d0` Records: how the books were chosen (`books/selection.csv`), the reader bake-off, the caption-reading test, the cross-book identity note.
- `c201521` `found` no longer credits Claude before anything is read.
- `e75ec38` `217c674` `audit.py`, run by `proof`; `build` skips an unread face instead of failing.
- `72fbee5` `f7279cd` `foundry read-models`: models, reasoning-off, the agreement rule, the italic exclusion and word breaks in code; every line logged to `books/<id>/reader.jsonl`.
- `c617428` CLAUDE.md, architecture.md; `e983094` the run's records, README, rename map; then the rename plan.

Tests: 23 → 37, all passing.

## What I measured

| | |
|---|---|
| Books | 179 candidates, 153 pulled (65 GB on disk), 82 catalogued, **21 give strikes** |
| Faces founded | 1,409 new (+103) from 20 books; ATF's seven books gave about 930 |
| Read | 7,899 lines sent, 5,740 agreed (73%), $1.19. Per book 22% (ATF 1923) to 89% (H. W. Caslon 1915) |
| Built | 1,179; 331 unread (162 italic/script, the rest all-disagreed); 2 fail on a glyph named "œ" |
| Listed on the site | **1,022** with ten or more letters, 27,591 letters; 41 thin; 116 suspect held back |
| Names | OCR confirmed by the page image for 1,083; **149 corrected**; 193 doubtful |
| Spend | **$3.14** of the $20 key, everything included |

Reader accuracy on the 878-line BB&S test, with the box-count gate, italics out:
both-agree accepts 88.6% of lines at 99.3% of letters; any-two-of-three accepts
92.9% at 99.2%; all-three 82.5% at 99.6%. Italics: 56% right even when agreed.

The disagreement queue (2,159 lines): in 502 neither reading fits the box count;
in 1,657 the letters differ. Lowercase is dropped more than capitals (82% of
mixed-case test lines pass against 94% of all-caps). 232 new strikes are
capitals only; for 52 the models saw lowercase in a line they then disagreed on.

Caption reading (not used): DeepSeek matched the parser's series on 95.3% of 289
BB&S pages and read Cincinnati, Palmer & Rey, Bruce, Bauer and Deberny correctly
by eye; about $16–20 for all 32,000 pages. It cannot repair a band that holds two
showings side by side, which full-width rows produce on two-column pages.

## Decisions waiting on you

1. **Fix `survey` first** (ignore page borders and dark surrounds; split a row at
   a wide column gap). *Recommend yes, before any more reading.* It unlocks
   MacKellar, Page, Tubbs and the 18th-century books and removes the two-column
   error at its source. It changes band numbers, so re-verify BB&S against its
   current catalogue, as the heading fix was.
2. **Disagreed lines.** *Recommend any-two-of-three* (add Gemini Flash-Lite,
   about $5 per 13,000 lines): +4 points of coverage for 0.1 point of accuracy.
   Then a stronger reader on what remains, lowercase lines first.
3. **The 116 suspect faces.** *Recommend deleting the ones whose "series" is a
   running head* (Copper Alloy Type, Loa, Special Characters, About…) and adding
   those phrases to the heading filter. Note the audit also distrusts ornamented,
   inline and shaded faces, where overlap is a poor likeness: those need a look,
   not deletion.
4. **71 audit flags in BB&S.** *Recommend a re-read of those lines*; the faces
   are public.
5. **193 doubtful names** in `books/name-audit.csv`, including faces split in two
   by a misreading. Yours to go through.
6. **Trademarked names and OFL reserved font names** (Franklin Gothic,
   Cheltenham…). The site says what a page shows; the font files carry the name
   too. Yours.
7. **`website/public/fonts|proofs` out of the repo** (134 MB). *Recommend yes*
   once you have seen the live site reading from the bucket. Not done tonight.
8. **GitHub description:** "Strikes of public domain type: faithful impressions
   traced from scanned specimen books, ready to be justified." Not changed.
9. **proto → strike in data:** `agent_docs/strike-rename-plan.md` recommends
   `kind` + `review` instead of a one-word swap.
10. **Disk:** 65 GB of scans plus about 140 GB of survey sheets and crops.
    *Recommend deleting the sheets and crops of the 61 books that gave nothing*
    (regenerable); keep the 21.
11. `various1930` is Waterlow & Sons, a London printer's book, not a foundry's:
    58 strikes that duplicate foundry faces. Keep or drop.

## Open threads

Non-ASCII glyph names (œ); provenance surviving a re-export from Glyphs or
FontForge; OFL reserved font names; per-face download packaging; trademarked
names on public domain designs; releases for the 106 tags that have none and for
the new strikes; a custom domain for the bucket (needs DNS on Cloudflare).
