"""AWS Lambda handler for adapter conversions between pipeline stages."""

from __future__ import annotations

import traceback
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from phaeton_models.adapters import (
    convert_output_to_packager_input,
    convert_report_to_analysis,
)
from phaeton_models.analyzer import ConversionReport
from phaeton_models.translator_output import TranslationOutput

logger = Logger(service="phaeton-adapter")

_OPERATIONS = {
    "analyzer_to_translator",
    "translator_to_packager",
}


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """
    Lambda handler that routes to the appropriate adapter conversion.

    Parameters
    ----------
    event:
        JSON payload with ``operation``, ``payload``, and optionally
        ``workflow_name``.
    context:
        AWS Lambda context (may be ``None`` for local invocation).

    Returns
    -------
    dict
        The converted model as JSON, or a structured error response.

    """
    if context is not None:
        logger.structure_logs(
            append=True,
            function_name=context.function_name,
            function_arn=context.invoked_function_arn,
            function_request_id=context.aws_request_id,
        )

    operation = event.get("operation")
    if operation not in _OPERATIONS:
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message=f"Unknown operation: {operation!r}. Must be one of {sorted(_OPERATIONS)}",
        )

    payload = event.get("payload")
    if not isinstance(payload, dict):
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message="'payload' must be a JSON object",
        )

    try:
        if operation == "analyzer_to_translator":
            return _adapt_analyzer_to_translator(payload)
        return _adapt_translator_to_packager(payload, event.get("workflow_name", "unnamed"))
    except Exception as exc:
        logger.exception("Adapter conversion failed", extra={"operation": operation})
        return _error_response(
            status_code=500,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )


def _adapt_analyzer_to_translator(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a ConversionReport to a WorkflowAnalysis."""
    report = ConversionReport.model_validate(payload)
    analysis = convert_report_to_analysis(report)
    logger.info("Adapted analyzer output to translator input")
    return analysis.model_dump(mode="json")


def _adapt_translator_to_packager(
    payload: dict[str, Any],
    workflow_name: str,
) -> dict[str, Any]:
    """Convert a TranslationOutput to a PackagerInput."""
    output = TranslationOutput.model_validate(payload)
    packager_input = convert_output_to_packager_input(output, workflow_name)
    logger.info("Adapted translator output to packager input")
    return packager_input.model_dump(mode="json")


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
