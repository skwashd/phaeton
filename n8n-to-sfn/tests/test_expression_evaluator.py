"""Tests for the REQUIRES_LAMBDA expression evaluator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from phaeton_models.translator import (
    ClassifiedExpression,
    ClassifiedNode,
    ExpressionCategory,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.asl import StateMachine
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import LambdaRuntime, TranslationContext
from n8n_to_sfn.translators.expression_evaluator import (
    ExpressionEvalResult,
    _validate_expression,
    evaluate_lambda_expressions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(
    name: str,
    expressions: list[ClassifiedExpression] | None = None,
) -> ClassifiedNode:
    """Create a classified node with the given expressions."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type="n8n-nodes-base.set",
            type_version=1,
            position=[0, 0],
            parameters={},
        ),
        classification=NodeClassification.FLOW_CONTROL,
        expressions=expressions or [],
    )


def _lambda_expr(
    original: str,
    node_references: list[str] | None = None,
    parameter_path: str = "",
) -> ClassifiedExpression:
    """Create a REQUIRES_LAMBDA classified expression."""
    return ClassifiedExpression(
        original=original,
        category=ExpressionCategory.REQUIRES_LAMBDA,
        node_references=node_references or [],
        parameter_path=parameter_path,
    )


def _jsonata_expr(original: str) -> ClassifiedExpression:
    """Create a JSONATA_DIRECT classified expression."""
    return ClassifiedExpression(
        original=original,
        category=ExpressionCategory.JSONATA_DIRECT,
    )


