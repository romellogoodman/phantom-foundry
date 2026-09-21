# Extra Condensed No — changelog

Revival of Boston **Extra Condensed No** from *Specimen book from the Boston type foundry * (1889), leaf 137 (p. 131) — archive.org `specimenbookfrom00unse`, 300 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/specimenbookfrom00unse/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Extra Condensed No. 2**: the archive's OCR read the heading as “Extra Condensed No”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
