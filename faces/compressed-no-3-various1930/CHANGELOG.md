# Compressed No — changelog

Revival of Waterlow & Sons Ltd. **Compressed No** from *Specimen Book of Printing Type* (1930-01), leaf 166 (p. 154) — archive.org `bwb_P9-EDB-136`, 360 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/bwb_P9-EDB-136/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Compressed No. 3**: the archive's OCR read the heading as “Compressed No”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
