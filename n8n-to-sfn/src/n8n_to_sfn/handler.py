"""AWS Lambda handler for the n8n-to-Step Functions translation service."""

from __future__ import annotations

import os
import traceback
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from phaeton_models.translator import WorkflowAnalysis
from pydantic import ValidationError

from n8n_to_sfn.ai_agent.client import AIAgentClient
from n8n_to_sfn.engine import TranslationEngine, TranslationOutput
from n8n_to_sfn.errors import TranslationError
from n8n_to_sfn.translators.aws_service import AWSServiceTranslator
from n8n_to_sfn.translators.code_node import CodeNodeTranslator
from n8n_to_sfn.translators.flow_control import FlowControlTranslator
from n8n_to_sfn.translators.http_request import HttpRequestTranslator
from n8n_to_sfn.translators.picofun import PicoFunTranslator
from n8n_to_sfn.translators.triggers import TriggerTranslator

logger = Logger(service="n8n-to-sfn")


def create_default_engine() -> TranslationEngine:
    """Create a TranslationEngine with all registered translators."""
    ai_agent = None
    agent_function = os.environ.get("AI_AGENT_FUNCTION_NAME")
    if agent_function:
        ai_agent = AIAgentClient(function_name=agent_function)
    return TranslationEngine(
        translators=[
            FlowControlTranslator(),
            AWSServiceTranslator(),
            TriggerTranslator(),
            CodeNodeTranslator(),
            HttpRequestTranslator(),
            PicoFunTranslator(),
        ],
        ai_agent=ai_agent,
    )


def handler(event: dict[str, Any], context: LambdaContext | None) -> dict[str, Any]:
    """Lambda handler that translates a WorkflowAnalysis into a TranslationOutput.

    Parameters
    ----------
    event:
        JSON payload conforming to the ``WorkflowAnalysis`` schema.
    context:
        AWS Lambda context (may be ``None`` for local invocation).

    Returns
    -------
    dict
        JSON response conforming to the ``TranslationOutput`` schema, or a
        structured error response on failure.

    """
    if context is not None:
        logger.structure_logs(
            append=True,
            function_name=context.function_name,
            function_arn=context.invoked_function_arn,
            function_request_id=context.aws_request_id,
        )

    try:
        analysis = WorkflowAnalysis.model_validate(event)
    except ValidationError as exc:
        logger.warning("Invalid payload", extra={"errors": exc.error_count()})
        return _error_response(
            status_code=400,
            error_type="ValidationError",
            message=f"Invalid WorkflowAnalysis payload: {exc.error_count()} validation error(s)",
            details=exc.errors(include_url=False),
        )

    try:
        engine = create_default_engine()
        output: TranslationOutput = engine.translate(analysis)
    except TranslationError as exc:
        logger.exception("Translation failed")
        return _error_response(
            status_code=422,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )
    except Exception as exc:
        logger.exception("Unexpected error during translation")
        return _error_response(
            status_code=500,
            error_type=type(exc).__name__,
            message=str(exc),
            details=traceback.format_exc(),
        )

    logger.info(
        "Translation succeeded",
        extra={
            "total_nodes": output.conversion_report.get("total_nodes"),
            "translated_nodes": output.conversion_report.get("translated_nodes"),
            "warning_count": len(output.warnings),
        },
    )
    return output.model_dump(mode="json")


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


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m n8n_to_sfn.handler <payload.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        payload = json.load(f)

    result = handler(payload, None)
    print(json.dumps(result, indent=2))