def _context() -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[])
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEvaluateLambdaExpressions:
    """Tests for evaluate_lambda_expressions."""

    def test_no_lambda_expressions_returns_empty(self) -> None:
        """Test that nodes with no REQUIRES_LAMBDA expressions return empty."""
        node = _node("NodeA", [_jsonata_expr("{{ $json.field }}")])
        result = evaluate_lambda_expressions(node, _context())

        assert isinstance(result, ExpressionEvalResult)
        assert result.states == {}
        assert result.lambda_artifacts == []
        assert result.warnings == []
        assert result.eval_state_names == []

    def test_no_expressions_returns_empty(self) -> None:
        """Test that nodes with no expressions at all return empty."""
        node = _node("NodeA")
        result = evaluate_lambda_expressions(node, _context())

        assert result.states == {}
        assert result.lambda_artifacts == []

    def test_single_lambda_expression_produces_state_and_artifact(self) -> None:
        """Test that a single REQUIRES_LAMBDA expression produces one state and artifact."""
        expr = _lambda_expr('={{ Math.round($json.value * 100) / 100 }}')
        node = _node("CalcNode", [expr])
        result = evaluate_lambda_expressions(node, _context())

        assert len(result.states) == 1
        assert len(result.lambda_artifacts) == 1
        assert len(result.eval_state_names) == 1

        state_name = result.eval_state_names[0]
        assert state_name == "CalcNode_ExprEval"
        assert state_name in result.states

        state = result.states[state_name]
        assert state.resource == "arn:aws:states:::lambda:invoke"

        artifact = result.lambda_artifacts[0]
        assert artifact.runtime == LambdaRuntime.NODEJS
        assert "luxon" in artifact.dependencies
        assert "Math.round" in artifact.handler_code

    def test_multiple_lambda_expressions_produce_indexed_states(self) -> None:
        """Test that multiple REQUIRES_LAMBDA expressions produce indexed states."""
        expr1 = _lambda_expr('={{ Math.round($json.x) }}')
        expr2 = _lambda_expr('={{ DateTime.now().toISO() }}')
        node = _node("MultiExpr", [expr1, expr2])
        result = evaluate_lambda_expressions(node, _context())

        assert len(result.states) == 2
        assert len(result.lambda_artifacts) == 2
        assert result.eval_state_names == [
            "MultiExpr_ExprEval_0",
            "MultiExpr_ExprEval_1",
        ]

    def test_multi_node_references_in_expression(self) -> None:
        """Test that multi-node references are reflected in upstream bindings."""
        expr = _lambda_expr(
            '={{ $node["Node A"].data.field + $node["Node B"].data.field }}',
            node_references=["Node A", "Node B"],
        )
        node = _node("MergeCalc", [expr])
        result = evaluate_lambda_expressions(node, _context())

        handler = result.lambda_artifacts[0].handler_code
        assert '$node["Node A"]' in handler
        assert '$node["Node B"]' in handler
        assert "$node = {};" in handler

    def test_node_references_extracted_from_expression(self) -> None:
        """Test that node refs are extracted from expression text when not in metadata."""
        expr = _lambda_expr(
            '={{ $node["Lookup"].json.id }}',
            node_references=[],
        )
        node = _node("UseRef", [expr])
        result = evaluate_lambda_expressions(node, _context())

        handler = result.lambda_artifacts[0].handler_code
        assert '$node["Lookup"]' in handler

    def test_javascript_builtins_in_handler(self) -> None:
        """Test JavaScript built-in methods are preserved in handler code."""
        expr = _lambda_expr('={{ Math.round($json.value * 100) / 100 }}')
        node = _node("MathNode", [expr])
        result = evaluate_lambda_expressions(node, _context())

        handler = result.lambda_artifacts[0].handler_code
        assert "Math.round" in handler
        assert "expressionResult" in handler

    def test_string_operation_expression(self) -> None:
        """Test string operation expressions are handled."""
        expr = _lambda_expr('={{ $json.name.toUpperCase() }}')
        node = _node("StrNode", [expr])
        result = evaluate_lambda_expressions(node, _context())

        handler = result.lambda_artifacts[0].handler_code
        assert "toUpperCase" in handler

    def test_date_expression(self) -> None:
        """Test DateTime/luxon expressions include luxon import."""
        expr = _lambda_expr('={{ DateTime.now().toISO() }}')
        node = _node("DateNode", [expr])
        result = evaluate_lambda_expressions(node, _context())

        handler = result.lambda_artifacts[0].handler_code
        assert "require('luxon')" in handler
        assert "DateTime.now()" in handler

    def test_conditional_expression(self) -> None:
        """Test conditional (ternary) expressions are handled."""
        expr = _lambda_expr(
            '={{ $json.status === "active" ? "yes" : "no" }}'
        )
        node = _node("CondNode", [expr])
        result = evaluate_lambda_expressions(node, _context())

        handler = result.lambda_artifacts[0].handler_code
        assert '"active"' in handler
        assert '"yes"' in handler
        assert '"no"' in handler

    def test_warnings_generated_for_each_expression(self) -> None:
        """Test that a warning is emitted for each REQUIRES_LAMBDA expression."""
        expr = _lambda_expr('={{ $json.x }}')
        node = _node("WarnNode", [expr])
        result = evaluate_lambda_expressions(node, _context())

        assert len(result.warnings) == 1
        assert "WarnNode" in result.warnings[0]
        assert "Lambda evaluation" in result.warnings[0]

    def test_function_name_sanitized(self) -> None:
        """Test that function names are sanitized from node names."""
        expr = _lambda_expr('={{ $json.x }}')
        node = _node("My Cool Node!", [expr])
        result = evaluate_lambda_expressions(node, _context())

        artifact = result.lambda_artifacts[0]
        assert artifact.function_name == "expr_eval_my_cool_node_"
        assert " " not in artifact.function_name
        assert "!" not in artifact.function_name

    def test_expression_wrapper_stripped(self) -> None:
        """Test that n8n expression wrappers are properly stripped."""
        expr = _lambda_expr('={{ Math.floor($json.val) }}')
        node = _node("StripNode", [expr])
        result = evaluate_lambda_expressions(node, _context())

        handler = result.lambda_artifacts[0].handler_code
        assert "Math.floor($json.val)" in handler
        assert "{{" not in handler


