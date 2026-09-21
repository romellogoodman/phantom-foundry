# Lining Old Style No. Italic. — changelog

Revival of Toronto : Stephenson, Blake & Co. **Lining Old Style No. Italic.** from *Specimens of point line type : borders ornaments brass rules &c* (1908), leaf 20 (p. 6) — archive.org `specimensofpoint00step`, 350 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/specimensofpoint00step/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Lining Old Style No. 5 Italic**: the archive's OCR read the heading as “Lining Old Style No. Italic.”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
