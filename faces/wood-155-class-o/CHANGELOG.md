# Wood 155 Class O — changelog

Revival of Barnhart Bros. & Spindler wood type **No. 155, Class O** (a
Clarendon), from *Book of Type Specimens, Specimen Book No. 9* (Chicago, 1907),
leaf 892 / printed page 848 — archive.org `bookoftypespecim00barnrich`, 400 ppi,
public domain.

Maturity: **proto** (0.x, traced, machine-spaced) → **draft** → **release**.

## 0.1.1 — 2026-09-04 · proto

- The twelve-line E in DIE on leaf 892 is printed **mirror-reversed** — the block's stem is on
  the right and its counters open to the left. It had been traced as the encoded E. It is now
  `Ereversed` (Ǝ, U+018E), exactly as printed, and the six-line E is the encoded E. Found by
  the reading pass that re-transcribed every band of the book; the page is the evidence.

## 0.1.0 — 2026-08-30 · proto

- Everything the page shows, traced with potrace from five sizes: "DIE" (twelve-line),
  "ROGUE" (six), "BINDER" (five), "NORTH 29" (four), "Rose Garden 6" (three).
  Capitals B D E G H I N O R T U; lowercase a d e n o r s; figures 2 6 9;
  same-letter alternates from other sizes kept unencoded.
- Glyphs from each line share its baseline and scale; lowercase lands at an
  x-height of 513 units.
- Spacing derived from the printed gaps (half the median: 26 units a side).
- No constructed letters yet; no kerning.
