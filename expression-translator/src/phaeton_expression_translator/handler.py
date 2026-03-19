"""AWS Lambda handler for the expression translator service."""

from __future__ import annotations

import traceback
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from phaeton_expression_translator.agent import translate_expression
from phaeton_expression_translator.models import ExpressionTranslationRequest

logger = Logger(service="phaeton-expression-translator")


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """
    Lambda handler that translates an n8n expression to JSONata.

    The event is deserialized directly as an ``ExpressionTranslationRequest`` — no
    ``operation`` field routing is needed.

    Parameters
    ----------
    event:
        JSON payload matching the ``ExpressionTranslationRequest`` schema.
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

    try:
        request = ExpressionTranslationRequest.model_validate(event)
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
    details: str | list[Any] | None = None,
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
