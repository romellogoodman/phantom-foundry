# Freivch Clarendon Ex. Cond. — changelog

Revival of Chicago : The Company **Freivch Clarendon Ex. Cond.** from *Abridged specimen book : type, borders, brass rules, ornaments and price list of printing machinery, furniture, fixtures and material* (1899), leaf 221 (p. 217) — archive.org `abridgedspecimen00adfa`, 500 ppi, public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** (reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.1.0 — 2026-09-21 · proto

- Founded from the book catalog: every letter the specimen shows at display size, traced with potrace.
  Who read each line is recorded with the reading (`books/abridgedspecimen00adfa/readings.json`, `by`) and
  shown on the face's page; the archive's OCR is only a cross-check. No constructed letters.
- Named **French Clarendon Ex. Cond**: the archive's OCR read the heading as “Freivch Clarendon Ex. Cond.”; the name was read again from the page image. The OCR reading is kept in `face.yaml` (`series`, `heading_as_read`).
