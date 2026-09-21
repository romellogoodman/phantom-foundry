# Lining' Doric Xo. — changelog

Revival of [s.\U+fffd\] American type founders co. **Lining' Doric Xo.** from *American line type book, borders, ornaments, price list printing material and machinery* (1906), leaf 568 (p. 518) — archive.org `americanlinetype00daysrich`, 400 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/americanlinetype00daysrich/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **Lining Doric No. 520**: the archive's OCR read the heading as “Lining' Doric Xo.”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
