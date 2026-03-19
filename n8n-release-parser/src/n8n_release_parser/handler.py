"""AWS Lambda handler for the n8n release parser service."""

from __future__ import annotations

import traceback
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from n8n_release_parser import service
from n8n_release_parser.storage import create_backend

logger = Logger(service="n8n-release-parser")


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """Route incoming events to the appropriate service operation."""
    if context is not None:
        logger.structure_logs(
            append=True,
            function_name=context.function_name,
            function_arn=context.invoked_function_arn,
            function_request_id=context.aws_request_id,
        )

    operation = event.get("operation", "list_versions")

    try:
        match operation:
            case "list_versions":
                return _handle_list_versions(event)
            case "fetch_releases":
                return _handle_fetch_releases(event)
            case "diff_catalogs":
                return _handle_diff_catalogs(event)
            case "build_catalog":
                return _handle_build_catalog(event)
            case "generate_report":
                return _handle_generate_report(event)
            case _:
                return _error_response(
                    status_code=400,
                    error_type="ValidationError",
                    message=f"Unknown operation: {operation}",
                )
    except Exception as exc:
        logger.exception("Operation %s failed", operation)
        return _error_response(
            status_code=500,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )


def _handle_list_versions(event: dict[str, Any]) -> dict[str, Any]:
    """Handle the list_versions operation."""
    months = event.get("months", 12)
    if not isinstance(months, int) or months < 1:
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message="'months' must be a positive integer",
        )

    versions = service.list_versions(months=months)
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


def _handle_fetch_releases(event: dict[str, Any]) -> dict[str, Any]:
    """Handle the fetch_releases operation."""
    return _handle_list_versions(event)


def _handle_diff_catalogs(event: dict[str, Any]) -> dict[str, Any]:
    """Handle the diff_catalogs operation."""
    store_uri = event.get("store_uri")
    old_version = event.get("old_version")
    new_version = event.get("new_version")

    if not store_uri or not old_version or not new_version:
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message="'store_uri', 'old_version', and 'new_version' are required",
        )

    backend = create_backend(store_uri)
    result = service.diff_catalogs(backend, old_version, new_version)

    return {
        "status": "success",
        "diff": result.model_dump(mode="json"),
    }


def _handle_build_catalog(event: dict[str, Any]) -> dict[str, Any]:
    """Handle the build_catalog operation."""
    store_uri = event.get("store_uri")
    if not store_uri:
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message="'store_uri' is required",
        )

    backend = create_backend(store_uri)
    lookup = service.build_catalog(backend)

    entries = [
        {
            "node_type": key[0],
            "type_version": key[1],
            "entry": entry.model_dump(mode="json"),
        }
        for key, entry in sorted(lookup.items())
    ]

    return {
        "status": "success",
        "entry_count": len(entries),
        "entries": entries,
    }


def _handle_generate_report(event: dict[str, Any]) -> dict[str, Any]:
    """Handle the generate_report operation."""
    store_uri = event.get("store_uri")
    if not store_uri:
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message="'store_uri' is required",
        )

    backend = create_backend(store_uri)
    result = service.generate_report(backend)

    return {
        "status": "success",
        "report": result,
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
