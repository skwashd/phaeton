"""Tests for the CLI entry point."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from n8n_release_parser.catalog import NodeCatalogStore
from n8n_release_parser.cli import app
from n8n_release_parser.models import NodeCatalog, NodeTypeEntry


def _make_entry(
    node_type: str = "n8n-nodes-base.slack",
    type_version: int = 1,
    display_name: str = "Slack",
) -> NodeTypeEntry:
    return NodeTypeEntry(
        node_type=node_type,
        type_version=type_version,
        display_name=display_name,
    )


def _make_catalog(
    version: str,
    release_date: datetime,
    entries: list[NodeTypeEntry] | None = None,
) -> NodeCatalog:
    return NodeCatalog(
        n8n_version=version,
        release_date=release_date,
        entries=entries or [],
    )


class TestMainHelp:
    def test_main_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "fetch-releases" in result.output
        assert "diff" in result.output
        assert "build-index" in result.output
        assert "match" in result.output
        assert "lookup" in result.output
        assert "report" in result.output


class TestFetchReleases:
    def test_fetch_releases_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["fetch-releases", "--help"])
        assert result.exit_code == 0
        assert "--months" in result.output
        assert "--cache-dir" in result.output


class TestDiff:
    def test_diff_missing_catalog(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["diff", "1.19.0", "1.20.0", "--store-dir", str(tmp_path)],
        )
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_diff_with_catalogs(self, tmp_path: Path) -> None:
        store = NodeCatalogStore(tmp_path)

        old_entries = [
            _make_entry("n8n-nodes-base.slack", 1, "Slack"),
            _make_entry("n8n-nodes-base.github", 1, "GitHub"),
        ]
        new_entries = [
            _make_entry("n8n-nodes-base.slack", 1, "Slack Updated"),
            _make_entry("n8n-nodes-base.discord", 1, "Discord"),
        ]

        store.save_catalog(
            _make_catalog(
                "1.19.0",
                datetime(2025, 1, 1, tzinfo=UTC),
                entries=old_entries,
            ),
        )
        store.save_catalog(
            _make_catalog(
                "1.20.0",
                datetime(2025, 2, 1, tzinfo=UTC),
                entries=new_entries,
            ),
        )

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["diff", "1.19.0", "1.20.0", "--store-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Added:" in result.output
        assert "Removed:" in result.output
        assert "Modified:" in result.output
        # discord was added, github was removed, slack was modified
        assert "1" in result.output


class TestBuildIndex:
    def test_build_index(self, tmp_path: Path) -> None:
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API"},
            "paths": {"/test": {"get": {"operationId": "getTest", "tags": ["test"]}}},
        }
        (specs_dir / "test_api.json").write_text(json.dumps(spec), encoding="utf-8")

        output_path = tmp_path / "index.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["build-index", str(specs_dir), "--output", str(output_path)],
        )
        assert result.exit_code == 0
        assert "Indexed" in result.output
        assert "1" in result.output
        assert output_path.exists()

    def test_build_index_empty_dir(self, tmp_path: Path) -> None:
        specs_dir = tmp_path / "empty_specs"
        specs_dir.mkdir()

        output_path = tmp_path / "index.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["build-index", str(specs_dir), "--output", str(output_path)],
        )
        assert result.exit_code == 0
        assert "Indexed 0 specs" in result.output


class TestMatch:
    def test_match_missing_catalog(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["match", "--version", "1.20.0", "--store-dir", str(tmp_path)],
        )
        assert result.exit_code != 0
        assert "not found" in result.output


class TestLookup:
    def test_lookup_not_found(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["lookup", "n8n-nodes-base.nonexistent", "--store-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "No entries found" in result.output


class TestReport:
    def test_report_empty_store(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["report", "--store-dir", str(tmp_path)],
        )
        assert result.exit_code != 0
        assert "no catalogs found" in result.output.lower()


class TestVerboseFlag:
    def test_verbose_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--verbose", "fetch-releases", "--help"])
        assert result.exit_code == 0
