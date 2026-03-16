"""AWS Lambda handler for the packaging service."""

from __future__ import annotations

import os
import traceback
import zipfile
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from n8n_to_sfn_packager.models.inputs import PackagerInput
from n8n_to_sfn_packager.packager import Packager, PackagerError

logger = Logger(service="packager")


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """
    Lambda handler that packages a translated workflow and uploads to S3.

    Parameters
    ----------
    event:
        JSON payload conforming to the ``PackagerInput`` schema.
    context:
        AWS Lambda context (may be ``None`` for local invocation).

    Returns
    -------
    dict
        JSON response with ``s3_bucket`` and ``s3_key`` of the uploaded
        package, or a structured error response on failure.

    """
    if context is not None:
        logger.structure_logs(
            append=True,
            function_name=context.function_name,
            function_arn=context.invoked_function_arn,
            function_request_id=context.aws_request_id,
        )

    try:
        input_data = PackagerInput.model_validate(event)
    except ValidationError as exc:
        logger.warning("Invalid payload", extra={"errors": exc.error_count()})
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message=f"Invalid PackagerInput payload: {exc.error_count()} validation error(s)",
            details=exc.errors(include_url=False),  # type: ignore[invalid-argument-type]
        )

    workflow_name = input_data.metadata.workflow_name
    output_dir = Path("/tmp") / workflow_name  # noqa: S108

    try:
        packager = Packager()
        packager.package(input_data, output_dir)
    except PackagerError as exc:
        logger.exception("Packaging failed")
        return _error_response(
            status_code=422,
            error_type="PackagerError",
            message=str(exc),
            details=traceback.format_exc(),
        )
    except Exception as exc:
        logger.exception("Unexpected error during packaging")
        return _error_response(
            status_code=500,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )

    zip_path = Path("/tmp") / f"{workflow_name}.zip"  # noqa: S108
    _zip_directory(output_dir, zip_path)

    bucket = os.environ.get("OUTPUT_BUCKET", "")
    if not bucket:
        return _error_response(
            status_code=500,
            error_type="ConfigurationError",
            message="OUTPUT_BUCKET environment variable is not set",
        )

    s3_key = f"packages/{workflow_name}.zip"
    try:
        s3 = boto3.client("s3")
        s3.upload_file(str(zip_path), bucket, s3_key)
    except Exception as exc:
        logger.exception("S3 upload failed")
        return _error_response(
            status_code=500,
            error_type="S3UploadError",
            message=f"Failed to upload package to S3: {exc}",
            details=traceback.format_exc(),
        )

    logger.info(
        "Packaging succeeded",
        extra={"s3_bucket": bucket, "s3_key": s3_key},
    )
    return {
        "status": "success",
        "s3_bucket": bucket,
        "s3_key": s3_key,
        "workflow_name": workflow_name,
    }


def _zip_directory(source_dir: Path, zip_path: Path) -> None:
    """Create a zip archive from a directory."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(source_dir))


def _error_response(
    *,
    status_code: int,
    error_type: str,
    message: str,
    details: str | list[dict[str, Any]] | None = None,
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
