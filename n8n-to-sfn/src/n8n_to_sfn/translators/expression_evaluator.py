"""
Expression evaluator for REQUIRES_LAMBDA expressions (Category C).

Generates Lambda functions to evaluate complex n8n expressions that cannot
be translated directly to JSONata or Step Functions Variables.  These
include multi-node references, JavaScript built-ins, Date/Luxon operations,
and conditional expressions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from phaeton_models.translator import (
    ClassifiedExpression,
    ClassifiedNode,
    ExpressionCategory,
)

from n8n_to_sfn.models.asl import TaskState
from n8n_to_sfn.translators.base import (
    LambdaArtifact,
    LambdaRuntime,
    TranslationContext,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol for AI agent expression translation
# ---------------------------------------------------------------------------


class AIExpressionTranslator(Protocol):
    """Protocol for AI agent expression translation."""

    def translate_expression(
        self,
        expr: str,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> str:
        """Translate an n8n expression via the AI agent."""
        ...


# ---------------------------------------------------------------------------
# Lambda templates
# ---------------------------------------------------------------------------

_EXPR_LAMBDA_TEMPLATE = """\
// Auto-generated Lambda for evaluating n8n expression on node: {node_name}
const {{ DateTime }} = require('luxon');

exports.handler = async (event) => {{
  const nodeData = event.nodeData || {{}};
{upstream_bindings}
  // Expression evaluation
{expression_code}

  return {{ result: expressionResult }};
}};
"""

_FALLBACK_EXPR_TEMPLATE = """\
// Auto-generated placeholder Lambda for expression on node: {node_name}
// WARNING: This expression could not be automatically translated.
// The original n8n expression was: {original_expr}
// Manual review is required.

