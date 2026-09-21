# Qoudy Italic — changelog

Revival of Jersey City, N.J. : American Type Founders Company **Qoudy Italic** from *Supplementary catalogue : new type faces, borders, ornaments, brass rule* ([c1917]), leaf 42 (p. 36) — archive.org `supplementarycat00daysrich`, 400 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/supplementarycat00daysrich/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Goudy Italic**: the archive's OCR read the heading as “Qoudy Italic”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
