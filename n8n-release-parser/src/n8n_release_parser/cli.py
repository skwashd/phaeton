"""
CLI entry point for the n8n release parser.

Thin adapter layer that parses CLI arguments, calls :mod:`service` functions,
and formats output for the terminal. All business logic lives in ``service.py``.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer

from n8n_release_parser import service
from n8n_release_parser.storage import create_backend

app = typer.Typer()


@app.callback()
def _callback(
    verbose: Annotated[
        bool, typer.Option("-v", "--verbose", help="Enable verbose logging.")
    ] = False,
) -> None:
    """n8n Release Parser — maintain a versioned catalog of n8n node types."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )


@app.command()
def fetch_releases(
    months: Annotated[int, typer.Option(help="Months of history to fetch.")] = 12,
    cache_dir: Annotated[
        Path, typer.Option(help="Directory for cached downloads.")
    ] = Path(".n8n-cache"),
) -> None:
    """Fetch recent n8n-nodes-base releases from npm."""
    _ = cache_dir  # available for future use

    try:
        versions = service.fetch_releases(months=months)
    except Exception as exc:
        typer.echo(f"Error: failed to fetch releases: {exc}")
        raise typer.Exit(1) from exc

    for info in versions:
        typer.echo(f"{info.version}  {info.publish_date:%Y-%m-%d}")

    typer.echo(f"\n{len(versions)} releases found.")


@app.command()
def diff(
    old_version: Annotated[str, typer.Argument()],
    new_version: Annotated[str, typer.Argument()],
    store_dir: Annotated[
        str, typer.Option(help="Catalog store directory or s3:// URI.")
    ] = ".n8n-catalog",
) -> None:
    """Diff two n8n release catalogs."""
    backend = create_backend(store_dir)

    try:
        result = service.diff_catalogs(backend, old_version, new_version)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    typer.echo(f"Diff {result.from_version} -> {result.to_version}")
    typer.echo(f"  Added:    {result.added_count}")
    typer.echo(f"  Removed:  {result.removed_count}")
    typer.echo(f"  Modified: {result.modified_count}")

    if result.changes:
        typer.echo("\nChanges:")
        for change in result.changes:
            typer.echo(f"  [{change.change_type.value}] {change.node_type}")
            for field in change.changed_fields:
                typer.echo(f"    - {field}")


@app.command()
def lookup(
    node_type: Annotated[str, typer.Argument()],
    store_dir: Annotated[
        str, typer.Option(help="Catalog store directory or s3:// URI.")
    ] = ".n8n-catalog",
    type_version: Annotated[
        int | None, typer.Option("--version", help="Specific type version to look up.")
    ] = None,
) -> None:
    """Look up a node type across stored catalogs."""
    backend = create_backend(store_dir)

    try:
        all_entries = service.build_catalog(backend)
    except Exception as exc:
        typer.echo(f"Error: failed to build lookup: {exc}")
        raise typer.Exit(1) from exc

    matches = {
        key: entry
        for key, entry in all_entries.items()
        if key[0] == node_type and (type_version is None or key[1] == type_version)
    }

    if not matches:
        typer.echo(f"No entries found for {node_type!r}.")
        return

    for (ntype, ver), entry in sorted(matches.items(), key=lambda item: item[0][1]):
        typer.echo(f"{ntype} v{ver}")
        typer.echo(f"  Display name: {entry.display_name}")
        typer.echo(f"  Description:  {entry.description}")
        typer.echo(f"  Parameters:   {len(entry.parameters)}")
        typer.echo(f"  Operations:   {len(entry.resource_operations)}")
        typer.echo(f"  Credentials:  {len(entry.credential_types)}")


@app.command()
def report(
    store_dir: Annotated[
        str, typer.Option(help="Catalog store directory or s3:// URI.")
    ] = ".n8n-catalog",
) -> None:
    """Generate priority coverage report from the latest catalog."""
    backend = create_backend(store_dir)

    try:
        result = service.generate_report(backend)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    total = result["total_priority_nodes"]
    mapped = result["mapped_priority_nodes"]
    missing = result["missing_mappings"]
    breakdown = result["breakdown"]

    typer.echo("Priority Coverage Report")
    typer.echo(f"  Total priority nodes:  {total}")
    typer.echo(f"  Mapped priority nodes: {mapped}")

    if isinstance(breakdown, dict):
        typer.echo("\n  Breakdown:")
        for group, count in breakdown.items():
            typer.echo(f"    {group}: {count}")

    if isinstance(missing, list) and missing:
        typer.echo(f"\n  Missing mappings ({len(missing)}):")
        for node_type_name in missing:
            typer.echo(f"    - {node_type_name}")


def main() -> None:
    """Entry point wrapper for the CLI."""
    app()
