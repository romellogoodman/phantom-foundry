# O.s. Grotesq.ue. — changelog

Revival of Edinburgh, London **O.s. Grotesq.ue.** from *Printing type specimens, comprising a large variety of book and jobbing faces, borders and ornaments* ([1921?]), leaf 130 (p. 198) — archive.org `printingtypespec00millrich`, 300 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/printingtypespec00millrich/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **O.S. Grotesque**: the archive's OCR read the heading as “O.s. Grotesq.ue.”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
