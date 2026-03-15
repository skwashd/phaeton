"""Trigger node translator (Schedule, Webhook, Manual, App-specific)."""

from __future__ import annotations

from phaeton_models.translator import ClassifiedNode, NodeClassification

from n8n_to_sfn.translators.base import (
    BaseTranslator,
    LambdaArtifact,
    LambdaRuntime,
    TranslationContext,
    TranslationResult,
    TriggerArtifact,
    TriggerType,
)

# ---------------------------------------------------------------------------
# n8n node type constants
# ---------------------------------------------------------------------------

_TYPE_SCHEDULE = "n8n-nodes-base.scheduleTrigger"
_TYPE_WEBHOOK = "n8n-nodes-base.webhook"
_TYPE_MANUAL = "n8n-nodes-base.manualTrigger"

# ---------------------------------------------------------------------------
# Webhook handler template
# ---------------------------------------------------------------------------

_WEBHOOK_HANDLER_TEMPLATE = '''\
"""Lambda handler for webhook trigger.

Receives an API Gateway event and starts a Step Functions execution.
The state machine ARN is read from the STATE_MACHINE_ARN environment variable.
"""

from __future__ import annotations

import json
import logging
import os
import uuid

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sfn_client = boto3.client("stepfunctions")


def handler(event: dict, context: object) -> dict:
    """Handle an API Gateway proxy event and start a Step Functions execution.

    Args:
        event: The API Gateway proxy event dict.
        context: The Lambda context object (unused).

    Returns:
        An API Gateway proxy response dict.
    """
    state_machine_arn = os.environ["STATE_MACHINE_ARN"]

    body = event.get("body") or "{}"
    if isinstance(body, str):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw_body": body}
    else:
        payload = body

    execution_input = {
        "webhook_event": {
            "body": payload,
            "headers": event.get("headers", {}),
            "query_string": event.get("queryStringParameters", {}),
            "http_method": event.get("httpMethod", "POST"),
            "path": event.get("path", "/"),
        }
    }

    execution_name = f"webhook-{uuid.uuid4()}"

    try:
        response = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps(execution_input),
        )
        logger.info("Started execution: %s", response["executionArn"])
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "executionArn": response["executionArn"],
                    "startDate": response["startDate"].isoformat(),
                }
            ),
        }
    except Exception:
        logger.exception("Failed to start Step Functions execution")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Failed to start execution"}),
        }
'''


# ---------------------------------------------------------------------------
# Schedule extraction helpers
# ---------------------------------------------------------------------------


def _extract_schedule_config(parameters: dict) -> dict:
    """
    Extract EventBridge schedule configuration from a scheduleTrigger node.

    Handles both cron-expression and interval-based trigger settings.
    Returns a dict suitable for use as ``TriggerArtifact.config``.
    """
    rule = parameters.get("rule", {})
    if not isinstance(rule, dict):
        return {}

    trigger_settings = rule.get("values", [])
    if not trigger_settings:
        return {}

    setting = (
        trigger_settings[0] if isinstance(trigger_settings, list) else trigger_settings
    )
    if not isinstance(setting, dict):
        return {}

    mode = setting.get("mode", "everyX")

    if mode == "cronExpression":
        return _config_from_cron(setting)

    return _config_from_interval(setting, mode)


def _config_from_cron(setting: dict) -> dict:
    """Build a schedule config from a cron-expression setting."""
    cron_expr = setting.get("cronExpression", "")
    return {
        "schedule_type": "cron",
        "cron_expression": cron_expr,
        "schedule_expression": f"cron({cron_expr})" if cron_expr else "",
    }


def _config_from_interval(setting: dict, mode: str) -> dict:
    """Build a schedule config from an interval-based setting."""
    unit_map = {
        "everyMinute": ("minutes", 1),
        "everyX": ("minutes", int(setting.get("value", 5))),
        "everyHour": ("hours", 1),
        "everyDay": ("days", 1),
        "everyWeek": ("weeks", 1),
        "everyMonth": ("months", 1),
    }
    if mode in unit_map:
        unit, value = unit_map[mode]
        return {
            "schedule_type": "rate",
            "rate_value": value,
            "rate_unit": unit,
            "schedule_expression": f"rate({value} {unit})",
        }

    interval = int(setting.get("value", 5))
    return {
        "schedule_type": "rate",
        "rate_value": interval,
        "rate_unit": "minutes",
        "schedule_expression": f"rate({interval} minutes)",
    }


# ---------------------------------------------------------------------------
# Per-trigger translation helpers
# ---------------------------------------------------------------------------


def _translate_schedule(node: ClassifiedNode) -> TranslationResult:
    """Translate a scheduleTrigger node to an EventBridge schedule artifact."""
    config = _extract_schedule_config(node.node.parameters)
    artifact = TriggerArtifact(
        trigger_type=TriggerType.EVENTBRIDGE_SCHEDULE,
        config=config,
    )
    return TranslationResult(trigger_artifacts=[artifact])


