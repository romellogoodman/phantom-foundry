"""foundry — the pipeline CLI: shelve → catalog → found → label → cut → cast → sort → construct → justify → matrix → proof.

One face: fetch/survey/label by hand. A book: shelve, catalog, found, label --auto from readings, build."""

from __future__ import annotations

import json

import typer

from .face import Face

app = typer.Typer(help=__doc__, no_args_is_help=True)


def _out(obj) -> None:
    typer.echo(json.dumps(obj, indent=2))


@app.command()
def fetch(face: str, archive_id: str, leaf: list[int] = typer.Option(..., "--leaf", "-l", help="Leaf index (repeatable)")):
    """Pull raw JP2 page scans from an Internet Archive item into faces/<face>/specimens/."""
    from .fetch import fetch as _fetch
    _out(_fetch(Face(face), archive_id, leaf))


@app.command()
def survey(face: str, leaf: int = typer.Option(..., "--leaf", "-l"),
           min_line_height: int = typer.Option(150, help="ignore ink bands shorter than this (px)")):
    """Find display lines and letter boxes on a fetched leaf; writes a numbered sheet to name into the manifest."""
    from .cut import survey as _survey
    rec = _survey(Face(face), leaf, min_line_height=min_line_height)
    for ln in rec["lines"]:
        typer.echo(f"band {ln['band']}: y {ln['y0']}-{ln['y1']} (h {ln['height']}), {len(ln['letters'])} letters")
        for L in ln["letters"]:
            typer.echo(f"  #{L['n']:>3}  x={L['x']:<5} y={L['y']:<5} w={L['w']:<4} h={L['h']:<4} ink={L['ink']}")
    typer.echo(f"sheet: {rec['sheet']}")


@app.command()
def label(face: str, leaf: int = typer.Option(None, "--leaf", "-l"), band: int = typer.Option(None, "--band", "-b"),
          text: str = typer.Option(None, "--text", "-t", help="the characters printed on the band, in order"),
          line: str = typer.Option(None, "--line", help="specimen line name, e.g. fifteen or 42pt (the size)"),
          by: str = typer.Option("human", help="who read the line: human | claude | ocr"),
          auto: bool = typer.Option(False, "--auto", help="label every band of the face's series from the book's readings"),
          min_tall: int = typer.Option(0, help="(auto) skip bands whose tallest boxes are under this many px"),
          trust_ocr: bool = typer.Option(False, help="(auto) accept OCR text with no reading when it fits the boxes exactly")):
    """Name a surveyed band's boxes into manifest rows. Label the largest size first.

    --auto fills the manifest from books/<book>/readings.json for a face founded from a book."""
    from .cut import label as _label
    f = Face(face)
    if auto:
        from .book import Book, label_auto
        book_id = f.load().get("book")
        if not book_id:
            raise typer.BadParameter(f"{face} was not founded from a book (no `book:` in face.yaml)")
        _out(label_auto(f, Book(book_id), min_tall_px=min_tall, trust_ocr=trust_ocr))
        return
    if leaf is None or band is None or text is None or line is None:
        raise typer.BadParameter("need --leaf, --band, --text and --line (or --auto)")
    _out(_label(f, leaf, band, text, line, by=by))


# -- the book: shelve → catalog → found → read ---------------------------------

@app.command()
def shelve(archive_id: str):
    """Fetch a whole specimen book into books/<archive_id>/: metadata, every leaf's JP2, the archive's OCR."""
    from .book import shelve as _shelve
    _out(_shelve(archive_id))


@app.command()
def catalog(archive_id: str, leaves: str = typer.Option(None, "--leaves", help="e.g. 889-900 or 450,451 (default: every leaf)"),
            min_line_height: int = typer.Option(120, help="ignore ink bands shorter than this (px)"),
            workers: int = typer.Option(0, help="parallel leaves (default: cores − 1)"),
            force: bool = typer.Option(False, help="re-survey leaves that already have a survey")):
    """Survey every leaf of a shelved book and index its display bands by the series each caption names."""
    from .book import catalog as _catalog
    _out(_catalog(archive_id, _leaf_list(leaves), min_line_height=min_line_height, workers=workers, force=force))


