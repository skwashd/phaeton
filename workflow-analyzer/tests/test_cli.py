"""Tests for the CLI interface."""

from pathlib import Path

from typer.testing import CliRunner

from workflow_analyzer.cli import app

runner = CliRunner()


def test_cli_analyze(fixtures_dir: Path, tmp_path: Path) -> None:
    """Test CLI analyze."""
    result = runner.invoke(
        app,
        [
            str(fixtures_dir / "simple_linear.json"),
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Confidence Score" in result.output
    assert "Simple Linear Workflow" in result.output


def test_cli_analyze_json_only(fixtures_dir: Path, tmp_path: Path) -> None:
    """Test CLI analyze JSON only."""
    result = runner.invoke(
        app,
        [
            str(fixtures_dir / "simple_linear.json"),
            "--output-dir",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "simple_linear_report.json").exists()


def test_cli_output_contains_confidence(fixtures_dir: Path, tmp_path: Path) -> None:
    """Test CLI output contains confidence."""
    result = runner.invoke(
        app,
        [
            str(fixtures_dir / "branching.json"),
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert "Confidence Score:" in result.output
    assert "Total Nodes:" in result.output


def test_cli_creates_output_files(fixtures_dir: Path, tmp_path: Path) -> None:
    """Test CLI creates output files."""
    result = runner.invoke(
        app,
        [
            str(fixtures_dir / "merge_workflow.json"),
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "merge_workflow_report.json").exists()
    assert (tmp_path / "merge_workflow_report.md").exists()
