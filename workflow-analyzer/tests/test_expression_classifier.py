"""Tests for expression classification."""

from workflow_analyzer.expressions.expression_classifier import ExpressionClassifier
from workflow_analyzer.models.expression import ExpressionCategory


def test_category_a_simple_property() -> None:
    """Test category A simple property."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ $json.name }}")
    assert result.category == ExpressionCategory.JSONATA_DIRECT
    assert result.jsonata_preview is not None
    assert "$states.input.name" in result.jsonata_preview


def test_category_a_uppercase() -> None:
    """Test category A uppercase."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ $json.name.toUpperCase() }}")
    assert result.category == ExpressionCategory.JSONATA_DIRECT
    assert result.jsonata_preview is not None
    assert "$uppercase" in result.jsonata_preview


def test_category_a_lowercase() -> None:
    """Test category A lowercase."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ $json.value.toLowerCase() }}")
    assert result.category == ExpressionCategory.JSONATA_DIRECT
    assert result.jsonata_preview is not None
    assert "$lowercase" in result.jsonata_preview


def test_category_a_math_round() -> None:
    """Test category A math round."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ Math.round($json.price) }}")
    assert result.category == ExpressionCategory.JSONATA_DIRECT
    assert result.jsonata_preview is not None
    assert "$round" in result.jsonata_preview


def test_category_a_ternary() -> None:
    """Test category A ternary."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ $json.active ? 'yes' : 'no' }}")
    assert result.category == ExpressionCategory.JSONATA_DIRECT


def test_category_a_no_preview_for_unknown_pattern() -> None:
    """Test category A no preview for unknown pattern."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ 1 + 2 }}")
    assert result.category == ExpressionCategory.JSONATA_DIRECT
    assert result.jsonata_preview is None


def test_category_b_single_quote_ref() -> None:
    """Test category B single quote ref."""
    c = ExpressionClassifier()
    result = c.classify("Node2", "param", "={{ $('Node1').first().json.value }}")
    assert result.category == ExpressionCategory.VARIABLE_REFERENCE
    assert "Node1" in result.referenced_nodes


def test_category_b_double_quote_ref() -> None:
    """Test category B double quote ref."""
    c = ExpressionClassifier()
    result = c.classify("Node2", "param", '={{ $("Node1").first().json.value }}')
    assert result.category == ExpressionCategory.VARIABLE_REFERENCE
    assert "Node1" in result.referenced_nodes


def test_category_b_execution_ref() -> None:
    """Test category B execution ref."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ $execution.id }}")
    assert result.category == ExpressionCategory.VARIABLE_REFERENCE
    assert "$execution reference" in result.reason


def test_category_b_multiple_refs() -> None:
    """Test category B multiple refs."""
    c = ExpressionClassifier()
    result = c.classify(
        "Node3", "param", "={{ $('Node1').json.a + $('Node2').json.b }}"
    )
    assert result.category == ExpressionCategory.VARIABLE_REFERENCE
    assert "Node1" in result.referenced_nodes
    assert "Node2" in result.referenced_nodes


def test_category_c_require() -> None:
    """Test category C require."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ require('lodash').get($json, 'a.b') }}")
    assert result.category == ExpressionCategory.LAMBDA_REQUIRED
    assert "require" in result.reason.lower()


def test_category_c_env() -> None:
    """Test category C env."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ $env.API_KEY }}")
    assert result.category == ExpressionCategory.LAMBDA_REQUIRED
    assert "environment" in result.reason.lower()


def test_category_c_iife() -> None:
    """Test category C IIFE."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ (function(){ return 1; })() }}")
    assert result.category == ExpressionCategory.LAMBDA_REQUIRED
    assert "IIFE" in result.reason


def test_category_c_await() -> None:
    """Test category C await."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ await fetch('url') }}")
    assert result.category == ExpressionCategory.LAMBDA_REQUIRED
    assert "async" in result.reason.lower()


def test_category_c_luxon() -> None:
    """Test category C Luxon."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ DateTime.now().toISO() }}")
    assert result.category == ExpressionCategory.LAMBDA_REQUIRED
    assert "DateTime" in result.reason


def test_category_c_loop() -> None:
    """Test category C loop."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ for (let i=0; i<10; i++) {} }}")
    assert result.category == ExpressionCategory.LAMBDA_REQUIRED
    assert "loop" in result.reason.lower()


def test_mixed_a_and_b_returns_b() -> None:
    """Test mixed A and B returns B."""
    c = ExpressionClassifier()
    result = c.classify(
        "Node2", "param", "={{ $json.value + $('Node1').first().json.extra }}"
    )
    assert result.category == ExpressionCategory.VARIABLE_REFERENCE


def test_mixed_a_and_c_returns_c() -> None:
    """Test mixed A and C returns C."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{ $json.value + require('x').y }}")
    assert result.category == ExpressionCategory.LAMBDA_REQUIRED


def test_mixed_b_and_c_returns_c() -> None:
    """Test mixed B and C returns C."""
    c = ExpressionClassifier()
    result = c.classify("Node2", "param", "={{ $('Node1').json.v + require('x').y }}")
    assert result.category == ExpressionCategory.LAMBDA_REQUIRED
    assert len(result.referenced_nodes) > 0


def test_empty_expression() -> None:
    """Test empty expression."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "=")
    assert result.category == ExpressionCategory.JSONATA_DIRECT


def test_whitespace_expression() -> None:
    """Test whitespace expression."""
    c = ExpressionClassifier()
    result = c.classify("Node1", "param", "={{   }}")
    assert result.category == ExpressionCategory.JSONATA_DIRECT


def test_classify_all() -> None:
    """Test classify all."""
    from workflow_analyzer.models.n8n_workflow import N8nNode

    c = ExpressionClassifier()
    node = N8nNode.model_validate(
        {
            "id": "1",
            "name": "TestNode",
            "type": "n8n-nodes-base.set",
            "typeVersion": 1,
            "position": [0, 0],
            "parameters": {},
        }
    )
    expressions = [
        (node, "p1", "={{ $json.x }}"),
        (node, "p2", "={{ $('Other').json.y }}"),
        (node, "p3", "={{ require('fs').readFileSync('x') }}"),
    ]
    results = c.classify_all(expressions)
    assert len(results) == 3
    assert results[0].category == ExpressionCategory.JSONATA_DIRECT
    assert results[1].category == ExpressionCategory.VARIABLE_REFERENCE
    assert results[2].category == ExpressionCategory.LAMBDA_REQUIRED
