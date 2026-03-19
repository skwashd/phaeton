"""AWS Lambda handler for the node translator service."""

from __future__ import annotations

import traceback
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from phaeton_node_translator.agent import translate_node
from phaeton_node_translator.models import NodeTranslationRequest

logger = Logger(service="phaeton-node-translator")


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """
    Lambda handler that translates an n8n node to ASL states.

    The event is deserialized directly as a ``NodeTranslationRequest`` — no
    ``operation`` field routing is needed.

    Parameters
    ----------
    event:
        JSON payload matching the ``NodeTranslationRequest`` schema.
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
        request = NodeTranslationRequest.model_validate(event)
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