exports.handler = async (event) => {{
  // TODO: Implement expression evaluation
  // Original expression: {original_expr}
  return {{ result: null, warning: "Expression evaluation not implemented" }};
}};
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_name(name: str) -> str:
    """Convert a node/expression name to a valid Lambda function name."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return f"expr_eval_{sanitized.lower()}"


def _extract_node_references(expr: ClassifiedExpression) -> list[str]:
    """Extract upstream node names referenced in an expression."""
    refs = list(expr.node_references)
    for match in re.finditer(r'\$node\[\s*["\']([^"\']+)["\']\s*\]', expr.original):
        ref_name = match.group(1)
        if ref_name not in refs:
            refs.append(ref_name)
    return refs


def _build_upstream_bindings(node_refs: list[str]) -> str:
    """Build JS variable bindings for upstream node data."""
    lines = ['  const $json = nodeData["$json"] || {};']
    if node_refs:
        lines.append("  const $node = {};")
        for ref in node_refs:
            lines.append(f'  $node["{ref}"] = nodeData["{ref}"] || {{}};')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Expression security validation
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bprocess\b"), "access to 'process' object"),
    (re.compile(r"\brequire\b"), "use of 'require'"),
    (re.compile(r"\beval\b"), "use of 'eval'"),
    (re.compile(r"\bFunction\b"), "use of 'Function' constructor"),
    (re.compile(r"\bimport\b"), "use of 'import'"),
    (re.compile(r"\bglobal\b"), "access to 'global' object"),
    (re.compile(r"\bwindow\b"), "access to 'window' object"),
    (re.compile(r"\b__proto__\b"), "access to '__proto__'"),
    (re.compile(r"\bconstructor\b"), "access to 'constructor'"),
    (re.compile(r";"), "statement separator ';'"),
]

# Curly braces that are NOT part of template literal interpolation ${...}
_BARE_BRACE_PATTERN = re.compile(r"(?<!\$)\{")


def _validate_expression(expr: str) -> None:
    """
    Validate that an expression does not contain dangerous patterns.

    Raises ``ValueError`` if the expression contains patterns that could
    allow arbitrary code execution when interpolated into JavaScript.

    Parameters
    ----------
    expr:
        The stripped expression (without n8n ``={{ }}`` wrappers).

    """
    for pattern, description in _DANGEROUS_PATTERNS:
        if pattern.search(expr):
            msg = (
                f"Expression rejected: contains {description}. Expression: {expr[:100]}"
            )
            raise ValueError(msg)

    if _BARE_BRACE_PATTERN.search(expr):
        msg = (
            f"Expression rejected: contains block statement braces. "
            f"Use template literals (${{...}}) instead. "
            f"Expression: {expr[:100]}"
        )
        raise ValueError(msg)


def _strip_expression_wrapper(expr: str) -> str:
    """Strip n8n expression wrappers (``={{ }}``, ``{{ }}``, ``=``)."""
    stripped = expr.strip()
    if stripped.startswith("={{"):
        stripped = stripped[1:]
    if stripped.startswith("{{") and stripped.endswith("}}"):
        stripped = stripped[2:-2].strip()
    elif stripped.startswith("="):
        stripped = stripped[1:].strip()
    return stripped


def _build_expression_code(expr: str) -> str:
    """Build the JS code that evaluates the expression; raises ValueError if unsafe."""
    inner = _strip_expression_wrapper(expr)
    _validate_expression(inner)
    return f"  const expressionResult = {inner};"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ExpressionEvalResult:
    """Result of evaluating REQUIRES_LAMBDA expressions for a node."""

    def __init__(self) -> None:
        """Initialize an empty result."""
        self.states: dict[str, Any] = {}
        self.lambda_artifacts: list[LambdaArtifact] = []
        self.warnings: list[str] = []
        self.eval_state_names: list[str] = []


def evaluate_lambda_expressions(
    node: ClassifiedNode,
    context: TranslationContext,
    ai_agent: AIExpressionTranslator | None = None,
) -> ExpressionEvalResult:
    """
    Generate Lambda functions for REQUIRES_LAMBDA expressions on a node.

    For each expression classified as ``REQUIRES_LAMBDA``, a Node.js Lambda
    function is generated that evaluates the expression at runtime.  If an
    AI agent is available it is tried first; otherwise a direct-evaluation
    fallback is produced.

    Parameters
    ----------
    node:
        The classified node whose expressions should be evaluated.
    context:
        The current translation context.
    ai_agent:
        Optional AI agent for generating expression evaluation code.

    Returns
    -------
    ExpressionEvalResult
        States, Lambda artifacts, and warnings for the generated evaluators.

    """
    result = ExpressionEvalResult()

    lambda_exprs = [
        expr
        for expr in node.expressions
        if expr.category == ExpressionCategory.REQUIRES_LAMBDA
    ]

    if not lambda_exprs:
        return result

    for i, expr in enumerate(lambda_exprs):
        suffix = f"_{i}" if len(lambda_exprs) > 1 else ""
        state_name = f"{node.node.name}_ExprEval{suffix}"
        func_name = _sanitize_name(f"{node.node.name}{suffix}")

        node_refs = _extract_node_references(expr)

        handler_code = _try_ai_agent(expr, node, context, ai_agent, node_refs)

        if handler_code is None:
            handler_code = _build_eval_lambda(expr, node, node_refs)

        artifact = LambdaArtifact(
            function_name=func_name,
            runtime=LambdaRuntime.NODEJS,
            handler_code=handler_code,
            dependencies=["luxon"],
            directory_name=func_name,
        )

        state = TaskState(
            resource="arn:aws:states:::lambda:invoke",
            end=True,
            comment=f"Evaluate expression: {expr.original[:80]}",
        )

        result.states[state_name] = state
        result.lambda_artifacts.append(artifact)
        result.eval_state_names.append(state_name)
        result.warnings.append(
            f"Expression on '{node.node.name}' requires Lambda evaluation: "
            f"{expr.original[:100]}"
        )

    return result


# ---------------------------------------------------------------------------
# AI agent integration
# ---------------------------------------------------------------------------


def _try_ai_agent(
    expr: ClassifiedExpression,
    node: ClassifiedNode,
    context: TranslationContext,
    ai_agent: AIExpressionTranslator | None,
    node_refs: list[str],
) -> str | None:
    """
    Try to use the AI agent to generate expression evaluation code.

    Returns the full Lambda handler code on success, or ``None`` if the
    AI agent is unavailable or fails.
    """
    if ai_agent is None:
        return None

    try:
        translated = ai_agent.translate_expression(expr.original, node, context)
        if translated and translated != expr.original:
            _validate_expression(translated)
            upstream_bindings = _build_upstream_bindings(node_refs)
            return _EXPR_LAMBDA_TEMPLATE.format(
                node_name=node.node.name,
                upstream_bindings=upstream_bindings,
                expression_code=f"  const expressionResult = {translated};",
            )
    except ConnectionError, TimeoutError, json.JSONDecodeError, ValueError:
        logger.debug("AI agent failed for expression: %s", expr.original)

    return None


# ---------------------------------------------------------------------------
# Fallback Lambda generation
# ---------------------------------------------------------------------------


def _build_eval_lambda(
    expr: ClassifiedExpression,
    node: ClassifiedNode,
    node_refs: list[str],
) -> str:
    """Build a Lambda that evaluates the expression directly in Node.js."""
    upstream_bindings = _build_upstream_bindings(node_refs)

    try:
        expression_code = _build_expression_code(expr.original)
    except ValueError, IndexError, KeyError:
        return _FALLBACK_EXPR_TEMPLATE.format(
            node_name=node.node.name,
            original_expr=expr.original.replace("*/", "* /"),
        )

    return _EXPR_LAMBDA_TEMPLATE.format(
        node_name=node.node.name,
        upstream_bindings=upstream_bindings,
        expression_code=expression_code,
    )
