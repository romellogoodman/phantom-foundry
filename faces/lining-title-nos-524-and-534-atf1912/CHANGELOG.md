# Lining Title Nos. and — changelog

Revival of Jersey City, N.J. : American Type Founders Company **Lining Title Nos. and** from *American specimen book of type styles : complete catalogue of printing machinery and printing supplies, 1912* (1912), leaf 670 (p. 648) — archive.org `americanspecimen00amer`, 400 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/americanspecimen00amer/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Lining Title Nos. 524 and 534**: the archive's OCR read the heading as “Lining Title Nos. and”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
