"""Tests for node classification."""

from pathlib import Path

from phaeton_models.analyzer import NodeCategory

from workflow_analyzer.classifier.node_classifier import NodeClassifier
from workflow_analyzer.models.n8n_workflow import N8nNode
from workflow_analyzer.parser.workflow_parser import WorkflowParser


def _make_node(
    node_type: str,
    name: str = "TestNode",
    parameters: dict | None = None,
) -> N8nNode:
    return N8nNode.model_validate(
        {
            "id": "test-id",
            "name": name,
            "type": node_type,
            "typeVersion": 1,
            "position": [0, 0],
            "parameters": parameters or {},
        }
    )


def test_classify_flow_control() -> None:
    """Test classify flow control."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.if")
    result = classifier.classify(node)
    assert result.category == NodeCategory.FLOW_CONTROL


def test_classify_trigger() -> None:
    """Test classify trigger."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.manualTrigger")
    result = classifier.classify(node)
    assert result.category == NodeCategory.TRIGGER


def test_classify_trigger_suffix() -> None:
    """Test classify trigger suffix."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.someCustomTrigger")
    result = classifier.classify(node)
    assert result.category == NodeCategory.TRIGGER


def test_classify_aws_native() -> None:
    """Test classify AWS native."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.awsS3")
    result = classifier.classify(node)
    assert result.category == NodeCategory.AWS_NATIVE


def test_classify_email_send_as_aws_native() -> None:
    """Test classify email send as AWS native."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.emailSend")
    result = classifier.classify(node)
    assert result.category == NodeCategory.AWS_NATIVE


def test_classify_code_js_default() -> None:
    """Test classify code JS default."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.code")
    result = classifier.classify(node)
    assert result.category == NodeCategory.CODE_JS


def test_classify_code_js_explicit() -> None:
    """Test classify code JS explicit."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.code", parameters={"language": "javaScript"})
    result = classifier.classify(node)
    assert result.category == NodeCategory.CODE_JS


def test_classify_code_python() -> None:
    """Test classify code Python."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.code", parameters={"language": "python"})
    result = classifier.classify(node)
    assert result.category == NodeCategory.CODE_PYTHON


def test_classify_http_request() -> None:
    """Test classify HTTP request."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.httpRequest")
    result = classifier.classify(node)
    assert result.category == NodeCategory.PICOFUN_API


def test_classify_picofun_base_node() -> None:
    """Test classify PicoFun base node."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.slack")
    result = classifier.classify(node)
    assert result.category == NodeCategory.PICOFUN_API


def test_classify_unsupported() -> None:
    """Test classify unsupported."""
    classifier = NodeClassifier()
    node = _make_node("community-nodes.someNode")
    result = classifier.classify(node)
    assert result.category == NodeCategory.UNSUPPORTED
    assert result.notes is not None
    assert "not in the supported node registry" in result.notes


def test_classify_google_sheets_unsupported() -> None:
    """Test classify Google Sheets unsupported."""
    classifier = NodeClassifier()
    node = _make_node("n8n-nodes-base.googleSheets")
    result = classifier.classify(node)
    # Google Sheets is an n8n-nodes-base node, so it classifies as PICOFUN_API
    # (not UNSUPPORTED) because it has an API that PicoFun can potentially wrap
    assert result.category == NodeCategory.PICOFUN_API


def test_classify_all(fixtures_dir: Path) -> None:
    """Test classify all."""
    parser = WorkflowParser()
    wf = parser.parse_file(fixtures_dir / "simple_linear.json")
    classifier = NodeClassifier()
    classified = classifier.classify_all(wf.nodes)
    assert len(classified) == 4
    categories = [c.category for c in classified]
    assert NodeCategory.TRIGGER in categories
    assert NodeCategory.FLOW_CONTROL in categories
    assert NodeCategory.PICOFUN_API in categories


def test_classify_all_no_unclassified(fixtures_dir: Path) -> None:
    """Test classify all no unclassified."""
    parser = WorkflowParser()
    for name in ["simple_linear.json", "branching.json", "merge_workflow.json"]:
        wf = parser.parse_file(fixtures_dir / name)
        classifier = NodeClassifier()
        classified = classifier.classify_all(wf.nodes)
        assert len(classified) == len(wf.nodes)
        for c in classified:
            assert c.category is not None
            assert c.translation_strategy


def test_classify_branching_counts(fixtures_dir: Path) -> None:
    """Test classify branching counts."""
    parser = WorkflowParser()
    wf = parser.parse_file(fixtures_dir / "branching.json")
    classifier = NodeClassifier()
    classified = classifier.classify_all(wf.nodes)
    cat_counts: dict[NodeCategory, int] = {}
    for c in classified:
        cat_counts[c.category] = cat_counts.get(c.category, 0) + 1
    assert cat_counts[NodeCategory.TRIGGER] == 1
    assert cat_counts[NodeCategory.FLOW_CONTROL] == 2  # IF + Set
    assert cat_counts[NodeCategory.PICOFUN_API] == 1  # HTTP Request
    assert cat_counts[NodeCategory.AWS_NATIVE] == 1  # SES