def _translate_webhook(node: ClassifiedNode, workflow_name: str) -> TranslationResult:
    """
    Translate a webhook node to a Lambda function URL artifact and trigger artifact.

    Generates a Python Lambda handler that calls ``sfn_client.start_execution``
    and pairs it with a ``LAMBDA_FURL`` trigger artifact.
    """
    safe_name = workflow_name.lower().replace(" ", "-") if workflow_name else "workflow"
    function_name = f"{safe_name}-webhook-handler"
    directory_name = f"{safe_name}-webhook-handler"

    params = node.node.parameters
    http_method = params.get("httpMethod", "POST")
    path = params.get("path", "/webhook")

    lambda_artifact = LambdaArtifact(
        function_name=function_name,
        runtime=LambdaRuntime.PYTHON,
        handler_code=_WEBHOOK_HANDLER_TEMPLATE,
        dependencies=["boto3"],
        directory_name=directory_name,
    )

    trigger_config = {
        "http_method": http_method,
        "path": path,
        "authentication": params.get("authentication", "none"),
    }

    trigger_artifact = TriggerArtifact(
        trigger_type=TriggerType.LAMBDA_FURL,
        config=trigger_config,
        lambda_artifact=lambda_artifact,
    )

    return TranslationResult(
        lambda_artifacts=[lambda_artifact],
        trigger_artifacts=[trigger_artifact],
    )


def _translate_manual(_node: ClassifiedNode) -> TranslationResult:
    """Translate a manualTrigger node to a MANUAL trigger artifact with no infrastructure."""
    artifact = TriggerArtifact(
        trigger_type=TriggerType.MANUAL,
        config={},
    )
    return TranslationResult(trigger_artifacts=[artifact])


def _translate_unknown(node: ClassifiedNode, workflow_name: str) -> TranslationResult:
    """Translate an unrecognised trigger to a LAMBDA_FURL artifact with a warning."""
    node_type = node.node.type
    warning = (
        f"Unsupported trigger type '{node_type}' on node '{node.node.name}'. "
        "Falling back to LAMBDA_FURL. Manual wiring of the trigger source is required."
    )

    safe_name = workflow_name.lower().replace(" ", "-") if workflow_name else "workflow"
    safe_type = node_type.split(".")[-1].lower()
    function_name = f"{safe_name}-{safe_type}-handler"
    directory_name = function_name

    lambda_artifact = LambdaArtifact(
        function_name=function_name,
        runtime=LambdaRuntime.PYTHON,
        handler_code=_WEBHOOK_HANDLER_TEMPLATE,
        dependencies=["boto3"],
        directory_name=directory_name,
    )

    trigger_artifact = TriggerArtifact(
        trigger_type=TriggerType.LAMBDA_FURL,
        config={"source_node_type": node_type},
        lambda_artifact=lambda_artifact,
    )

    return TranslationResult(
        lambda_artifacts=[lambda_artifact],
        trigger_artifacts=[trigger_artifact],
        warnings=[warning],
    )


# ---------------------------------------------------------------------------
# Main translator class
# ---------------------------------------------------------------------------


class TriggerTranslator(BaseTranslator):
    """
    Translator for n8n trigger nodes.

    Trigger nodes do not produce ASL states. Instead they produce infrastructure
    artifacts (``TriggerArtifact`` and optionally ``LambdaArtifact``) that the
    surrounding IaC layer uses to wire up the workflow's entry point.

    Supported trigger types:

    * ``n8n-nodes-base.scheduleTrigger`` → EventBridge scheduled rule
    * ``n8n-nodes-base.webhook``         → Lambda function URL (FURL)
    * ``n8n-nodes-base.manualTrigger``   → No infrastructure (manual only)
    * Any other trigger                  → Lambda FURL fallback with warning
    """

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True when the node is classified as a TRIGGER."""
        return node.classification == NodeClassification.TRIGGER

    def translate(
        self,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> TranslationResult:
        """
        Translate a trigger node into infrastructure artifacts.

        No ASL states are emitted. The returned ``TranslationResult`` carries
        ``trigger_artifacts`` (and, for webhook/unknown types, ``lambda_artifacts``)
        that the engine surfaces in its output.
        """
        node_type = node.node.type
        workflow_name = context.workflow_name

        if node_type == _TYPE_SCHEDULE:
            return _translate_schedule(node)

        if node_type == _TYPE_WEBHOOK:
            return _translate_webhook(node, workflow_name)

        if node_type == _TYPE_MANUAL:
            return _translate_manual(node)

        return _translate_unknown(node, workflow_name)
