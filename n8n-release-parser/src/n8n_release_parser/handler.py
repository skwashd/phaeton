"""AWS Lambda handler for the n8n release parser service."""

from __future__ import annotations

import asyncio
import traceback
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from n8n_release_parser.fetcher import list_versions

logger = Logger(service="n8n-release-parser")


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """Fetch recent n8n release versions from the npm registry."""
    if context is not None:
        logger.structure_logs(
            append=True,
            function_name=context.function_name,
            function_arn=context.invoked_function_arn,
            function_request_id=context.aws_request_id,
        )

    months = event.get("months", 12)
    if not isinstance(months, int) or months < 1:
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message="'months' must be a positive integer",
        )

    try:
        versions = asyncio.run(list_versions(months=months))
    except Exception as exc:
        logger.exception("Failed to fetch versions from npm")
        return _error_response(
            status_code=500,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )

    version_list = [v.model_dump(mode="json") for v in versions]

    logger.info(
        "Fetched versions",
        extra={"version_count": len(version_list), "months": months},
    )
    return {
        "status": "success",
        "months": months,
        "version_count": len(version_list),
        "versions": version_list,
    }


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