class TestAIAgentIntegration:
    """Tests for AI agent integration in expression evaluation."""

    def test_ai_agent_used_when_available(self) -> None:
        """Test that the AI agent is called when provided."""
        ai_agent = MagicMock()
        ai_agent.translate_expression.return_value = "Math.round(event.value)"

        expr = _lambda_expr('={{ Math.round($json.value) }}')
        node = _node("AINode", [expr])
        result = evaluate_lambda_expressions(node, _context(), ai_agent=ai_agent)

        ai_agent.translate_expression.assert_called_once()
        handler = result.lambda_artifacts[0].handler_code
        assert "Math.round(event.value)" in handler

    def test_ai_agent_fallback_on_same_return(self) -> None:
        """Test fallback when AI agent returns the original expression."""
        ai_agent = MagicMock()
        ai_agent.translate_expression.return_value = '={{ Math.round($json.value) }}'

        expr = _lambda_expr('={{ Math.round($json.value) }}')
        node = _node("FallbackNode", [expr])
        result = evaluate_lambda_expressions(node, _context(), ai_agent=ai_agent)

        handler = result.lambda_artifacts[0].handler_code
        assert "Math.round($json.value)" in handler

    def test_ai_agent_fallback_on_exception(self) -> None:
        """Test fallback when AI agent raises an exception."""
        ai_agent = MagicMock()
        ai_agent.translate_expression.side_effect = RuntimeError("Agent down")

        expr = _lambda_expr('={{ $json.name.toUpperCase() }}')
        node = _node("ErrorNode", [expr])
        result = evaluate_lambda_expressions(node, _context(), ai_agent=ai_agent)

        assert len(result.lambda_artifacts) == 1
        handler = result.lambda_artifacts[0].handler_code
        assert "toUpperCase" in handler

    def test_ai_agent_fallback_on_empty_return(self) -> None:
        """Test fallback when AI agent returns empty string."""
        ai_agent = MagicMock()
        ai_agent.translate_expression.return_value = ""

        expr = _lambda_expr('={{ $json.x }}')
        node = _node("EmptyNode", [expr])
        result = evaluate_lambda_expressions(node, _context(), ai_agent=ai_agent)

        assert len(result.lambda_artifacts) == 1
        handler = result.lambda_artifacts[0].handler_code
        assert "$json.x" in handler

    def test_no_ai_agent_uses_fallback(self) -> None:
        """Test that no AI agent falls back to direct evaluation."""
        expr = _lambda_expr('={{ $json.x }}')
        node = _node("NoAgent", [expr])
        result = evaluate_lambda_expressions(node, _context(), ai_agent=None)

        assert len(result.lambda_artifacts) == 1
        handler = result.lambda_artifacts[0].handler_code
        assert "$json.x" in handler


