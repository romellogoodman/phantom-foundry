"""foundry — the six-stage pipeline CLI: fetch → cut → cast → sort → matrix → proof."""

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
def matrix(face: str, formats: str = typer.Option("otf,ttf", help="comma-separated: otf,ttf")):
    """Assemble: finalize UFO metadata and compile to dist/ with fontmake."""
    from .matrix import matrix as _matrix
    _out(_matrix(Face(face), formats.split(",")))


@app.command()
def proof(face: str):
    """Render specimen sheets and scan overlays into proofs/."""
    from .proof import proof as _proof
    _out(_proof(Face(face)))


if __name__ == "__main__":
    app()
