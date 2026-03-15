"""Tests for the analyzer-to-translator adapter."""

from datetime import UTC, datetime

from phaeton_models.adapters.analyzer_to_translator import convert_report_to_analysis
from phaeton_models.analyzer import (
    ClassifiedExpression,
    ClassifiedNode,
    ConversionReport,
    ExpressionCategory,
    NodeCategory,
    PayloadWarning,
)
from phaeton_models.n8n_workflow import N8nNode
from phaeton_models.translator import (
    ExpressionCategory as SfnExpressionCategory,
)
from phaeton_models.translator import (
    NodeClassification,
    WorkflowAnalysis,
)


def _make_node(name: str, node_type: str = "n8n-nodes-base.set") -> N8nNode:
    return N8nNode(
        id=name,
        name=name,
        type=node_type,
        type_version=1,
        position=[0.0, 0.0],
    )


def _make_report(
    classified_nodes: list[ClassifiedNode] | None = None,
    classified_expressions: list[ClassifiedExpression] | None = None,
    payload_warnings: list[PayloadWarning] | None = None,
    unsupported_nodes: list[ClassifiedNode] | None = None,
    graph_metadata: dict | None = None,
    confidence_score: float = 85.0,
) -> ConversionReport:
    if classified_nodes is None:
        classified_nodes = []
    if classified_expressions is None:
        classified_expressions = []
    if payload_warnings is None:
        payload_warnings = []
    if unsupported_nodes is None:
        unsupported_nodes = []
    if graph_metadata is None:
        graph_metadata = {}

    return ConversionReport(
        source_workflow_name="Test Workflow",
        source_n8n_version="1.0.0",
        analyzer_version="0.1.0",
        timestamp=datetime.now(tz=UTC),
        total_nodes=len(classified_nodes),
        classification_summary={},
        classified_nodes=classified_nodes,
        expression_summary={},
        classified_expressions=classified_expressions,
        payload_warnings=payload_warnings,
        cross_node_references=[],
        unsupported_nodes=unsupported_nodes,
        trigger_nodes=[],
        sub_workflows_detected=[],
        required_picofun_clients=[],
        required_credentials=[],
        confidence_score=confidence_score,
        blocking_issues=[],
        graph_metadata=graph_metadata,
    )


def test_empty_report_converts() -> None:
    """An empty report produces a valid empty WorkflowAnalysis."""
    report = _make_report()
    result = convert_report_to_analysis(report)

    assert isinstance(result, WorkflowAnalysis)
    assert result.classified_nodes == []
    assert result.dependency_edges == []
    assert result.variables_needed == {}
    assert result.payload_warnings == []
    assert result.unsupported_nodes == []
    assert result.confidence_score == 85.0


def test_node_category_mapping() -> None:
    """All NodeCategory values map to matching NodeClassification values."""
    nodes = [
        ClassifiedNode(
            node=_make_node(cat.value),
            category=cat,
            translation_strategy="direct",
        )
        for cat in NodeCategory
    ]
    report = _make_report(classified_nodes=nodes)
    result = convert_report_to_analysis(report)

    for i, cat in enumerate(NodeCategory):
        assert result.classified_nodes[i].classification == NodeClassification(cat.value)


def test_expression_category_mapping() -> None:
    """Expression categories map correctly across the boundary."""
    expressions = [
        ClassifiedExpression(
            node_name="NodeA",
            parameter_path="params.val",
            raw_expression="{{ $json.name }}",
            category=ExpressionCategory.JSONATA_DIRECT,
        ),
        ClassifiedExpression(
            node_name="NodeA",
            parameter_path="params.ref",
            raw_expression="{{ $node.Other.json.id }}",
            category=ExpressionCategory.VARIABLE_REFERENCE,
            referenced_nodes=["Other"],
        ),
        ClassifiedExpression(
            node_name="NodeA",
            parameter_path="params.code",
            raw_expression="{{ $items.map(i => i.json) }}",
            category=ExpressionCategory.LAMBDA_REQUIRED,
        ),
    ]
    node = ClassifiedNode(
        node=_make_node("NodeA"),
        category=NodeCategory.AWS_NATIVE,
        translation_strategy="direct",
    )
    report = _make_report(classified_nodes=[node], classified_expressions=expressions)
    result = convert_report_to_analysis(report)

    exprs = result.classified_nodes[0].expressions
    assert len(exprs) == 3
    assert exprs[0].category == SfnExpressionCategory.JSONATA_DIRECT
    assert exprs[1].category == SfnExpressionCategory.REQUIRES_VARIABLES
    assert exprs[2].category == SfnExpressionCategory.REQUIRES_LAMBDA


def test_expression_field_mapping() -> None:
    """Expression fields are renamed correctly."""
    expr = ClassifiedExpression(
        node_name="NodeA",
        parameter_path="params.val",
        raw_expression="{{ $json.name }}",
        category=ExpressionCategory.JSONATA_DIRECT,
        referenced_nodes=["Upstream"],
    )
    node = ClassifiedNode(
        node=_make_node("NodeA"),
        category=NodeCategory.AWS_NATIVE,
        translation_strategy="direct",
    )
    report = _make_report(classified_nodes=[node], classified_expressions=[expr])
    result = convert_report_to_analysis(report)

    converted = result.classified_nodes[0].expressions[0]
    assert converted.original == "{{ $json.name }}"
    assert converted.node_references == ["Upstream"]
    assert converted.parameter_path == "params.val"


