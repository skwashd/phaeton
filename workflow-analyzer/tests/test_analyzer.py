"""Integration tests for the WorkflowAnalyzer orchestrator."""

from pathlib import Path

from workflow_analyzer.analyzer import WorkflowAnalyzer


def test_analyze_simple_linear(fixtures_dir: Path) -> None:
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze(fixtures_dir / "simple_linear.json")
    assert report.total_nodes == 4
    assert report.source_workflow_name == "Simple Linear Workflow"
    assert 0 <= report.confidence_score <= 100


def test_analyze_branching(fixtures_dir: Path) -> None:
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze(fixtures_dir / "branching.json")
    assert report.total_nodes == 5


def test_analyze_merge(fixtures_dir: Path) -> None:
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze(fixtures_dir / "merge_workflow.json")
    assert report.total_nodes == 5


def test_analyze_cross_references(fixtures_dir: Path) -> None:
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze(fixtures_dir / "cross_references.json")
    assert len(report.cross_node_references) > 0


def test_analyze_and_render(fixtures_dir: Path, tmp_path: Path) -> None:
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze_and_render(
        fixtures_dir / "simple_linear.json",
        tmp_path,
    )
    assert report.total_nodes == 4

    json_file = tmp_path / "simple_linear_report.json"
    md_file = tmp_path / "simple_linear_report.md"
    assert json_file.exists()
    assert md_file.exists()
    assert json_file.stat().st_size > 0
    assert md_file.stat().st_size > 0


def test_analyze_and_render_json_only(fixtures_dir: Path, tmp_path: Path) -> None:
    analyzer = WorkflowAnalyzer()
    analyzer.analyze_and_render(
        fixtures_dir / "simple_linear.json",
        tmp_path,
        formats=["json"],
    )
    assert (tmp_path / "simple_linear_report.json").exists()
    assert not (tmp_path / "simple_linear_report.md").exists()


def test_all_fixtures_pass(fixtures_dir: Path) -> None:
    analyzer = WorkflowAnalyzer()
    for path in fixtures_dir.glob("*.json"):
        report = analyzer.analyze(path)
        assert report.total_nodes > 0
        assert len(report.classified_nodes) == report.total_nodes
