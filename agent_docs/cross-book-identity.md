# The same face in more than one book (design note, nothing built)

A strike is one showing from one book. ATF's 1897, 1900, 1906, 1912 and 1923
books all show De Vinne; each is its own strike with its own letters, because
each was set in different words. That is correct and stays. This note is about
the *derived* object: knowing that strikes are the same design, and what a
merged alphabet would look like without losing where each letter came from.

## It is the same problem as the name audit

A name read wrongly from a heading ("Qoudy Italic") and a face shown in a
second book under the same name are both answered by one question: *which
strikes are showings of one design?* Build the matcher once; the name audit is
its within-book and spelling-level use, identity its across-book use.

## Three signals, in order of cost

1. **Name.** Normalise the series (case, punctuation, "No.", "Oldstyle/Old
   Style", "Bold Condensed/Condensed Bold"). A name seen in one book that is
   one or two edits from a name seen in several is a misreading, not a new face.
   Cheap and decides most cases inside one foundry's run of books.
2. **Lineage.** Names only mean the same thing within a lineage. American Type
   Founders was formed in 1892 from MacKellar Smiths & Jordan, Bruce, Boston,
   Cleveland, Cincinnati, Palmer & Rey and others, and later took in Inland; a
   MacKellar face reappears in ATF books, sometimes renamed or renumbered.
   Barnhart Brothers & Spindler stayed apart until 1929, and Keystone throughout,
   so "Gothic No. 3" at BB&S and at Keystone are different designs until shape
   says otherwise. Keep lineage as data: `books/lineage.yaml`, foundry → absorbed
   by, year.
3. **Shape.** Two strikes' same-letter glyphs, scaled to a common cap height and
   compared (overlap of the filled outlines after aligning centroids, as the
   label audit does within a face). Several shared letters agreeing at the level
   two sizes of one face agree is strong evidence; it also *separates* faces that
   share a generic name. Costs a pass over glyph pairs, but only for candidates
   the first two signals propose.

A match is a claim with evidence, never a rename: `{strikes: [...], evidence:
{name, lineage, shape: {letters, score}}, by}`. A person confirms the doubtful ones.

## What a merged alphabet looks like on disk

Not a face. A separate kind of thing, so a strike never quietly becomes a composite:

```
designs/<design-slug>/
  design.yaml      # the strikes it draws on, the evidence for each, who confirmed
  glyphs.csv       # glyph, unicode, strike, leaf, line, band, box: one row per letter, its source strike named
  ufo/ dist/ proofs/
```

Each letter comes from exactly one strike, chosen by a stated rule (largest
printed size; then sharpest scan; then earliest book), and carries that strike's
book, leaf and box in its glyph lib and in the font's `PHFD` table, as strike
glyphs do now. The proof sheet colours letters by source book. Sizes differ
between books as they do between sizes within one, so every letter is rescaled
to one cap height by the same `sort` logic, and spacing is re-derived
(`justify`), not inherited. Mixing foundries' cuts of "the same" face is a
decision recorded in `design.yaml`, not a default: a MacKellar cutting and its
ATF recasting are one design; two foundries' rival Caslons are not.

## Not now

Nothing here is needed to publish strikes. It becomes worth building when
someone wants a usable full alphabet more than a faithful single showing.
