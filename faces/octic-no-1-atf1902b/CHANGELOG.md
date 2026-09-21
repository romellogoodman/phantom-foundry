# Octic No I — changelog

Revival of [Philadelphia] **Octic No I** from *Desk book of type specimens, borders, ornaments, brass rules and cuts; (Vol* (1902), leaf 65 — archive.org `deskbookoftypesp02amer`, 300 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/deskbookoftypesp02amer/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Octic No 1**: the archive's OCR read the heading as “Octic No I”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
