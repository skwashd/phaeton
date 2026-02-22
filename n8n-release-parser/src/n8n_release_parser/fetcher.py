"""
Fetch n8n-nodes-base packages from the npm registry.

Provides helpers to list available versions, download and extract tarballs,
and locate node description files inside the extracted package tree.
"""

from __future__ import annotations

import tarfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

from n8n_release_parser.models import NpmVersionInfo

_NPM_REGISTRY_URL = "https://registry.npmjs.org/n8n-nodes-base"


def _is_stable(version: str) -> bool:
    """Return True when *version* has no pre-release suffix."""
    # A pre-release version contains a hyphen after the patch number,
    # e.g. "1.0.0-beta.1" or "1.0.0-rc.0".
    parts = version.split("-", 1)
    return len(parts) == 1


async def list_versions(months: int = 12) -> list[NpmVersionInfo]:
    """
    Query npm registry for stable n8n-nodes-base versions within the time window.

    Parameters
    ----------
    months:
        How many months back from *now* to include.

    Returns
    -------
    list[NpmVersionInfo]
        Versions sorted newest-first by publish date.

    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _NPM_REGISTRY_URL,
            headers={"Accept": "application/json"},
            timeout=60.0,
        )
        resp.raise_for_status()

    data = resp.json()
    versions_dict: dict[str, dict] = data.get("versions", {})
    time_dict: dict[str, str] = data.get("time", {})

    now = datetime.now(tz=UTC)

    # Calculate cutoff: go back *months* calendar months from today.
    total_months = now.year * 12 + (now.month - 1) - months
    cutoff_year, cutoff_month_idx = divmod(total_months, 12)
    cutoff = now.replace(year=cutoff_year, month=cutoff_month_idx + 1, day=1)

    results: list[NpmVersionInfo] = []
    for version, meta in versions_dict.items():
        if not _is_stable(version):
            continue

        time_str = time_dict.get(version)
        if time_str is None:
            continue

        publish_date = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        if publish_date < cutoff:
            continue

        tarball_url: str = meta.get("dist", {}).get("tarball", "")
        if not tarball_url:
            continue

        results.append(
            NpmVersionInfo(
                version=version,
                publish_date=publish_date,
                tarball_url=tarball_url,
            )
        )

    results.sort(key=lambda v: v.publish_date, reverse=True)
    return results


async def fetch_package(version: str, cache_dir: Path) -> Path:
    """
    Download and extract npm tarball for the given version.

    Parameters
    ----------
    version:
        The exact version string, e.g. ``"1.68.0"``.
    cache_dir:
        Directory used for caching tarballs and extracted trees.

    Returns
    -------
    Path
        Path to the extracted package directory.

    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    tarball_name = f"n8n-nodes-base-{version}.tgz"
    tarball_path = cache_dir / tarball_name
    extract_dir = cache_dir / f"n8n-nodes-base-{version}"

    # If already extracted, return immediately.
    if extract_dir.is_dir():
        return extract_dir

    # Download tarball if not cached.
    if not tarball_path.exists():
        url = (
            f"https://registry.npmjs.org/n8n-nodes-base/-/n8n-nodes-base-{version}.tgz"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=120.0, follow_redirects=True)
            resp.raise_for_status()
            tarball_path.write_bytes(resp.content)

    # Extract tarball.
    extract_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball_path, "r:gz") as tar:
        tar.extractall(path=extract_dir, filter="data")

    return extract_dir


def find_node_files(package_dir: Path) -> list[Path]:
    """
    Find all node description files within the extracted package.

    Looks for ``.node.js`` files inside the extracted tree, which is the
    standard naming convention for compiled n8n node descriptions.

    Parameters
    ----------
    package_dir:
        Root of the extracted package (the directory returned by
        :func:`fetch_package`).

    Returns
    -------
    list[Path]
        Sorted list of paths to node description files.

    """
    return sorted(package_dir.rglob("*.node.js"))
