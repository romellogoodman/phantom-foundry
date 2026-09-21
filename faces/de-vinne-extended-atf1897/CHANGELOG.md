# De Yiivne Extended — changelog

Revival of Chicago : American Type Founders **De Yiivne Extended** from *Specimens of type, borders, ornaments, brass rules and cuts, etc* (1897), leaf 354 (p. 352) — archive.org `specimensoftypeb00amer`, 500 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/specimensoftypeb00amer/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **De Vinne Extended**: the archive's OCR read the heading as “De Yiivne Extended”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
