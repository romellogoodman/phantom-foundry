# Muw Satanick. Open — changelog

Revival of Boston **Muw Satanick. Open** from *A desk book of printing types; to which is appended a condensed catalogue and price list of printing machinery and materials* (1898), leaf 396 — archive.org `deskbookofprinti00amer`, 300 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/deskbookofprinti00amer/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Satanick Open**: the archive's OCR read the heading as “Muw Satanick. Open”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
