"""Integration tests for the WorkflowAnalyzer orchestrator."""

from pathlib import Path

from workflow_analyzer.analyzer import WorkflowAnalyzer


def test_analyze_simple_linear(fixtures_dir: Path) -> None:
    """Test analyze simple linear."""
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze(fixtures_dir / "simple_linear.json")
    assert report.total_nodes == 4
    assert report.source_workflow_name == "Simple Linear Workflow"
    assert 0 <= report.confidence_score <= 100


def test_analyze_branching(fixtures_dir: Path) -> None:
    """Test analyze branching."""
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze(fixtures_dir / "branching.json")
    assert report.total_nodes == 5


def test_analyze_merge(fixtures_dir: Path) -> None:
    """Test analyze merge."""
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze(fixtures_dir / "merge_workflow.json")
    assert report.total_nodes == 5


def test_analyze_cross_references(fixtures_dir: Path) -> None:
    """Test analyze cross references."""
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze(fixtures_dir / "cross_references.json")
    assert len(report.cross_node_references) > 0


def test_all_fixtures_pass(fixtures_dir: Path) -> None:
    """Test all fixtures pass."""
    analyzer = WorkflowAnalyzer()
    for path in fixtures_dir.glob("*.json"):
        report = analyzer.analyze(path)
        assert report.total_nodes > 0
        assert len(report.classified_nodes) == report.total_nodes
