"""Dev-only CLI for the spec registry."""

import json
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Spec registry: build and query API spec indexes.")


@app.command()
def build_index(
    specs_dir: Annotated[
        Path,
        typer.Argument(help="Directory containing API spec files."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path to write the spec index JSON."),
    ] = Path("spec_index.json"),
) -> None:
    """Build a spec index from a local directory of API spec files."""
    from spec_registry.indexer import build_spec_index, save_index

    if not specs_dir.is_dir():
        typer.echo(f"Error: {specs_dir} is not a directory", err=True)
        raise typer.Exit(code=1)

    index = build_spec_index(specs_dir)
    save_index(index, output)

    typer.echo(f"Index built: {len(index.entries)} entries -> {output}")


@app.command()
def match(
    index_path: Annotated[
        Path,
        typer.Argument(help="Path to a spec index JSON file."),
    ],
    node_types: Annotated[
        list[str],
        typer.Argument(help="Node type strings to match (e.g. n8n-nodes-base.slack)."),
    ],
) -> None:
    """Match n8n node types against a spec index."""
    from spec_registry.indexer import load_index
    from spec_registry.matcher import match_all_nodes

    if not index_path.exists():
        typer.echo(f"Error: {index_path} does not exist", err=True)
        raise typer.Exit(code=1)

    spec_index = load_index(index_path)
    results = match_all_nodes(node_types, spec_index)

    if not results:
        typer.echo("No matches found.")
        return

    output = {
        node_type: {
            "spec_filename": entry.spec_filename,
            "service_name": entry.service_name,
        }
        for node_type, entry in results.items()
    }
    typer.echo(json.dumps(output, indent=2))
