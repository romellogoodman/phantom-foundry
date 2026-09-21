# De Vinne Italic Outline — changelog

Revival of [Philadelphia] : American Type Founders Company **De Vinne Italic Outline** from *Desk book of type specimens, borders, ornaments, brass rules and cuts : catalogue of printing machinery and printers' supplies* (1900), leaf 518 (p. 244), leaf 519 (p. 244) — archive.org `deskbookoftypesp00amer`, 400 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/deskbookoftypesp00amer/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **De Vinnè Italic Outline**: the archive's OCR read the heading as “De Vinne Italic Outline”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