class TestEngineExpressionIntegration:
    """Tests for expression evaluator integration in the translation engine."""

    def test_engine_processes_lambda_expressions(self) -> None:
        """Test that the engine processes REQUIRES_LAMBDA expressions on nodes."""
        from n8n_to_sfn.engine import TranslationEngine
        from n8n_to_sfn.models.asl import PassState
        from n8n_to_sfn.translators.base import BaseTranslator, TranslationResult

        class StubTranslator(BaseTranslator):
            """Stub translator that produces a PassState for any node."""

            def can_translate(self, node: ClassifiedNode) -> bool:
                """Accept all nodes."""
                return True

            def translate(
                self, node: ClassifiedNode, context: TranslationContext
            ) -> TranslationResult:
                """Return a simple PassState."""
                return TranslationResult(
                    states={node.node.name: PassState()},
                )

        expr = _lambda_expr('={{ DateTime.now().toISO() }}')
        cn = _node("MyNode", [expr])

        analysis = WorkflowAnalysis(
            classified_nodes=[cn],
            dependency_edges=[],
        )

        engine = TranslationEngine(translators=[StubTranslator()])
        output = engine.translate(analysis)

        assert "MyNode_ExprEval" in StateMachine.model_validate(output.state_machine).states
        assert "MyNode" in StateMachine.model_validate(output.state_machine).states
        assert len(output.lambda_artifacts) == 1
        assert any("Lambda evaluation" in w for w in output.warnings)

    def test_engine_wires_eval_before_main_state(self) -> None:
        """Test that eval states are wired before the main node state."""
        from n8n_to_sfn.engine import TranslationEngine
        from n8n_to_sfn.models.asl import PassState
        from n8n_to_sfn.translators.base import BaseTranslator, TranslationResult

        class StubTranslator(BaseTranslator):
            """Stub translator that produces a PassState for any node."""

            def can_translate(self, node: ClassifiedNode) -> bool:
                """Accept all nodes."""
                return True

            def translate(
                self, node: ClassifiedNode, context: TranslationContext
            ) -> TranslationResult:
                """Return a simple PassState."""
                return TranslationResult(
                    states={node.node.name: PassState()},
                )

        expr = _lambda_expr('={{ Math.round($json.x) }}')
        cn = _node("Calc", [expr])

        analysis = WorkflowAnalysis(
            classified_nodes=[cn],
            dependency_edges=[],
        )

        engine = TranslationEngine(translators=[StubTranslator()])
        output = engine.translate(analysis)

        eval_state = StateMachine.model_validate(output.state_machine).states["Calc_ExprEval"]
        assert eval_state.next == "Calc"

    def test_engine_start_at_points_to_eval_state(self) -> None:
        """Test that StartAt points to the eval state when first node has one."""
        from n8n_to_sfn.engine import TranslationEngine
        from n8n_to_sfn.models.asl import PassState
        from n8n_to_sfn.translators.base import BaseTranslator, TranslationResult

        class StubTranslator(BaseTranslator):
            """Stub translator that produces a PassState for any node."""

            def can_translate(self, node: ClassifiedNode) -> bool:
                """Accept all nodes."""
                return True

            def translate(
                self, node: ClassifiedNode, context: TranslationContext
            ) -> TranslationResult:
                """Return a simple PassState."""
                return TranslationResult(
                    states={node.node.name: PassState()},
                )

        expr = _lambda_expr('={{ $json.x }}')
        cn = _node("First", [expr])

        analysis = WorkflowAnalysis(
            classified_nodes=[cn],
            dependency_edges=[],
        )

        engine = TranslationEngine(translators=[StubTranslator()])
        output = engine.translate(analysis)

        assert output.state_machine["StartAt"] == "First_ExprEval"

    def test_engine_predecessor_wires_to_eval_state(self) -> None:
        """Test that predecessor Next points to eval state, not main state."""
        from phaeton_models.translator import DependencyEdge

        from n8n_to_sfn.engine import TranslationEngine
        from n8n_to_sfn.models.asl import PassState
        from n8n_to_sfn.translators.base import BaseTranslator, TranslationResult

        class StubTranslator(BaseTranslator):
            """Stub translator that produces a PassState for any node."""

            def can_translate(self, node: ClassifiedNode) -> bool:
                """Accept all nodes."""
                return True

            def translate(
                self, node: ClassifiedNode, context: TranslationContext
            ) -> TranslationResult:
                """Return a simple PassState."""
                return TranslationResult(
                    states={node.node.name: PassState()},
                )

        prev_node = _node("Prev")
        expr = _lambda_expr('={{ $json.x }}')
        target_node = _node("Target", [expr])

        analysis = WorkflowAnalysis(
            classified_nodes=[prev_node, target_node],
            dependency_edges=[
                DependencyEdge(
                    from_node="Prev",
                    to_node="Target",
                    edge_type="CONNECTION",
                ),
            ],
        )

        engine = TranslationEngine(translators=[StubTranslator()])
        output = engine.translate(analysis)

        prev_state = StateMachine.model_validate(output.state_machine).states["Prev"]
        assert prev_state.next == "Target_ExprEval"


# ---------------------------------------------------------------------------
# Expression injection validation tests
# ---------------------------------------------------------------------------


