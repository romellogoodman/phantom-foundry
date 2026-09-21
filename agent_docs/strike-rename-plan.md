# "proto" and "strike" in code and data: a plan, not executed

Words on the site, README and docs now say *strike*. Code and data still say
`status: proto`. This is what changing that would touch, and whether it should.

## Does proto → draft → release still make sense?

It describes a face the foundry means to finish. Most strikes are not that:
the foundry's job ends at the handoff, and a strike someone else finishes is no
longer a strike. So *strike* is what the object **is**, not a stage it is
**at**. Swapping the word `proto` for `strike` one-for-one would keep a ladder
that most faces will never climb.

**Recommended:** two fields instead of one.

- `kind: strike` — one showing from one book, machine-made. (Later: `kind:
  design` for the merged, derived object in `cross-book-identity.md`.)
- `review: none | looked-at | corrected` — what a person has done to it. A
  strike that has been looked at and found sound is still a strike; one whose
  UFO has been edited is `corrected`, and that is the moment its `.gitignore`
  goes and everything is committed.
- `version` stays semantic: 0.x while only a machine has touched it.

**Alternative:** keep one field and rename only the first rung
(`strike → draft → release`). Smaller change, but it keeps implying every strike
is on its way to a release, and it makes "draft" mean "a strike a person edited",
which the word doesn't say.

## What the change touches

| Where | What |
|---|---|
| `faces/*/face.yaml` (1,512) | `status: proto` → `kind` + `review`; one scripted pass, records only |
| `tools/foundry/book.py` `found` | the template's `status`, the CHANGELOG's "Maturity:" paragraph |
| `tools/foundry/face.py` `load` default, `matrix.py` (`status` in the provenance record and `PHFD` table), `proof.py` (`face.json`), `showing.py` | read `kind`/`review`; keep reading `status` for a release or two so old records load |
| `website/src/App.jsx` | the colophon's version line; `face.status !== "proto"` in the index row |
| `.github/workflows/release.yml`, tags | unchanged: tags are `<face>/vX.Y.Z` |
| `tests/` | fixtures that write `status` |
| `CLAUDE.md`, `architecture.md` "Maturity and releases" | rewritten around kind and review |
| built fonts | the `PHFD` table and `*-provenance.json` change, so every font rebuilds and re-uploads once |

Order: teach the readers both spellings → migrate `face.yaml` → rebuild →
drop the old spelling. Half a day including the rebuild; nothing is lost if it
waits, because the public wording is already right.
