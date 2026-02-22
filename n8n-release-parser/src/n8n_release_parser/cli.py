"""
CLI entry point for the n8n release parser.

Orchestrates all Component 1 operations: fetching n8n releases, parsing node
descriptions, diffing releases, building API spec indexes, matching nodes to
specs, and managing the versioned node catalog.
"""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer

from n8n_release_parser.catalog import NodeCatalogStore

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
    months: Annotated[
        int, typer.Option(help="Months of history to fetch.")
    ] = 12,
    cache_dir: Annotated[
        Path, typer.Option(help="Directory for cached downloads.")
    ] = Path(".n8n-cache"),
) -> None:
    """Fetch recent n8n-nodes-base releases from npm."""
    from n8n_release_parser import fetcher

    _ = cache_dir  # available for future use
    logger = logging.getLogger(__name__)
    logger.debug("Fetching releases for the last %d months", months)

    try:
        versions = asyncio.run(fetcher.list_versions(months))
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
        Path, typer.Option(help="Catalog store directory.")
    ] = Path(".n8n-catalog"),
) -> None:
    """Diff two n8n release catalogs."""
    from n8n_release_parser import differ

    store = NodeCatalogStore(store_dir)

    old_cat = store.load_catalog(old_version)
    if old_cat is None:
        typer.echo(
            f"Error: catalog for version {old_version} not found in {store_dir}"
        )
        raise typer.Exit(1)

    new_cat = store.load_catalog(new_version)
    if new_cat is None:
        typer.echo(
            f"Error: catalog for version {new_version} not found in {store_dir}"
        )
        raise typer.Exit(1)

    result = differ.diff_catalogs(old_cat, new_cat)

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


@app.command(name="build-index")
def build_index(
    specs_dir: Annotated[Path, typer.Argument()],
    output: Annotated[
        Path, typer.Option(help="Output path for the index JSON.")
    ] = Path("spec_index.json"),
) -> None:
    """Build an API spec index from a directory of OpenAPI/Swagger files."""
    from n8n_release_parser import spec_index

    try:
        index = spec_index.build_spec_index(specs_dir)
        spec_index.save_index(index, output)
    except Exception as exc:
        typer.echo(f"Error: failed to build spec index: {exc}")
        raise typer.Exit(1) from exc

    typer.echo(f"Indexed {len(index.entries)} specs -> {output}")


@app.command()
def match(
    store_dir: Annotated[
        Path, typer.Option(help="Catalog store directory.")
    ] = Path(".n8n-catalog"),
    index_file: Annotated[
        Path, typer.Option(help="Path to the spec index JSON.")
    ] = Path("spec_index.json"),
    version: Annotated[
        str, typer.Option(help="n8n version to match.")
    ] = ...,
) -> None:
    """Match catalog nodes against API specs."""
    from n8n_release_parser import matcher
    from n8n_release_parser.spec_index import load_index

    store = NodeCatalogStore(store_dir)
    catalog = store.load_catalog(version)
    if catalog is None:
        typer.echo(f"Error: catalog for version {version} not found in {store_dir}")
        raise typer.Exit(1)

    if not index_file.exists():
        typer.echo(f"Error: spec index file not found: {index_file}")
        raise typer.Exit(1)

    try:
        index = load_index(index_file)
    except Exception as exc:
        typer.echo(f"Error: failed to load spec index: {exc}")
        raise typer.Exit(1) from exc

    mappings = matcher.match_all_nodes(catalog, index)
    store.save_api_mappings(mappings)

    matched_count = len(mappings)
    total_count = len(catalog.entries)
    unmatched_count = total_count - matched_count

    typer.echo(f"Matched {matched_count}/{total_count} nodes.")
    if unmatched_count:
        typer.echo(f"Unmatched: {unmatched_count}")


@app.command()
def lookup(
    node_type: Annotated[str, typer.Argument()],
    store_dir: Annotated[
        Path, typer.Option(help="Catalog store directory.")
    ] = Path(".n8n-catalog"),
    type_version: Annotated[
        int | None, typer.Option("--version", help="Specific type version to look up.")
    ] = None,
) -> None:
    """Look up a node type across stored catalogs."""
    store = NodeCatalogStore(store_dir)

    try:
        all_entries = store.build_lookup()
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
        Path, typer.Option(help="Catalog store directory.")
    ] = Path(".n8n-catalog"),
) -> None:
    """Generate priority coverage report from the latest catalog."""
    from n8n_release_parser import priority

    store = NodeCatalogStore(store_dir)

    catalogs = store.list_catalogs()
    if not catalogs:
        typer.echo("Error: no catalogs found in store.")
        raise typer.Exit(1)

    latest_version = catalogs[0][0]
    catalog = store.load_catalog(latest_version)
    if catalog is None:
        typer.echo(f"Error: could not load catalog for {latest_version}.")
        raise typer.Exit(1)

    mappings = store.load_api_mappings()

    result = priority.priority_coverage_report(catalog, mappings)

    total = result["total_priority_nodes"]
    mapped = result["mapped_priority_nodes"]
    missing = result["missing_mappings"]
    breakdown = result["breakdown"]

    typer.echo(f"Priority Coverage Report (v{latest_version})")
    typer.echo(f"  Total priority nodes:  {total}")
    typer.echo(f"  Mapped priority nodes: {mapped}")

    if isinstance(breakdown, dict):
        typer.echo("\n  Breakdown:")
        for group, count in breakdown.items():
            typer.echo(f"    {group}: {count}")

    if isinstance(missing, list) and missing:
        typer.echo(f"\n  Missing mappings ({len(missing)}):")
        for node_type in missing:
            typer.echo(f"    - {node_type}")


def main() -> None:
    """Entry point wrapper for the CLI."""
    app()