def test_expression_redistribution() -> None:
    """Expressions are assigned to the correct node by node_name."""
    node_a = ClassifiedNode(
        node=_make_node("A"),
        category=NodeCategory.AWS_NATIVE,
        translation_strategy="direct",
    )
    node_b = ClassifiedNode(
        node=_make_node("B"),
        category=NodeCategory.FLOW_CONTROL,
        translation_strategy="direct",
    )
    expressions = [
        ClassifiedExpression(
            node_name="A",
            parameter_path="p1",
            raw_expression="expr1",
            category=ExpressionCategory.JSONATA_DIRECT,
        ),
        ClassifiedExpression(
            node_name="B",
            parameter_path="p2",
            raw_expression="expr2",
            category=ExpressionCategory.LAMBDA_REQUIRED,
        ),
        ClassifiedExpression(
            node_name="A",
            parameter_path="p3",
            raw_expression="expr3",
            category=ExpressionCategory.VARIABLE_REFERENCE,
        ),
    ]
    report = _make_report(
        classified_nodes=[node_a, node_b],
        classified_expressions=expressions,
    )
    result = convert_report_to_analysis(report)

    # Node A should have 2 expressions, Node B should have 1
    assert len(result.classified_nodes[0].expressions) == 2
    assert result.classified_nodes[0].expressions[0].original == "expr1"
    assert result.classified_nodes[0].expressions[1].original == "expr3"
    assert len(result.classified_nodes[1].expressions) == 1
    assert result.classified_nodes[1].expressions[0].original == "expr2"


def test_dependency_edges_from_graph_metadata() -> None:
    """Edges in graph_metadata are parsed into DependencyEdge objects."""
    graph_metadata = {
        "root_nodes": ["Trigger"],
        "leaf_nodes": ["End"],
        "edges": [
            {
                "source_node": "Trigger",
                "target_node": "Process",
                "edge_type": "connection",
                "output_index": 0,
            },
            {
                "source_node": "Process",
                "target_node": "End",
                "edge_type": "data_reference",
            },
        ],
    }
    report = _make_report(graph_metadata=graph_metadata)
    result = convert_report_to_analysis(report)

    assert len(result.dependency_edges) == 2
    assert result.dependency_edges[0].from_node == "Trigger"
    assert result.dependency_edges[0].to_node == "Process"
    assert result.dependency_edges[0].edge_type == "CONNECTION"
    assert result.dependency_edges[0].output_index == 0
    assert result.dependency_edges[1].from_node == "Process"
    assert result.dependency_edges[1].to_node == "End"
    assert result.dependency_edges[1].edge_type == "DATA_REFERENCE"
    assert result.dependency_edges[1].output_index is None


def test_dependency_edges_with_from_to_keys() -> None:
    """Edges using from_node/to_node keys are parsed correctly."""
    graph_metadata = {
        "edges": [
            {
                "from_node": "A",
                "to_node": "B",
                "edge_type": "connection",
            },
        ],
    }
    report = _make_report(graph_metadata=graph_metadata)
    result = convert_report_to_analysis(report)

    assert len(result.dependency_edges) == 1
    assert result.dependency_edges[0].from_node == "A"
    assert result.dependency_edges[0].to_node == "B"


def test_empty_graph_metadata() -> None:
    """Empty graph_metadata produces no dependency edges."""
    report = _make_report(graph_metadata={})
    result = convert_report_to_analysis(report)
    assert result.dependency_edges == []


def test_graph_metadata_without_edges_key() -> None:
    """Graph metadata with only summary data produces empty edges."""
    graph_metadata = {
        "root_nodes": ["Trigger"],
        "leaf_nodes": ["End"],
        "merge_points": [],
        "has_cycles": False,
    }
    report = _make_report(graph_metadata=graph_metadata)
    result = convert_report_to_analysis(report)
    assert result.dependency_edges == []


def test_payload_warnings_to_strings() -> None:
    """PayloadWarning objects are converted to descriptive strings."""
    warnings = [
        PayloadWarning(
            node_name="BigNode",
            warning_type="SIZE_LIMIT",
            description="Payload exceeds 256KB limit",
            severity="high",
            recommendation="Split into smaller payloads",
        ),
        PayloadWarning(
            node_name="SmallNode",
            warning_type="NESTED_DATA",
            description="Deeply nested data structure",
            severity="low",
            recommendation="Flatten data",
        ),
    ]
    report = _make_report(payload_warnings=warnings)
    result = convert_report_to_analysis(report)

    assert len(result.payload_warnings) == 2
    assert result.payload_warnings[0] == "BigNode: Payload exceeds 256KB limit"
    assert result.payload_warnings[1] == "SmallNode: Deeply nested data structure"


