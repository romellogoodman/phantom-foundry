# Liitho Roman — changelog

Revival of St. Louis : The foundry **Liitho Roman** from *Specimen book and catalog : a price list of printers' supplies * (1907), leaf 172 (p. 164) — archive.org `specimenbookcata00inla`, 400 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/specimenbookcata00inla/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Litho Roman**: the archive's OCR read the heading as “Liitho Roman”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
