"""AWS Lambda handler for the workflow analysis service."""

from __future__ import annotations

import traceback
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from workflow_analyzer.analyzer import WorkflowAnalyzer
from workflow_analyzer.models.exceptions import WorkflowParseError

logger = Logger(service="workflow-analyzer")


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """Analyze an n8n workflow and return a ConversionReport."""
    if context is not None:
        logger.structure_logs(
            append=True,
            function_name=context.function_name,
            function_arn=context.invoked_function_arn,
            function_request_id=context.aws_request_id,
        )

    workflow_data = event.get("workflow")
    if not isinstance(workflow_data, dict):
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message="Payload must contain a 'workflow' key with the n8n workflow JSON object",
        )

    try:
        analyzer = WorkflowAnalyzer()
        report = analyzer.analyze_dict(workflow_data)
    except (ValidationError, WorkflowParseError) as exc:
        logger.warning("Invalid workflow payload", extra={"error": str(exc)})
        return _error_response(
            status_code=400,
            error_type=type(exc).__name__,
            message=str(exc),
        )
    except Exception as exc:
        logger.exception("Unexpected error during analysis")
        return _error_response(
            status_code=500,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )

    logger.info(
        "Analysis succeeded",
        extra={
            "total_nodes": report.total_nodes,
            "confidence_score": report.confidence_score,
        },
    )
    return report.model_dump(mode="json")


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
