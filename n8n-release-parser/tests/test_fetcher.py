"""Tests for the npm package fetcher module."""

from __future__ import annotations

import io
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from n8n_release_parser.fetcher import (
    _is_stable,
    fetch_package,
    find_node_files,
    list_versions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_payload(
    versions: dict[str, str],
    time_map: dict[str, str],
) -> dict:
    """
    Build a minimal npm registry JSON payload.

    Parameters
    ----------
    versions:
        Mapping of version string to tarball URL.
    time_map:
        Mapping of version string to ISO-8601 publish timestamp.

    """
    ver_section: dict = {}
    for ver, tarball in versions.items():
        ver_section[ver] = {"dist": {"tarball": tarball}}
    return {"versions": ver_section, "time": time_map}


def _make_test_tarball(files: dict[str, str]) -> bytes:
    """
    Create an in-memory ``.tgz`` archive with the given file contents.

    Parameters
    ----------
    files:
        Mapping of relative path (inside the archive) to text content.

    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _is_stable
# ---------------------------------------------------------------------------


class TestIsStable:
    def test_stable_version(self) -> None:
        assert _is_stable("1.68.0") is True

    def test_beta_prerelease(self) -> None:
        assert _is_stable("1.68.0-beta.1") is False

    def test_rc_prerelease(self) -> None:
        assert _is_stable("2.0.0-rc.0") is False

    def test_alpha_prerelease(self) -> None:
        assert _is_stable("1.0.0-alpha") is False

    def test_patch_only(self) -> None:
        assert _is_stable("0.0.1") is True


# ---------------------------------------------------------------------------
# list_versions
# ---------------------------------------------------------------------------


class TestListVersions:
    @respx.mock
    async def test_returns_stable_versions_only(self) -> None:
        now = datetime.now(tz=UTC)
        recent = now.isoformat()

        payload = _make_registry_payload(
            versions={
                "1.68.0": "https://registry.npmjs.org/n8n-nodes-base/-/n8n-nodes-base-1.68.0.tgz",
                "1.69.0-beta.1": "https://registry.npmjs.org/n8n-nodes-base/-/n8n-nodes-base-1.69.0-beta.1.tgz",
                "1.69.0": "https://registry.npmjs.org/n8n-nodes-base/-/n8n-nodes-base-1.69.0.tgz",
            },
            time_map={
                "1.68.0": recent,
                "1.69.0-beta.1": recent,
                "1.69.0": recent,
            },
        )

        respx.get("https://registry.npmjs.org/n8n-nodes-base").mock(
            return_value=httpx.Response(200, json=payload),
        )

        results = await list_versions(months=12)
        version_strings = [v.version for v in results]

        assert "1.68.0" in version_strings
        assert "1.69.0" in version_strings
        assert "1.69.0-beta.1" not in version_strings

    @respx.mock
    async def test_filters_by_time_window(self) -> None:
        old_date = "2020-01-01T00:00:00+00:00"
        now = datetime.now(tz=UTC)
        recent = now.isoformat()

        payload = _make_registry_payload(
            versions={
                "1.0.0": "https://example.com/1.0.0.tgz",
                "1.68.0": "https://example.com/1.68.0.tgz",
            },
            time_map={
                "1.0.0": old_date,
                "1.68.0": recent,
            },
        )

        respx.get("https://registry.npmjs.org/n8n-nodes-base").mock(
            return_value=httpx.Response(200, json=payload),
        )

        results = await list_versions(months=12)
        version_strings = [v.version for v in results]

        assert "1.68.0" in version_strings
        assert "1.0.0" not in version_strings

    @respx.mock
    async def test_sorted_newest_first(self) -> None:
        payload = _make_registry_payload(
            versions={
                "1.66.0": "https://example.com/1.66.0.tgz",
                "1.68.0": "https://example.com/1.68.0.tgz",
                "1.67.0": "https://example.com/1.67.0.tgz",
            },
            time_map={
                "1.66.0": "2026-01-01T00:00:00+00:00",
                "1.67.0": "2026-01-15T00:00:00+00:00",
                "1.68.0": "2026-02-01T00:00:00+00:00",
            },
        )

        respx.get("https://registry.npmjs.org/n8n-nodes-base").mock(
            return_value=httpx.Response(200, json=payload),
        )

        results = await list_versions(months=12)
        versions = [v.version for v in results]

        assert versions == ["1.68.0", "1.67.0", "1.66.0"]

    @respx.mock
    async def test_empty_registry(self) -> None:
        payload: dict = {"versions": {}, "time": {}}
        respx.get("https://registry.npmjs.org/n8n-nodes-base").mock(
            return_value=httpx.Response(200, json=payload),
        )

        results = await list_versions(months=12)
        assert results == []

    @respx.mock
    async def test_skips_versions_without_tarball(self) -> None:
        now = datetime.now(tz=UTC).isoformat()
        payload = {
            "versions": {
                "1.0.0": {"dist": {}},
            },
            "time": {
                "1.0.0": now,
            },
        }
        respx.get("https://registry.npmjs.org/n8n-nodes-base").mock(
            return_value=httpx.Response(200, json=payload),
        )

        results = await list_versions(months=12)
        assert results == []


# ---------------------------------------------------------------------------
# fetch_package
# ---------------------------------------------------------------------------


class TestFetchPackage:
    @respx.mock
    async def test_downloads_and_extracts(self, tmp_path: Path) -> None:
        tarball_bytes = _make_test_tarball(
            {
                "package/index.js": "module.exports = {};",
                "package/nodes/MyNode.node.js": "// node code",
            }
        )
        respx.get(
            "https://registry.npmjs.org/n8n-nodes-base/-/n8n-nodes-base-1.68.0.tgz"
        ).mock(return_value=httpx.Response(200, content=tarball_bytes))

        result = await fetch_package("1.68.0", tmp_path)

        assert result.is_dir()
        assert result.name == "n8n-nodes-base-1.68.0"
        # The tarball should also be cached on disk.
        assert (tmp_path / "n8n-nodes-base-1.68.0.tgz").exists()

    @respx.mock
    async def test_cache_skip_download(self, tmp_path: Path) -> None:
        """When the tarball already exists the module should not re-download."""
        tarball_bytes = _make_test_tarball({"package/index.js": "module.exports = {};"})

        # Pre-seed the cache with the tarball.
        tarball_path = tmp_path / "n8n-nodes-base-1.68.0.tgz"
        tarball_path.write_bytes(tarball_bytes)

        # No mock route -- if the code tries to download it will fail.

        result = await fetch_package("1.68.0", tmp_path)
        assert result.is_dir()

    @respx.mock
    async def test_cache_skip_extraction(self, tmp_path: Path) -> None:
        """When the extracted directory already exists, skip both download and extraction."""
        extract_dir = tmp_path / "n8n-nodes-base-1.68.0"
        extract_dir.mkdir()

        # No mock route -- if the code tries to download it will fail.

        result = await fetch_package("1.68.0", tmp_path)
        assert result == extract_dir

    @respx.mock
    async def test_creates_cache_dir_if_absent(self, tmp_path: Path) -> None:
        cache = tmp_path / "sub" / "dir"
        assert not cache.exists()

        tarball_bytes = _make_test_tarball({"package/index.js": "module.exports = {};"})
        respx.get(
            "https://registry.npmjs.org/n8n-nodes-base/-/n8n-nodes-base-1.0.0.tgz"
        ).mock(return_value=httpx.Response(200, content=tarball_bytes))

        result = await fetch_package("1.0.0", cache)
        assert result.is_dir()
        assert cache.is_dir()


# ---------------------------------------------------------------------------
# find_node_files
# ---------------------------------------------------------------------------


class TestFindNodeFiles:
    def test_finds_node_js_files(self, tmp_path: Path) -> None:
        nodes_dir = tmp_path / "package" / "nodes" / "Slack"
        nodes_dir.mkdir(parents=True)
        (nodes_dir / "Slack.node.js").write_text("// slack node")
        (nodes_dir / "SlackHelper.js").write_text("// helper")

        gmail_dir = tmp_path / "package" / "nodes" / "Gmail"
        gmail_dir.mkdir(parents=True)
        (gmail_dir / "Gmail.node.js").write_text("// gmail node")

        results = find_node_files(tmp_path)

        names = [p.name for p in results]
        assert "Slack.node.js" in names
        assert "Gmail.node.js" in names
        assert "SlackHelper.js" not in names
        assert len(results) == 2

    def test_returns_sorted(self, tmp_path: Path) -> None:
        (tmp_path / "B.node.js").write_text("")
        (tmp_path / "A.node.js").write_text("")
        (tmp_path / "C.node.js").write_text("")

        results = find_node_files(tmp_path)
        names = [p.name for p in results]
        assert names == ["A.node.js", "B.node.js", "C.node.js"]

    def test_empty_directory(self, tmp_path: Path) -> None:
        results = find_node_files(tmp_path)
        assert results == []

    def test_nested_deeply(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "Deep.node.js").write_text("// deep")

        results = find_node_files(tmp_path)
        assert len(results) == 1
        assert results[0].name == "Deep.node.js"
