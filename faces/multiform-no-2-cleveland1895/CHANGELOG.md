# Multiform No — changelog

Revival of Cleveland **Multiform No** from *Catalogue and book of specimens of type faces and printing material and machinery* ([1895]), leaf 164 (p. 160), leaf 165 (p. 161) — archive.org `cataloguebookofs00clevrich`, 500 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/cataloguebookofs00clevrich/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Multiform No. 2**: the archive's OCR read the heading as “Multiform No”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
