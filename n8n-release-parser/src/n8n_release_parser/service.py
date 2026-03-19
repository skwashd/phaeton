"""
Core service layer for the n8n release parser.

Pure functions that both the Lambda handler and CLI call. Each function
accepts explicit parameters and returns data — no file I/O formatting,
no CLI output, no Typer dependencies.
"""

from __future__ import annotations

import asyncio
from typing import Any

from n8n_release_parser.catalog import NodeCatalogStore
from n8n_release_parser.models import (
    NodeTypeEntry,
    NpmVersionInfo,
    ReleaseDiff,
)
from n8n_release_parser.storage import StorageBackend


def list_versions(months: int = 12) -> list[NpmVersionInfo]:
    """Fetch stable n8n-nodes-base versions from npm within a time window."""
    from n8n_release_parser.fetcher import list_versions as _async_list_versions

    return asyncio.run(_async_list_versions(months=months))


def fetch_releases(months: int = 12) -> list[NpmVersionInfo]:
    """
    Fetch recent n8n-nodes-base releases from npm.

    Alias for :func:`list_versions` exposed as a distinct operation name
    so that handler consumers can use the more descriptive operation key.
    """
    return list_versions(months=months)


def diff_catalogs(
    backend: StorageBackend,
    old_version: str,
    new_version: str,
) -> ReleaseDiff:
    """
    Load two catalogs from the store and diff them.

    Raises
    ------
    ValueError
        If either catalog version is not found in the store.

    """
    from n8n_release_parser import differ

    store = NodeCatalogStore(backend)

    old_cat = store.load_catalog(old_version)
    if old_cat is None:
        msg = f"Catalog for version {old_version} not found"
        raise ValueError(msg)

    new_cat = store.load_catalog(new_version)
    if new_cat is None:
        msg = f"Catalog for version {new_version} not found"
        raise ValueError(msg)

    return differ.diff_catalogs(old_cat, new_cat)


def build_catalog(
    backend: StorageBackend,
) -> dict[tuple[str, int], NodeTypeEntry]:
    """
    Build a cumulative lookup map from all stored catalogs.

    Returns a dictionary keyed by ``(node_type, type_version)`` tuples.
    """
    store = NodeCatalogStore(backend)
    return store.build_lookup()


def generate_report(backend: StorageBackend) -> dict[str, object]:
    """
    Generate a priority coverage report from the latest catalog.

    Raises
    ------
    ValueError
        If no catalogs exist in the store or the latest cannot be loaded.

    """
    from n8n_release_parser import priority

    store = NodeCatalogStore(backend)
    catalogs = store.list_catalogs()
    if not catalogs:
        msg = "No catalogs found in store"
        raise ValueError(msg)

    latest_version = catalogs[0][0]
    catalog = store.load_catalog(latest_version)
    if catalog is None:
        msg = f"Could not load catalog for {latest_version}"
        raise ValueError(msg)

    mappings = store.load_api_mappings()
    result: dict[str, object] = priority.priority_coverage_report(catalog, mappings)
    return result


def list_catalogs(backend: StorageBackend) -> list[dict[str, Any]]:
    """
    List all stored catalogs with version and release date.

    Returns a list of dicts with ``version`` and ``release_date`` keys,
    sorted newest-first.
    """
    store = NodeCatalogStore(backend)
    return [
        {"version": version, "release_date": release_date.isoformat()}
        for version, release_date in store.list_catalogs()
    ]