def test_unsupported_nodes_to_strings() -> None:
    """Unsupported ClassifiedNode objects are converted to node name strings."""
    unsupported = [
        ClassifiedNode(
            node=_make_node("CustomNode", "community.custom"),
            category=NodeCategory.UNSUPPORTED,
            translation_strategy="none",
        ),
        ClassifiedNode(
            node=_make_node("LegacyNode", "community.legacy"),
            category=NodeCategory.UNSUPPORTED,
            translation_strategy="none",
        ),
    ]
    report = _make_report(unsupported_nodes=unsupported)
    result = convert_report_to_analysis(report)

    assert result.unsupported_nodes == ["CustomNode", "LegacyNode"]


def test_confidence_score_carried_over() -> None:
    """Confidence score is passed through unchanged."""
    report = _make_report(confidence_score=92.5)
    result = convert_report_to_analysis(report)
    assert result.confidence_score == 92.5


def test_no_unsupported_nodes() -> None:
    """No unsupported nodes results in an empty list."""
    report = _make_report(unsupported_nodes=[])
    result = convert_report_to_analysis(report)
    assert result.unsupported_nodes == []


def test_no_expressions() -> None:
    """Nodes with no matching expressions get empty expression lists."""
    node = ClassifiedNode(
        node=_make_node("Lonely"),
        category=NodeCategory.FLOW_CONTROL,
        translation_strategy="direct",
    )
    report = _make_report(classified_nodes=[node], classified_expressions=[])
    result = convert_report_to_analysis(report)

    assert result.classified_nodes[0].expressions == []


def test_round_trip_pydantic_validation() -> None:
    """A fully populated report converts to a valid WorkflowAnalysis."""
    nodes = [
        ClassifiedNode(
            node=_make_node("Trigger", "n8n-nodes-base.scheduleTrigger"),
            category=NodeCategory.TRIGGER,
            translation_strategy="eventbridge",
            notes="Schedule trigger",
        ),
        ClassifiedNode(
            node=_make_node("Process", "n8n-nodes-base.set"),
            category=NodeCategory.AWS_NATIVE,
            translation_strategy="pass_state",
        ),
        ClassifiedNode(
            node=_make_node("Code", "n8n-nodes-base.code"),
            category=NodeCategory.CODE_JS,
            translation_strategy="lambda",
        ),
    ]
    expressions = [
        ClassifiedExpression(
            node_name="Process",
            parameter_path="params.value",
            raw_expression="{{ $json.name }}",
            category=ExpressionCategory.JSONATA_DIRECT,
            referenced_nodes=[],
        ),
        ClassifiedExpression(
            node_name="Process",
            parameter_path="params.id",
            raw_expression="{{ $node.Trigger.json.id }}",
            category=ExpressionCategory.VARIABLE_REFERENCE,
            referenced_nodes=["Trigger"],
        ),
        ClassifiedExpression(
            node_name="Code",
            parameter_path="params.code",
            raw_expression="{{ $items.map(i => i.json) }}",
            category=ExpressionCategory.LAMBDA_REQUIRED,
            referenced_nodes=["Process"],
        ),
    ]
    warnings = [
        PayloadWarning(
            node_name="Process",
            warning_type="SIZE",
            description="Large payload",
            severity="medium",
            recommendation="Reduce size",
        ),
    ]
    unsupported = [
        ClassifiedNode(
            node=_make_node("Bad", "community.bad"),
            category=NodeCategory.UNSUPPORTED,
            translation_strategy="none",
        ),
    ]
    graph_metadata = {
        "root_nodes": ["Trigger"],
        "leaf_nodes": ["Code"],
        "edges": [
            {
                "source_node": "Trigger",
                "target_node": "Process",
                "edge_type": "connection",
                "output_index": 0,
            },
            {
                "source_node": "Process",
                "target_node": "Code",
                "edge_type": "connection",
            },
        ],
    }

    report = _make_report(
        classified_nodes=[*nodes, unsupported[0]],
        classified_expressions=expressions,
        payload_warnings=warnings,
        unsupported_nodes=unsupported,
        graph_metadata=graph_metadata,
        confidence_score=73.5,
    )
    result = convert_report_to_analysis(report)

    # Validate result is a proper WorkflowAnalysis (Pydantic validation)
    validated = WorkflowAnalysis.model_validate(result.model_dump())
    assert validated.confidence_score == 73.5
    assert len(validated.classified_nodes) == 4
    assert len(validated.dependency_edges) == 2
    assert len(validated.payload_warnings) == 1
    assert validated.unsupported_nodes == ["Bad"]

    # Verify expression redistribution
    process_node = next(
        n for n in validated.classified_nodes if n.node.name == "Process"
    )
    assert len(process_node.expressions) == 2
    code_node = next(n for n in validated.classified_nodes if n.node.name == "Code")
    assert len(code_node.expressions) == 1
    trigger_node = next(
        n for n in validated.classified_nodes if n.node.name == "Trigger"
    )
    assert len(trigger_node.expressions) == 0
