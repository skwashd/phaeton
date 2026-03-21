"""Client for invoking the AI agent Lambda from the Translation Engine."""

from __future__ import annotations

import json
import logging
from typing import Any

from phaeton_models.translator import ClassifiedNode

from n8n_to_sfn.translators.base import TranslationContext, TranslationResult

logger = logging.getLogger(__name__)


class AIAgentClient:
    """
    Invoke the AI agent Lambda to translate nodes and expressions.

    Implements ``AIAgentProtocol`` so it can be plugged into the
    ``TranslationEngine`` as the ``ai_agent`` parameter.

    boto3 is imported lazily at construction time because it is only
    available in the Lambda runtime and is not declared as a project
    dependency.
    """

    def __init__(
        self,
        node_translator_function_name: str,
        expression_translator_function_name: str,
        region_name: str | None = None,
    ) -> None:
        """Initialize the client with the Lambda function names."""
        import boto3

        self._node_translator_function_name = node_translator_function_name
        self._expression_translator_function_name = expression_translator_function_name
        self._lambda = boto3.client("lambda", region_name=region_name)

    def translate_node(
        self,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> TranslationResult:
        """
        Translate a node by invoking the AI agent Lambda.

        Parameters
        ----------
        node:
            The classified n8n node to translate.
        context:
            The current translation context.

        Returns
        -------
        TranslationResult
            The translation result, with ``ai_generated`` metadata on success.

        """
        try:
            payload = {
                "node_json": node.node.model_dump_json(),
                "node_type": node.node.type,
                "node_name": node.node.name,
                "expressions": _format_expressions(node),
                "workflow_context": _format_context(context),
                "position": f"states.{node.node.name}",
                "target_state_type": "Task",
            }
            response = self._invoke(
                self._node_translator_function_name,
                payload,
            )
        except Exception:
            logger.exception("Failed to invoke AI agent for node: %s", node.node.name)
            return TranslationResult(
                warnings=[f"AI agent invocation failed for node: {node.node.name}"],
                metadata={"ai_generated": True, "ai_error": True},
            )

        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            return TranslationResult(
                warnings=[f"AI agent error for node {node.node.name}: {error_msg}"],
                metadata={"ai_generated": True, "ai_error": True},
            )

        return TranslationResult(
            states=response.get("states", {}),
            warnings=response.get("warnings", []),
            metadata={
                "ai_generated": True,
                "confidence": response.get("confidence", "LOW"),
                "explanation": response.get("explanation", ""),
            },
        )

    def translate_expression(
        self,
        expr: str,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> str:
        """
        Translate an expression by invoking the AI agent Lambda.

        Parameters
        ----------
        expr:
            The n8n expression to translate.
        node:
            The node containing the expression.
        context:
            The current translation context.

        Returns
        -------
        str
            The translated expression, or the original on failure.

        """
        try:
            payload = {
                "expression": expr,
                "node_json": node.node.model_dump_json(),
                "node_type": node.node.type,
                "workflow_context": _format_context(context),
            }
            response = self._invoke(
                self._expression_translator_function_name,
                payload,
            )
        except Exception:
            logger.exception("Failed to invoke AI agent for expression: %s", expr)
            return expr

        if "error" in response:
            return expr

        return response.get("translated", expr)

    def _invoke(
        self,
        function_name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke the Lambda function and return the parsed response."""
        response = self._lambda.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )
        response_payload = response["Payload"].read()
        return json.loads(response_payload)


def _format_expressions(node: ClassifiedNode) -> str:
    """Format node expressions for the AI agent prompt."""
    params = node.node.parameters or {}
    expressions = []
    for key, value in params.items():
        if isinstance(value, str) and "{{" in value:
            expressions.append(f"- {key}: {value}")
    return "\n".join(expressions) if expressions else "None"


def _format_context(context: TranslationContext) -> str:
    """Format translation context for the AI agent prompt."""
    parts = []
    if context.workflow_name:
        parts.append(f"Workflow: {context.workflow_name}")
    parts.append(f"Total nodes: {len(context.analysis.classified_nodes)}")
    if context.resolved_variables:
        parts.append(f"Resolved variables: {list(context.resolved_variables.keys())}")
    return "\n".join(parts) if parts else "No additional context"
