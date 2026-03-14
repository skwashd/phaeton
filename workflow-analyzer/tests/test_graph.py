"""Tests for dependency graph construction."""

from pathlib import Path

from workflow_analyzer.graph.cross_node_detector import detect_cross_node_references
from workflow_analyzer.graph.graph_builder import GraphBuilder
from workflow_analyzer.models.n8n_workflow import N8nNode
from workflow_analyzer.parser.accessors import WorkflowAccessor
from workflow_analyzer.parser.workflow_parser import WorkflowParser


def _build_graph(fixtures_dir: Path, name: str) -> tuple:
    parser = WorkflowParser()
    wf = parser.parse_file(fixtures_dir / name)
    accessor = WorkflowAccessor(wf)
    expressions = accessor.get_all_expressions()
    builder = GraphBuilder()
    graph = builder.build(wf, expressions)
    return graph, wf, accessor, expressions


def test_linear_edges(fixtures_dir: Path) -> None:
    """Test linear edges."""
    graph, *_ = _build_graph(fixtures_dir, "simple_linear.json")
    connection_edges = [e for e in graph.edges if e.edge_type == "connection"]
    assert len(connection_edges) == 3


def test_linear_topological_sort(fixtures_dir: Path) -> None:
    """Test linear topological sort."""
    graph, *_ = _build_graph(fixtures_dir, "simple_linear.json")
    order = graph.topological_sort()
    assert order.index("Manual Trigger") < order.index("Set")
    assert order.index("Set") < order.index("HTTP Request")
    assert order.index("HTTP Request") < order.index("NoOp")


def test_linear_roots(fixtures_dir: Path) -> None:
    """Test linear roots."""
    graph, *_ = _build_graph(fixtures_dir, "simple_linear.json")
    roots = graph.get_roots()
    assert roots == ["Manual Trigger"]


def test_linear_leaves(fixtures_dir: Path) -> None:
    """Test linear leaves."""
    graph, *_ = _build_graph(fixtures_dir, "simple_linear.json")
    leaves = graph.get_leaves()
    assert leaves == ["NoOp"]


def test_branching_parallel_branches(fixtures_dir: Path) -> None:
    """Test branching parallel branches."""
    graph, *_ = _build_graph(fixtures_dir, "branching.json")
    branches = graph.get_parallel_branches("Check Status")
    assert len(branches) == 2
    branch_starts = {b[0] for b in branches}
    assert branch_starts == {"Send Welcome Email", "Log Inactive"}


def test_merge_points(fixtures_dir: Path) -> None:
    """Test merge points."""
    graph, *_ = _build_graph(fixtures_dir, "merge_workflow.json")
    merge_points = graph.get_merge_points()
    assert "Merge" in merge_points


def test_no_cycle(fixtures_dir: Path) -> None:
    """Test no cycle."""
    for name in ["simple_linear.json", "branching.json", "merge_workflow.json"]:
        graph, *_ = _build_graph(fixtures_dir, name)
        assert not graph.has_cycle()


def test_cross_node_detection(fixtures_dir: Path) -> None:
    """Test cross node detection."""
    graph, _wf, _accessor, _expressions = _build_graph(
        fixtures_dir, "cross_references.json"
    )
    data_ref_edges = [e for e in graph.edges if e.edge_type == "data_reference"]
    assert len(data_ref_edges) >= 2
    source_names = {e.source_node for e in data_ref_edges}
    assert "Fetch Config" in source_names
    assert "Fetch Users" in source_names


def test_cross_node_reference_patterns(fixtures_dir: Path) -> None:
    """Test cross node reference patterns."""
    parser = WorkflowParser()
    wf = parser.parse_file(fixtures_dir / "cross_references.json")
    accessor = WorkflowAccessor(wf)
    expressions = accessor.get_all_expressions()
    refs = detect_cross_node_references(expressions)
    patterns_used = {r.reference_pattern for r in refs}
    assert "$('NodeName')" in patterns_used
    assert '$("NodeName")' in patterns_used
    assert '$node["NodeName"]' in patterns_used


def test_topological_sort_valid_ordering(fixtures_dir: Path) -> None:
    """Test topological sort valid ordering."""
    for name in ["simple_linear.json", "branching.json", "merge_workflow.json"]:
        graph, *_ = _build_graph(fixtures_dir, name)
        order = graph.topological_sort()
        order_index = {name: i for i, name in enumerate(order)}
        for edge in graph.edges:
            assert order_index[edge.source_node] < order_index[edge.target_node]


def test_successors_and_predecessors(fixtures_dir: Path) -> None:
    """Test successors and predecessors."""
    graph, *_ = _build_graph(fixtures_dir, "simple_linear.json")
    assert "HTTP Request" in graph.get_successors("Set")
    assert "Set" in graph.get_predecessors("HTTP Request")


def test_merge_roots(fixtures_dir: Path) -> None:
    """Test merge roots."""
    graph, *_ = _build_graph(fixtures_dir, "merge_workflow.json")
    roots = graph.get_roots()
    assert roots == ["Webhook"]


def _make_node(name: str) -> N8nNode:
    return N8nNode.model_validate(
        {
            "id": f"id-{name}",
            "name": name,
            "type": "n8n-nodes-base.set",
            "typeVersion": 1,
            "position": [0, 0],
            "parameters": {},
        }
    )


def test_cross_node_dot_notation() -> None:
    """Test cross node dot notation."""
    node = _make_node("Consumer")
    expressions = [(node, "param", "={{ $node.Producer.json.value }}")]
    refs = detect_cross_node_references(expressions)
    assert len(refs) == 1
    assert refs[0].source_node_name == "Producer"
    assert refs[0].reference_pattern == "$node.NodeName"
