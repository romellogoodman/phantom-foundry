# The shelf

One directory per specimen book, named by its Internet Archive id. `book.yaml`,
`catalog.json` and `readings.json` are committed; page scans, OCR, survey
sheets and crops are fetched or rebuilt (`foundry shelve`, `foundry catalog`).

## How the books were chosen (2026-09-20)

`selection.csv` is the whole record: every candidate, what happened to it and why.

1. **Search.** archive.org `advancedsearch.php`, `mediatype:texts`, nine queries:
   subjects ("Printing -- Specimens", "Type and type-founding", "Type specimens",
   "Wood type"); titles with *specimen(s)* and *type / printing / typefounders /
   foundry / wood type*; known founders as creator (American Type Founders,
   Barnhart, Hamilton, Inland, Keystone, MacKellar, Bruce, Stephenson Blake,
   Caslon, Miller & Richard, Cincinnati, Marder Luse, Central, Dickinson, Boston,
   Farmer Little, Conner, Page) with *specimen / catalogue / price list* in the
   title; wood type makers; German (*Schriftproben, Schriftgiesserei, Hauptprobe*),
   French (*spécimen / épreuves … caractères / fonderie*), Dutch, Italian and
   Spanish equivalents; *type faces / book of types / printing types*; and the
   composing-machine makers. 4,351 items.
2. **Filter.** Dated before 1931 (public domain in the US in 2026), at least 30
   page images, a title that reads as a type specimen, and not natural history
   ("type specimens" of fossils and beetles), style manuals, handwriting, dyeing
   or the like. Read by eye and pruned again. **179 candidates.**
3. **Resolution check.** `archive.org/metadata/<id>` for `ppi` and the page-image
   archive. 14 Google scans exist only as bitonal TIFF and were skipped, with 11
   items the search had caught that are not type specimens. **153 pulled**, 32 GB.
4. **Coded for founding.** Foundry and wood type books only: a printer's type book
   shows faces it bought from a foundry, a scholarly book reproduces other
   specimens, and machine-composition books show text sizes. Second scans of an
   edition already held at higher resolution are shelved, not founded.
   **78 coded**, each with a short code (`atf1912`, `msj1892`) that ends the name
   of every face founded from it, so the same typeface in two books is two faces.

Barnhart Brothers & Spindler's Specimen Book No. 9 (1907) was the first book, founded on 2026-09-04.
