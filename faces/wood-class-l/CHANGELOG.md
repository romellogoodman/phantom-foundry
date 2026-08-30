# Wood Class L — changelog

Revival of Barnhart Bros. & Spindler wood type **No. 266, Class L** (a condensed
gothic), from *Book of Type Specimens, Specimen Book No. 9* (Chicago, 1907), leaf
895 — archive.org `bookoftypespecim00barnrich`, 400 ppi, public domain.

Maturity: **proto** (0.x, traced and constructed, machine-spaced) → **draft**
(reviewed by a person) → **release** (1.0: spaced, kerned, cleaned, tested).

## 0.3.0 — 2026-08-30 · proto

- Spacing (`justify`): per-glyph sidebearings from each side's ink profile, target
  taken from the gaps between the printed letters on leaf 895 (median 25 units at
  fifteen-line, 45 at eight-line). The re-set RECORD now matches the printed line's width.
- Website: type tester (text + size), specimen lines re-set, labeled alphabet,
  four-sizes table, Arrow comparison — all read from `proofs/face.json`.
- Kerning: none yet (a human pass).

## 0.2.0 — 2026-08-30 · proto

- Full A–Z. Eleven capitals the specimen never shows — F J K Q T U V W X Y Z — are
  **constructed** from traced parts (`construct.yaml`): E without its foot is F, M
  upside down is W, A upside down minus its bar is V, and so on. Each carries its
  recipe in the glyph lib and is flagged in `face.json`; the alphabet proof shows
  them in gray.

## 0.1.0 — 2026-08-30 · proto

- Fifteen capitals traced with potrace from the four sizes shown on leaf 895:
  R E C O D (fifteen-line), H A N G B L (eight-line), M S I (six-line), P (five-line).
  Fifteen same-letter alternates from the other sizes are kept unencoded (`E.six`, …).
- Glyphs from the same specimen line share its baseline and scale; the round letters
  turn out to have no overshoot, and the smaller cuts are relatively bolder
  (stem 13.9% of cap height at fifteen-line, 16.2% at five-line).
- Flat 40-unit sidebearings.

## 0.0.1 — 2026-08-29

- One glyph, R, end to end: fetch → cut → cast (potrace + two Arrow attempts) →
  sort → matrix → proof. Arrow drew pictures of the letter rather than its edge;
  the font is built from the potrace trace.
