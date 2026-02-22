"""AWS service node translator (S3, DynamoDB, SQS, SNS, SES, Lambda, EventBridge)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from n8n_to_sfn.models.analysis import ClassifiedNode, NodeClassification
from n8n_to_sfn.models.asl import RetryConfig, TaskState
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    TranslationContext,
    TranslationResult,
    apply_error_handling,
)

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ARN_SDK_BASE = "arn:aws:states:::aws-sdk"
_ARN_LAMBDA_INVOKE = "arn:aws:states:::lambda:invoke"

# Default retry applied to all AWS SDK task states unless the node overrides it.
_DEFAULT_RETRY = RetryConfig(
    error_equals=["States.TaskFailed"],
    interval_seconds=2,
    max_attempts=3,
    backoff_rate=2.0,
    max_delay_seconds=30,
)

# ---------------------------------------------------------------------------
# Operation maps: (resource, operation) -> SDK API method name
# ---------------------------------------------------------------------------

# Keys match n8n parameter values: node.parameters["resource"] / ["operation"].
# Values are the SDK camelCase method names used in the ARN suffix.

_S3_OPS: dict[tuple[str, str], str] = {
    ("bucket", "getAll"): "listBuckets",
    ("bucket", "create"): "createBucket",
    ("bucket", "delete"): "deleteBucket",
    ("object", "get"): "getObject",
    ("object", "getAll"): "listObjectsV2",
    ("object", "create"): "putObject",
    ("object", "delete"): "deleteObject",
    ("object", "copy"): "copyObject",
}

_DYNAMODB_OPS: dict[tuple[str, str], str] = {
    ("item", "get"): "getItem",
    ("item", "create"): "putItem",
    ("item", "update"): "updateItem",
    ("item", "delete"): "deleteItem",
    ("item", "getAll"): "scan",
    ("item", "query"): "query",
}

_SQS_OPS: dict[tuple[str, str], str] = {
    ("message", "send"): "sendMessage",
    ("message", "receive"): "receiveMessage",
    ("message", "delete"): "deleteMessage",
    ("message", "sendBatch"): "sendMessageBatch",
    ("queue", "getAll"): "listQueues",
    ("queue", "create"): "createQueue",
    ("queue", "delete"): "deleteQueue",
}

_SNS_OPS: dict[tuple[str, str], str] = {
    ("topic", "publish"): "publish",
    ("topic", "create"): "createTopic",
    ("topic", "delete"): "deleteTopic",
    ("topic", "getAll"): "listTopics",
    ("subscription", "create"): "subscribe",
    ("subscription", "delete"): "unsubscribe",
    ("subscription", "getAll"): "listSubscriptions",
}

_SES_OPS: dict[tuple[str, str], str] = {
    ("email", "send"): "sendEmail",
    ("email", "sendTemplate"): "sendTemplatedEmail",
    ("template", "create"): "createTemplate",
    ("template", "delete"): "deleteTemplate",
    ("template", "getAll"): "listTemplates",
}

_EVENTBRIDGE_OPS: dict[tuple[str, str], str] = {
    ("event", "send"): "putEvents",
    ("rule", "create"): "putRule",
    ("rule", "delete"): "deleteRule",
    ("rule", "getAll"): "listRules",
    ("rule", "enable"): "enableRule",
    ("rule", "disable"): "disableRule",
}

# Node type -> (service slug for ARN, operation lookup table)
# Lambda is handled separately (fixed ARN, no SDK suffix).
_SERVICE_REGISTRY: dict[str, tuple[str, dict[tuple[str, str], str]]] = {
    "n8n-nodes-base.awsS3": ("s3", _S3_OPS),
    "n8n-nodes-base.awsDynamoDB": ("dynamodb", _DYNAMODB_OPS),
    "n8n-nodes-base.awsSqs": ("sqs", _SQS_OPS),
    "n8n-nodes-base.awsSns": ("sns", _SNS_OPS),
    "n8n-nodes-base.awsSes": ("ses", _SES_OPS),
    "n8n-nodes-base.awsEventBridge": ("eventbridge", _EVENTBRIDGE_OPS),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _camel_to_pascal(name: str) -> str:
    """Convert a camelCase identifier to PascalCase.

    Examples::

        _camel_to_pascal("bucketName")  # -> "BucketName"
        _camel_to_pascal("Key")         # -> "Key"  (already Pascal)
        _camel_to_pascal("url")         # -> "Url"
    """
    if not name:
        return name
    return name[0].upper() + name[1:]


def _convert_params(params: dict[str, object]) -> dict[str, object]:
    """Return a new dict with all top-level keys converted to PascalCase.

    Only the outermost keys are converted; nested dicts are left as-is so
    that caller-controlled structures (e.g. FilterExpression objects) are not
    altered.
    """
    return {_camel_to_pascal(k): v for k, v in params.items()}


def _build_sdk_arn(service: str, api_name: str) -> str:
    """Construct the SDK integration ARN for a given service and API method."""
    return f"{_ARN_SDK_BASE}:{service}:{api_name}"


def _resolve_sdk_api_name(
    op_map: dict[tuple[str, str], str],
    resource: str,
    operation: str,
    service: str,
) -> tuple[str, list[str]]:
    """Look up the SDK API method name, falling back to a best-effort heuristic.

    Returns the resolved API name and a (possibly empty) list of warning messages.
    """
    warnings: list[str] = []
    api_name = op_map.get((resource, operation))
    if api_name is None:
        # Heuristic: combine operation + capitalised resource as PascalCase name.
        fallback = operation + _camel_to_pascal(resource)
        warnings.append(
            f"No explicit SDK mapping for {service} ({resource!r}, {operation!r}); "
            f"using heuristic name {fallback!r}. Verify against the AWS SDK."
        )
        api_name = fallback
    return api_name, warnings


def _extract_node_params(
    node: ClassifiedNode,
    exclude_keys: set[str],
) -> dict[str, object]:
    """Extract node parameters, skip routing keys, and convert to PascalCase."""
    raw = {
        k: v
        for k, v in node.node.parameters.items()
        if k not in exclude_keys and v is not None and v != ""
    }
    return _convert_params(raw)


# ---------------------------------------------------------------------------
# Per-service translators
# ---------------------------------------------------------------------------


def _translate_sdk_service(
    node: ClassifiedNode,
    service: str,
    op_map: dict[tuple[str, str], str],
) -> tuple[TaskState, list[str]]:
    """Build a TaskState for any generic SDK-integrated AWS service node.

    Returns the constructed TaskState and a list of any warnings generated
    during translation.
    """
    params = node.node.parameters
    resource: str = str(params.get("resource", ""))
    operation: str = str(params.get("operation", ""))

    api_name, warnings = _resolve_sdk_api_name(op_map, resource, operation, service)
    arn = _build_sdk_arn(service, api_name)
    arguments = _extract_node_params(node, exclude_keys={"resource", "operation"})

    state = TaskState(
        resource=arn,
        comment=f"n8n {node.node.type} — {resource}.{operation}",
        arguments=arguments if arguments else None,
        end=True,
    )
    return state, warnings


def _translate_lambda(
    node: ClassifiedNode,
) -> tuple[TaskState, list[str]]:
    """Build a TaskState for an awsLambda node using the Lambda invoke integration.

    Returns the constructed TaskState and a list of any warnings generated
    during translation.
    """
    warnings: list[str] = []
    params = node.node.parameters

    function_name: str = str(params.get("function", params.get("functionName", "")))
    raw_payload: object = params.get("payload", params.get("additionalFields", {}))

    arguments: dict[str, object] = {}
    if function_name:
        arguments["FunctionName"] = function_name
    if isinstance(raw_payload, dict) and raw_payload:
        arguments["Payload"] = _convert_params(raw_payload)
    elif raw_payload and not isinstance(raw_payload, dict):
        arguments["Payload"] = raw_payload

    if not function_name:
        warnings.append(
            "awsLambda node is missing a function name; "
            "FunctionName will be absent from Arguments."
        )

    state = TaskState(
        resource=_ARN_LAMBDA_INVOKE,
        comment="n8n n8n-nodes-base.awsLambda — invoke",
        arguments=arguments if arguments else None,
        end=True,
    )
    return state, warnings


# ---------------------------------------------------------------------------
# Public translator class
# ---------------------------------------------------------------------------


class AWSServiceTranslator(BaseTranslator):
    """Translate AWS-native n8n nodes into ASL TaskStates with SDK integrations.

    Handles S3, DynamoDB, SQS, SNS, SES, Lambda, and EventBridge nodes by
    mapping n8n resource/operation pairs to AWS SDK API method names and
    constructing the appropriate SDK integration ARNs.
    """

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True when the node is classified as AWS_NATIVE."""
        return node.classification == NodeClassification.AWS_NATIVE

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a single AWS-native node into a TranslationResult.

        Dispatches to a per-service helper based on the n8n node type, applies
        default retry configuration, and delegates error handling to
        apply_error_handling from the base module.
        """
        node_type = node.node.type
        warnings: list[str] = []

        if node_type == "n8n-nodes-base.awsLambda":
            state, svc_warnings = _translate_lambda(node)
        elif node_type in _SERVICE_REGISTRY:
            service, op_map = _SERVICE_REGISTRY[node_type]
            state, svc_warnings = _translate_sdk_service(node, service, op_map)
        else:
            warnings.append(
                f"AWSServiceTranslator received unrecognised node type {node_type!r}; "
                "producing a no-op TaskState."
            )
            state = TaskState(
                resource=_build_sdk_arn("states", "noop"),
                comment=f"Unrecognised AWS node: {node_type}",
                end=True,
            )
            svc_warnings = []

        warnings.extend(svc_warnings)

        state = apply_error_handling(
            state,
            node,
            next_state_name=None,
            default_retry=_DEFAULT_RETRY,
        )

        state_name = node.node.name
        return TranslationResult(
            states={state_name: state.model_dump(by_alias=True)},
            warnings=warnings,
        )