class TestExpressionValidation:
    """Tests for expression security validation."""

    @pytest.mark.parametrize(
        ("payload", "expected_reason"),
        [
            ("1; process.exit(0); //", "'process'"),
            ("process.env.SECRET", "'process'"),
            ('eval("malicious")', "'eval'"),
            ('require("child_process").exec("rm -rf /")', "'require'"),
            ('Function("return this")()', "'Function'"),
            ('import("fs")', "'import'"),
            ("global.constructor", "'global'"),
            ("window.location", "'window'"),
            ("$json.__proto__.polluted", "'__proto__'"),
            ("$json.constructor.prototype", "'constructor'"),
            ("$json.a; $json.b", "';'"),
        ],
        ids=[
            "process.exit",
            "process.env",
            "eval",
            "require",
            "Function_constructor",
            "import",
            "global",
            "window",
            "__proto__",
            "constructor",
            "semicolon",
        ],
    )
    def test_dangerous_patterns_rejected(
        self, payload: str, expected_reason: str
    ) -> None:
        """Test that known injection payloads are rejected."""
        with pytest.raises(ValueError, match=expected_reason):
            _validate_expression(payload)

    def test_bare_brace_rejected(self) -> None:
        """Test that block statement braces are rejected."""
        with pytest.raises(ValueError, match="block statement braces"):
            _validate_expression("if (true) { bad() }")

    @pytest.mark.parametrize(
        "expr",
        [
            "$json.name",
            "$json.count + 1",
            '$json.active ? "yes" : "no"',
            "$json.name.toUpperCase()",
            "$json.items.map(i => i.name)",
            "Math.round($json.value * 100) / 100",
            "DateTime.now().toISO()",
            '$json.status === "active" ? "yes" : "no"',
            "$json.items.length",
            "$json.a + $json.b",
            '$node["Lookup"].json.id',
            "$json.name.trim().toLowerCase()",
            "$json.list.filter(x => x > 0)",
            "`Hello ${$json.name}`",
        ],
        ids=[
            "property_access",
            "arithmetic",
            "ternary",
            "string_method",
            "array_map",
            "math_round",
            "datetime",
            "equality_ternary",
            "array_length",
            "addition",
            "node_reference",
            "chained_methods",
            "array_filter",
            "template_literal",
        ],
    )
    def test_legitimate_expressions_pass(self, expr: str) -> None:
        """Test that legitimate n8n expressions pass validation."""
        _validate_expression(expr)

    def test_error_message_includes_expression(self) -> None:
        """Test that error messages include the offending expression."""
        with pytest.raises(ValueError, match=r"process\.exit"):
            _validate_expression("process.exit(1)")


class TestInjectionInBuildExpressionCode:
    """Tests that injection is rejected through the full code path."""

    def test_injection_rejected_in_direct_path(self) -> None:
        """Test that _build_expression_code rejects injection payloads."""
        expr = _lambda_expr('={{ 1; process.exit(0); // }}')
        node = _node("InjectNode", [expr])
        result = evaluate_lambda_expressions(node, _context())

        # Should fall back to the placeholder template (not executable code)
        handler = result.lambda_artifacts[0].handler_code
        assert "Expression evaluation not implemented" in handler
        # The dangerous expression must not appear as executable JS
        assert "const expressionResult = 1; process.exit(0)" not in handler

    def test_injection_rejected_in_ai_agent_path(self) -> None:
        """Test that the AI agent path also rejects injection payloads."""
        ai_agent = MagicMock()
        ai_agent.translate_expression.return_value = (
            '1; process.exit(0); //'
        )

        expr = _lambda_expr('={{ $json.value }}')
        node = _node("AIInjectNode", [expr])
        result = evaluate_lambda_expressions(node, _context(), ai_agent=ai_agent)

        # AI agent result rejected, should fall back to direct eval
        handler = result.lambda_artifacts[0].handler_code
        assert "process.exit" not in handler

    def test_eval_injection_via_ai_agent(self) -> None:
        """Test that eval injection via AI agent is blocked."""
        ai_agent = MagicMock()
        ai_agent.translate_expression.return_value = 'eval("malicious")'

        expr = _lambda_expr('={{ $json.x }}')
        node = _node("EvalInject", [expr])
        result = evaluate_lambda_expressions(node, _context(), ai_agent=ai_agent)

        handler = result.lambda_artifacts[0].handler_code
        # The eval("malicious") payload must not appear as executable code
        assert 'eval("malicious")' not in handler

    def test_require_injection_via_ai_agent(self) -> None:
        """Test that require injection via AI agent is blocked."""
        ai_agent = MagicMock()
        ai_agent.translate_expression.return_value = (
            'require("child_process").exec("rm -rf /")'
        )

        expr = _lambda_expr('={{ $json.x }}')
        node = _node("ReqInject", [expr])
        result = evaluate_lambda_expressions(node, _context(), ai_agent=ai_agent)

        handler = result.lambda_artifacts[0].handler_code
        assert "child_process" not in handler