def _leaf_list(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


@app.command()
def series(archive_id: str, min_tall: int = typer.Option(140, help="tallest boxes at least this many px"),
           min_boxes: int = typer.Option(8)):
    """List the series in a book's catalog worth founding, largest showing first."""
    from .book import Book, candidates
    for s in candidates(Book(archive_id), min_tall_px=min_tall, min_boxes=min_boxes):
        sizes = ", ".join(f"{z}{s['unit']}" for z in s["sizes"])
        typer.echo(f"{s['slug']:<40} {s['max_tall_px']:>4}px  {s['boxes']:>4} boxes  leaves {s['leaves']}  pages {s['pages']}  sizes {sizes}")


@app.command()
def found(face: str, book: str = typer.Option(..., "--book"), series: str = typer.Option(..., "--series"),
          title: str = typer.Option(None), leaves: str = typer.Option(None, "--leaves", help="subset of the series' leaves")):
    """Start a face from a series in a book's catalog: face.yaml, linked leaves, copied surveys."""
    from .book import Book, found as _found
    _out(_found(face, Book(book), series, title=title, leaves=_leaf_list(leaves)))


@app.command()
def read(archive_id: str, leaf: int = typer.Option(None, "--leaf", "-l"), band: int = typer.Option(None, "--band", "-b"),
         text: str = typer.Option(None, "--text", "-t", help="one character per numbered box, spaces between words; empty = not type"),
         by: str = typer.Option("human", help="who read it: human | claude"),
         note: str = typer.Option("", help="anything worth recording about the reading"),
         from_file: str = typer.Option(None, "--from", help="JSON list of {leaf, band, text, note?} to import")):
    """Record what a display band says (books/<id>/readings.json). Labels are made from readings, never from OCR alone."""
    from .book import Book, import_readings, read as _read
    b = Book(archive_id)
    if from_file:
        _out(import_readings(b, from_file, by=by))
        return
    if leaf is None or band is None or text is None:
        raise typer.BadParameter("need --leaf, --band and --text (or --from)")
    _out(_read(b, leaf, band, text, by=by, note=note))


@app.command()
def cut(face: str, glyph: list[str] = typer.Option(None, "--glyph", "-g", help="Glyph name (repeatable); default all")):
    """Punchcutting: crop glyphs from specimen scans per glyphs/manifest.csv."""
    from .cut import cut as _cut
    _out(_cut(Face(face), glyph or None))


@app.command()
def cast(face: str, glyph: list[str] = typer.Option(None, "--glyph", "-g"),
         engine: str = typer.Option("potrace", help="potrace | arrow"),
         from_svg: str = typer.Option(None, "--from", help="(arrow) path to SVG returned by Arrow"),
         model: str = typer.Option(None, help="(arrow) model id"),
         task_id: str = typer.Option(None, help="(arrow) Quiver task id"),
         creation_id: str = typer.Option(None, help="(arrow) Quiver creation id"),
         input_png: str = typer.Option(None, "--input", help="(arrow) the PNG actually sent, if a variant")):
    """Vectorize cut glyphs. potrace runs locally; arrow ingests an SVG the agent fetched via Quiver MCP."""
    from .cast import cast_potrace, cast_arrow_ingest
    f = Face(face)
    if engine == "potrace":
        _out(cast_potrace(f, glyph or None))
    elif engine == "arrow":
        if not (glyph and len(glyph) == 1 and from_svg):
            raise typer.BadParameter("arrow ingest needs exactly one --glyph and --from <svg>")
        _out(cast_arrow_ingest(f, glyph[0], from_svg, model=model, task_id=task_id,
                               creation_id=creation_id, input_png=input_png))
    else:
        raise typer.BadParameter("engine must be potrace or arrow")


@app.command()
def frame(face: str, glyph: str = typer.Option(..., "--glyph", "-g"),
          size: int = typer.Option(768), margin: float = typer.Option(0.2)):
    """Re-frame a cut glyph on a square, margined canvas as an Arrow input variant."""
    from .cast import frame as _frame
    _out(_frame(Face(face), glyph, size=size, margin=margin))


@app.command()
def diff(face: str, glyph: list[str] = typer.Option(None, "--glyph", "-g")):
    """Compare Arrow vs potrace traces for a glyph (deviation metrics → log/diff.jsonl)."""
    from .cast import diff as _diff
    _out(_diff(Face(face), glyph or None))


@app.command()
def sort(face: str, glyph: list[str] = typer.Option(None, "--glyph", "-g"),
         engine: str = typer.Option("potrace", help="which trace feeds the UFO: potrace | arrow")):
    """Normalize traces (UPM, baseline, winding, counters) into the face's UFO."""
    from .sort import sort as _sort
    _out(_sort(Face(face), glyph or None, engine=engine))


@app.command()
def construct(face: str, glyph: list[str] = typer.Option(None, "--glyph", "-g")):
    """Build the letters the specimen doesn't show from recipes in faces/<face>/construct.yaml (flagged constructed)."""
    from .construct import construct as _construct
    _out(_construct(Face(face), glyph or None))


@app.command()
def justify(face: str, glyph: list[str] = typer.Option(None, "--glyph", "-g")):
    """Set sidebearings from each side's ink profile; target from the specimen's printed gaps (face.yaml metrics.spacing)."""
    from .justify import justify as _justify
    _out(_justify(Face(face), glyph or None))


@app.command()
def matrix(face: str, formats: str = typer.Option("otf,ttf", help="comma-separated: otf,ttf")):
    """Assemble: finalize UFO metadata and compile to dist/ with fontmake."""
    from .matrix import matrix as _matrix
    _out(_matrix(Face(face), formats.split(",")))


@app.command()
def proof(face: str, glyph_sheets: bool = typer.Option(None, "--glyph-sheets/--no-glyph-sheets",
                                                     help="per-glyph overlay/traces sheets (default: only with Arrow research)")):
    """Render specimen sheets, the alphabet, checks and face.json into proofs/."""
    from .proof import proof as _proof
    _out(_proof(Face(face), glyph_sheets=glyph_sheets))


@app.command()
def build(face: str = typer.Argument(None), all_faces: bool = typer.Option(False, "--all", help="every face under faces/"),
          book: str = typer.Option(None, "--book", help="every face founded from this book"),
          jobs: int = typer.Option(4, "--jobs", "-j"), force: bool = typer.Option(False, help="run every stage even if unchanged"),
          stages: str = typer.Option(None, help="comma-separated subset, e.g. justify,matrix,proof")):
    """Run cut → cast → sort → construct → justify → matrix → proof, skipping stages whose inputs are unchanged."""
    from .build import all_faces as _all, build as _build, build_many
    if all_faces or book:
        _out(build_many(_all(book), jobs=jobs, force=force))
    elif face:
        _out(_build(Face(face), stages.split(",") if stages else None, force=force))
    else:
        raise typer.BadParameter("give a face, --all, or --book <id>")


@app.command()
def showing(book: str = typer.Option(None, "--book", help="only faces founded from this book")):
    """One sheet across every face — status, glyph counts, warnings, alphabets — at showing/index.html."""
    from .showing import showing as _showing
    _out(_showing(book))


if __name__ == "__main__":
    app()
