# Cheltexham Bold Shaded — changelog

Revival of London, H.W. Caslon & Co., Ltd **Cheltexham Bold Shaded** from *Specimens of types & borders and illustrated catalogue of printers' joinery and materials* ([1915]), leaf 198 (p. 190) — archive.org `specimensoftypes00hwcarich`, 300 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/specimensoftypes00hwcarich/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Cheltenham Bold Shaded**: the archive's OCR read the heading as “Cheltexham Bold Shaded”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
