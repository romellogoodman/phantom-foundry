# Phantom Foundry

An open-source font foundry reviving public domain typefaces from scanned
specimen books, using [Quiver AI's Arrow model](https://quiver.ai) (image → SVG)
and bespoke tooling.

Revivals work from printed specimens — Internet Archive scans of metal-type
specimen books from foundries like ATF, Barnhart Brothers & Spindler, and
Inland Type Foundry. Each typeface moves through a six-stage pipeline named
from foundry vocabulary:

```
fetch → cut → cast → sort → matrix → proof
```

Every stage reads and writes plain files, every glyph keeps its provenance,
and every Arrow trace runs alongside a deterministic potrace control — because
the gap between the historical hand and the model's interpretation of it is
the research, not a defect.

See [agent_docs/architecture.md](agent_docs/architecture.md) for the full
system design.

## Status

Early. The architecture is sketched; the tools are next.
