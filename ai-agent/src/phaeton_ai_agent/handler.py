"""AWS Lambda handler for the AI agent translation service."""

from __future__ import annotations

import traceback
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from phaeton_ai_agent.agent import translate_expression, translate_node
from phaeton_ai_agent.models import ExpressionTranslationRequest, NodeTranslationRequest

logger = Logger(service="phaeton-ai-agent")


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """Lambda handler that routes AI agent translation requests.

    Parameters
    ----------
    event:
        JSON payload with ``operation`` and ``payload`` keys.
    context:
        AWS Lambda context (may be ``None`` for local invocation).

    Returns
    -------
    dict
        JSON response with the translation result, or a structured error.

    """
    if context is not None:
        logger.structure_logs(
            append=True,
            function_name=context.function_name,
            function_arn=context.invoked_function_arn,
            function_request_id=context.aws_request_id,
        )

    operation = event.get("operation")
    payload = event.get("payload", {})

    if operation == "translate_node":
        return _handle_translate_node(payload)
    if operation == "translate_expression":
        return _handle_translate_expression(payload)

    return _error_response(
        status_code=400,
        error_type="InvalidOperation",
        message=f"Unknown operation: {operation!r}. Expected 'translate_node' or 'translate_expression'.",
    )


def _handle_translate_node(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle a translate_node request."""
    try:
        request = NodeTranslationRequest.model_validate(payload)
    except ValidationError as exc:
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message=f"Invalid NodeTranslationRequest: {exc.error_count()} validation error(s)",
            details=exc.errors(include_url=False),
        )

    try:
        result = translate_node(request)
        return result.model_dump(mode="json")
    except Exception as exc:
        logger.exception("Unexpected error in translate_node")
        return _error_response(
            status_code=500,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )


def _handle_translate_expression(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle a translate_expression request."""
    try:
        request = ExpressionTranslationRequest.model_validate(payload)
    except ValidationError as exc:
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message=f"Invalid ExpressionTranslationRequest: {exc.error_count()} validation error(s)",
            details=exc.errors(include_url=False),
        )

    try:
        result = translate_expression(request)
        return result.model_dump(mode="json")
    except Exception as exc:
        logger.exception("Unexpected error in translate_expression")
        return _error_response(
            status_code=500,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )


def _error_response(
    *,
    status_code: int,
    error_type: str,
    message: str,
    details: str | list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a structured error response."""
    return {
        "error": {
            "status_code": status_code,
            "error_type": error_type,
            "message": message,
            "details": details,
        },
    }
