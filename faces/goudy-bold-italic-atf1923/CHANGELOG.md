# Qoudy Bold Italic — changelog

Revival of [Jersey City] : American Type Founders Co. **Qoudy Bold Italic** from *Specimen book and catalogue, 1923 --* (1923), leaf 349 (p. 47) — archive.org `specimenbookcata00amer`, 500 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/specimenbookcata00amer/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Goudy Bold Italic**: the archive's OCR read the heading as “Qoudy Bold Italic”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
