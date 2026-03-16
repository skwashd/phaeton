"""Tests for the priority module."""

from datetime import UTC, datetime

from n8n_release_parser.models import (
    NodeApiMapping,
    NodeCatalog,
    NodeClassification,
    NodeParameter,
    NodeTypeEntry,
)
from n8n_release_parser.priority import (
    CORE_FLOW_CONTROL_NODES,
    TOP_50_NODES,
    classify_node,
    is_priority_node,
    priority_coverage_report,
)


def _make_node(
    node_type: str,
    *,
    group: list[str] | None = None,
    parameters: list[NodeParameter] | None = None,
    request_defaults: dict | None = None,
) -> NodeTypeEntry:
    """Build a minimal NodeTypeEntry for testing."""
    return NodeTypeEntry(
        node_type=node_type,
        type_version=1,
        display_name=node_type,
        group=group or [],
        parameters=parameters or [],
        request_defaults=request_defaults,
    )


def _make_mapping(node_type: str) -> NodeApiMapping:
    """Build a minimal NodeApiMapping for testing."""
    return NodeApiMapping(
        node_type=node_type,
        type_version=1,
        api_spec="some_spec.yaml",
        spec_format="openapi3",
    )


class TestClassifyNode:
    """Tests for ClassifyNode."""

    def test_classify_aws_native_node(self) -> None:
        """Test classify aws native node."""
        node = _make_node("n8n-nodes-base.awsS3")
        result = classify_node(node, None)
        assert result == NodeClassification.AWS_NATIVE

    def test_classify_email_send_as_aws_native(self) -> None:
        """Test classify email send as aws native."""
        node = _make_node("n8n-nodes-base.emailSend")
        result = classify_node(node, None)
        assert result == NodeClassification.AWS_NATIVE

    def test_classify_flow_control_node(self) -> None:
        """Test classify flow control node."""
        node = _make_node("n8n-nodes-base.if")
        result = classify_node(node, None)
        assert result == NodeClassification.FLOW_CONTROL

    def test_classify_trigger_node(self) -> None:
        """Test classify trigger node."""
        node = _make_node("n8n-nodes-base.scheduleTrigger")
        result = classify_node(node, None)
        assert result == NodeClassification.TRIGGER

    def test_classify_trigger_node_via_group(self) -> None:
        """Test classify trigger node via group."""
        node = _make_node("n8n-nodes-base.webhook", group=["trigger"])
        result = classify_node(node, None)
        assert result == NodeClassification.TRIGGER

    def test_classify_code_js_node(self) -> None:
        """Test classify code js node."""
        lang_param = NodeParameter(
            name="language",
            display_name="Language",
            type="options",
            default="javaScript",
        )
        node = _make_node("n8n-nodes-base.code", parameters=[lang_param])
        result = classify_node(node, None)
        assert result == NodeClassification.CODE_JS

    def test_classify_code_js_node_no_language_param(self) -> None:
        """Test classify code js node no language param."""
        node = _make_node("n8n-nodes-base.code")
        result = classify_node(node, None)
        assert result == NodeClassification.CODE_JS

    def test_classify_code_python_node(self) -> None:
        """Test classify code python node."""
        lang_param = NodeParameter(
            name="language",
            display_name="Language",
            type="options",
            default="python",
        )
        node = _make_node("n8n-nodes-base.code", parameters=[lang_param])
        result = classify_node(node, None)
        assert result == NodeClassification.CODE_PYTHON

    def test_classify_picofun_api_node(self) -> None:
        """Test classify picofun api node."""
        node = _make_node("n8n-nodes-base.slack")
        mapping = _make_mapping("n8n-nodes-base.slack")
        result = classify_node(node, mapping)
        assert result == NodeClassification.PICOFUN_API

    def test_classify_graphql_node(self) -> None:
        """Test classify graphql node."""
        node = _make_node(
            "n8n-nodes-base.graphqlCustom",
            request_defaults={"baseURL": "https://api.example.com/graphql"},
        )
        result = classify_node(node, None)
        assert result == NodeClassification.GRAPHQL_API

    def test_classify_unsupported_node(self) -> None:
        """Test classify unsupported node."""
        node = _make_node("n8n-nodes-base.someObscureNode")
        result = classify_node(node, None)
        assert result == NodeClassification.UNSUPPORTED


class TestIsPriorityNode:
    """Tests for IsPriorityNode."""

    def test_is_priority_node_true(self) -> None:
        """Test is priority node true."""
        assert is_priority_node("n8n-nodes-base.if") is True
        assert is_priority_node("n8n-nodes-base.awsS3") is True
        assert is_priority_node("n8n-nodes-base.slack") is True

    def test_is_priority_node_false(self) -> None:
        """Test is priority node false."""
        assert is_priority_node("n8n-nodes-base.someObscureNode") is False
        assert is_priority_node("totally.unknown") is False


class TestPriorityCoverageReport:
    """Tests for PriorityCoverageReport."""

    def test_priority_coverage_report(self) -> None:
        """Test priority coverage report."""
        entries = [
            _make_node("n8n-nodes-base.if"),
            _make_node("n8n-nodes-base.awsS3"),
            _make_node("n8n-nodes-base.slack"),
            _make_node("n8n-nodes-base.someObscureNode"),
        ]
        catalog = NodeCatalog(
            n8n_version="1.0.0",
            release_date=datetime(2024, 1, 1, tzinfo=UTC),
            entries=entries,
        )
        mappings = [_make_mapping("n8n-nodes-base.if")]

        report = priority_coverage_report(catalog, mappings)

        assert report["total_priority_nodes"] == 3
        assert report["mapped_priority_nodes"] == 1
        missing = report["missing_mappings"]
        assert isinstance(missing, list)
        assert "n8n-nodes-base.awsS3" in missing
        assert "n8n-nodes-base.slack" in missing
        assert "n8n-nodes-base.someObscureNode" not in missing

        breakdown = report["breakdown"]
        assert isinstance(breakdown, dict)
        assert breakdown["core_flow_control"] == 1  # type: ignore[invalid-argument-type]
        assert breakdown["aws_service"] == 1  # type: ignore[invalid-argument-type]
        assert breakdown["top_50"] == 2  # if + slack  # type: ignore[invalid-argument-type]


class TestRegistryCompleteness:
    """Tests for RegistryCompleteness."""

    def test_core_flow_control_nodes_completeness(self) -> None:
        """Test core flow control nodes completeness."""
        expected = {
            "n8n-nodes-base.if",
            "n8n-nodes-base.switch",
            "n8n-nodes-base.merge",
            "n8n-nodes-base.splitInBatches",
            "n8n-nodes-base.set",
            "n8n-nodes-base.code",
            "n8n-nodes-base.function",
            "n8n-nodes-base.noOp",
            "n8n-nodes-base.wait",
            "n8n-nodes-base.httpRequest",
            "n8n-nodes-base.webhook",
            "n8n-nodes-base.scheduleTrigger",
            "n8n-nodes-base.manualTrigger",
            "n8n-nodes-base.executeWorkflow",
            "n8n-nodes-base.respondToWebhook",
            "n8n-nodes-base.errorTrigger",
        }
        assert expected == CORE_FLOW_CONTROL_NODES

    def test_top_50_nodes_count(self) -> None:
        """Test top 50 nodes count."""
        assert len(TOP_50_NODES) == 50
