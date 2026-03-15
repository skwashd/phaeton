"""
Flow control node translator (IF, Switch, Merge, SplitInBatches, Loop, Wait, NoOp, Execute Workflow).

Converts n8n flow control nodes into equivalent ASL states:

- IF              → ChoiceState with JSONata Condition
- Switch          → ChoiceState with multiple ChoiceRules + Default
- SplitInBatches  → MapState (MaxConcurrency=1, INLINE mode)
- Loop            → MapState (count-based) or ChoiceState loop-back (condition-based)
- Merge           → PassState placeholder (engine post-processing wraps in Parallel)
- Wait            → WaitState
- NoOp            → PassState
- Execute Workflow → TaskState (startExecution.sync:2)
"""

from __future__ import annotations

from phaeton_models.translator import ClassifiedNode, NodeClassification

from n8n_to_sfn.models.asl import (
    ChoiceRule,
    ChoiceState,
    ItemProcessor,
    MapState,
    PassState,
    ProcessorConfig,
    TaskState,
    WaitState,
)
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    LambdaArtifact,
    LambdaRuntime,
    TranslationContext,
    TranslationResult,
    TriggerArtifact,
    TriggerType,
    apply_error_handling,
)

# ---------------------------------------------------------------------------
# n8n type constants
# ---------------------------------------------------------------------------

_TYPE_IF = "n8n-nodes-base.if"
_TYPE_SWITCH = "n8n-nodes-base.switch"
_TYPE_SPLIT_IN_BATCHES = "n8n-nodes-base.splitInBatches"
_TYPE_MERGE = "n8n-nodes-base.merge"
_TYPE_WAIT = "n8n-nodes-base.wait"
_TYPE_NOOP = "n8n-nodes-base.noOp"
_TYPE_LOOP = "n8n-nodes-base.loop"
_TYPE_EXECUTE_WORKFLOW = "n8n-nodes-base.executeWorkflow"

# ARN for synchronous nested execution (SDK integration pattern v2)
_EXECUTE_WORKFLOW_RESOURCE = "arn:aws:states:::states:startExecution.sync:2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _condition_for_if(node: ClassifiedNode) -> str:
    """
    Build a JSONata condition string from an n8n IF node's parameters.

    n8n IF nodes store conditions in ``parameters.conditions``.  Each condition
    has a ``leftValue``, ``operator``, and ``rightValue``.  When the raw
    parameter value is a plain string we emit it verbatim (it may already be a
    JSONata expression); otherwise we fall back to a passthrough truthy check.
    """
    params = node.node.parameters
    conditions = params.get("conditions", {})

    # n8n ≥ 1.x stores conditions under a typed collection key
    # e.g. {"conditions": {"options": {...}, "conditions": [...]}}
    inner_list: list[dict] = []
    if isinstance(conditions, dict):
        inner_list = conditions.get("conditions", [])
    elif isinstance(conditions, list):
        inner_list = conditions

    if not inner_list:
        # Fall back: treat the whole condition object as a truthy expression
        raw = params.get("value1", params.get("leftValue", "true"))
        return str(raw) if raw else "true"

    parts: list[str] = []
    for cond in inner_list:
        part = _single_condition_to_jsonata(cond)
        if part:
            parts.append(part)

    if not parts:
        return "true"
    return " and ".join(parts)


def _single_condition_to_jsonata(cond: dict) -> str:
    """Convert a single n8n condition dict to a JSONata boolean expression."""
    left = cond.get("leftValue", cond.get("value1", ""))
    right = cond.get("rightValue", cond.get("value2", ""))
    operator_obj = cond.get("operator", {})

    if isinstance(operator_obj, dict):
        op_type = operator_obj.get("type", "string")
        op_name = operator_obj.get("operation", "equals")
    else:
        # Legacy format: operator is a plain string
        op_type = "string"
        op_name = str(operator_obj) if operator_obj else "equals"

    left_expr = _wrap_if_expression(str(left))
    right_expr = _wrap_if_expression(str(right))

    return _build_comparison(left_expr, right_expr, op_type, op_name)


def _wrap_if_expression(value: str) -> str:
    """Wrap an n8n expression in JSONata syntax if needed."""
    stripped = value.strip()
    if stripped.startswith("{{") and stripped.endswith("}}"):
        return stripped[2:-2].strip().replace("$json", "$states.input")
    if stripped.startswith("="):
        return stripped[1:].strip().replace("$json", "$states.input")
    # Plain literal — quote strings for JSONata
    return (
        f'"{stripped}"'
        if stripped and not stripped.lstrip("-").replace(".", "").isdigit()
        else stripped
    )


# Operators that can be represented as simple binary symbols
_BINARY_OP_SYMBOLS: dict[str, str] = {
    "equals": "=",
    "notEquals": "!=",
    "larger": ">",
    "largerEqual": ">=",
    "smaller": "<",
    "smallerEqual": "<=",
}


def _build_unary_comparison(left: str, op_name: str) -> str | None:
    """Return a JSONata expression for unary operators, or None if not unary."""
    unary_map: dict[str, str] = {
        "true": f"{left} = true",
        "false": f"{left} = false",
        "empty": f'$string({left}) = ""',
        "notEmpty": f'$string({left}) != ""',
        "exists": f"$exists({left})",
        "notExists": f"$not($exists({left}))",
    }
    return unary_map.get(op_name)


def _build_functional_comparison(left: str, right: str, op_name: str) -> str | None:
    """Return a JSONata expression for function-style operators, or None if not applicable."""
    func_map: dict[str, str] = {
        "contains": f"$contains({left}, {right})",
        "notContains": f"$not($contains({left}, {right}))",
        "startsWith": f"$startsWith({left}, {right})",
        "endsWith": f"$endsWith({left}, {right})",
        "regex": f"$match({left}, {right})",
    }
    return func_map.get(op_name)


def _build_comparison(left: str, right: str, op_type: str, op_name: str) -> str:
    """Build a JSONata comparison expression from operator type and name."""
    unary = _build_unary_comparison(left, op_name)
    if unary is not None:
        return unary

    functional = _build_functional_comparison(left, right, op_name)
    if functional is not None:
        return functional

    operator_symbol = _BINARY_OP_SYMBOLS.get(op_name, "=")
    return f"{left} {operator_symbol} {right}"


def _next_state_for_output(
    node: ClassifiedNode, output_index: int, context: TranslationContext
) -> str | None:
    """Find the name of the state connected to a given output index of a node."""
    node_name = node.node.name
    for edge in context.analysis.dependency_edges:
        if edge.from_node == node_name and edge.output_index == output_index:
            return edge.to_node
    return None


def _build_switch_rules(
    node: ClassifiedNode, context: TranslationContext
) -> tuple[list[ChoiceRule], str | None]:
    """Build ChoiceRules and Default state name from a Switch node's parameters."""
    params = node.node.parameters
    rules: list[ChoiceRule] = []

    # n8n stores switch rules as a list under "rules" or "conditions"
    raw_rules: list[dict] = params.get("rules", {}).get("values", [])
    if not raw_rules:
        raw_rules = params.get("conditions", [])

    output_index = 0
    for raw_rule in raw_rules:
        next_state = _next_state_for_output(node, output_index, context)
        if next_state is None:
            output_index += 1
            continue

        condition = _rule_to_condition(raw_rule)
        rules.append(ChoiceRule(condition=condition, next=next_state))
        output_index += 1

    # Default branch: the last output index that has no explicit rule
    default_state = _next_state_for_output(node, output_index, context)

    return rules, default_state


def _rule_to_condition(rule: dict) -> str:
    """Convert a single Switch rule dict to a JSONata condition string."""
    value = rule.get("value1", rule.get("value", ""))
    operation = rule.get("operation", "equal")
    compare_value = rule.get("value2", rule.get("output", ""))

    left_expr = _wrap_if_expression(str(value))
    right_expr = _wrap_if_expression(str(compare_value))

    op_map: dict[str, str] = {
        "equal": "=",
        "notEqual": "!=",
        "larger": ">",
        "largerEqual": ">=",
        "smaller": "<",
        "smallerEqual": "<=",
    }
    symbol = op_map.get(operation, "=")
    return f"{left_expr} {symbol} {right_expr}"


# ---------------------------------------------------------------------------
# Node-specific translators
# ---------------------------------------------------------------------------


def _translate_if(
    node: ClassifiedNode, context: TranslationContext
) -> TranslationResult:
    """
    Translate an n8n IF node to a ChoiceState.

    The true branch is connected to output index 0 and the false branch to
    output index 1.
    """
    condition = _condition_for_if(node)
    true_state = _next_state_for_output(node, 0, context)
    false_state = _next_state_for_output(node, 1, context)

    choices: list[ChoiceRule] = []
    if true_state:
        choices.append(ChoiceRule(condition=condition, next=true_state))

    state = ChoiceState(
        choices=choices,
        default=false_state,
        comment=f"IF: {node.node.name}",
    )
    return TranslationResult(states={node.node.name: state})


def _translate_switch(
    node: ClassifiedNode, context: TranslationContext
) -> TranslationResult:
    """Translate an n8n Switch node to a ChoiceState with multiple rules."""
    rules, default_state = _build_switch_rules(node, context)

    # Ensure we always have at least one choice (required by ASL)
    if not rules:
        rules = [ChoiceRule(condition="true", next=default_state or node.node.name)]
        default_state = None

    state = ChoiceState(
        choices=rules,
        default=default_state,
        comment=f"Switch: {node.node.name}",
    )
    return TranslationResult(states={node.node.name: state})


def _translate_split_in_batches(
    node: ClassifiedNode, context: TranslationContext
) -> TranslationResult:
    """
    Translate an n8n SplitInBatches node to a MapState (MaxConcurrency=1).

    The inner processor is INLINE mode with a placeholder Pass state.  The
    engine's ``_apply_map_for_split_in_batches`` post-processing step detects
    the ``split_in_batches_node`` metadata and replaces the placeholder with
    the actual loop-body states collected from the dependency graph.
    """
    batch_size = int(node.node.parameters.get("batchSize", 10))

    processor_config = ProcessorConfig(mode="INLINE")
    placeholder_name = f"{node.node.name}_Item"
    item_processor = ItemProcessor(
        processor_config=processor_config,
        start_at=placeholder_name,
        states={
            placeholder_name: PassState(end=True, comment="Batch item placeholder")
        },
    )

    state = MapState(
        max_concurrency=1,
        item_processor=item_processor,
        comment=f"SplitInBatches (batch_size={batch_size}): {node.node.name}",
    )

    # The "done" output (index 0) goes to the next state after the loop.
    # The "loop" output (index 1) feeds back into the loop body.
    done_next = _next_state_for_output(node, 0, context)

    return TranslationResult(
        states={node.node.name: state},
        metadata={
            "split_in_batches_node": True,
            "batch_size": batch_size,
            "done_next": done_next,
        },
    )


def _translate_loop(
    node: ClassifiedNode, context: TranslationContext
) -> TranslationResult:
    """
    Translate an n8n Loop node to a Map state or Choice loop-back pattern.

    The Loop node supports two modes:

    - **Count-based** (``loopMode="count"``): produces a Map state that iterates
      over a generated array of the specified size, with ``MaxConcurrency=1`` to
      ensure sequential execution.
    - **Condition-based** (``loopMode="condition"``): produces a Choice state
      that evaluates a condition each iteration and loops back to the body or
      exits.  The engine's post-processing step detects the ``loop_node``
      metadata and wires up the loop-back edge.
    """
    params = node.node.parameters
    loop_mode = str(params.get("loopMode", "count"))

    # The "done" output (index 0) goes to the next state after the loop.
    done_next = _next_state_for_output(node, 0, context)

    if loop_mode == "condition":
        return _translate_loop_condition(node, context, done_next)
    return _translate_loop_count(node, context, done_next)


def _translate_loop_count(
    node: ClassifiedNode,
    context: TranslationContext,
    done_next: str | None,
) -> TranslationResult:
    """Translate a count-based Loop node to a Map state."""
    params = node.node.parameters
    loop_count = int(params.get("loopCount", 10))

    processor_config = ProcessorConfig(mode="INLINE")
    placeholder_name = f"{node.node.name}_Item"
    item_processor = ItemProcessor(
        processor_config=processor_config,
        start_at=placeholder_name,
        states={
            placeholder_name: PassState(end=True, comment="Loop body placeholder")
        },
    )

    state = MapState(
        items_path="{% $range($states.input.loopCount) %}",
        max_concurrency=1,
        item_processor=item_processor,
        comment=f"Loop (count={loop_count}): {node.node.name}",
    )

    return TranslationResult(
        states={node.node.name: state},
        metadata={
            "loop_node": True,
            "loop_mode": "count",
            "loop_count": loop_count,
            "done_next": done_next,
        },
    )


def _translate_loop_condition(
    node: ClassifiedNode,
    context: TranslationContext,
    done_next: str | None,
) -> TranslationResult:
    """Translate a condition-based Loop node to a Choice + loop-back pattern."""
    params = node.node.parameters
    condition = str(params.get("condition", "true"))

    # The loop body is connected to output index 1
    loop_body = _next_state_for_output(node, 1, context)
    exit_name = done_next or f"{node.node.name}_Exit"

    choices: list[ChoiceRule] = []
    if loop_body:
        choices.append(ChoiceRule(condition=condition, next=loop_body))

    state = ChoiceState(
        choices=choices,
        default=exit_name,
        comment=f"Loop (condition): {node.node.name}",
    )

    states: dict[str, object] = {node.node.name: state}

    # If there is no downstream "done" state, emit a terminal Pass state as the
    # exit target so the ASL remains valid.
    if done_next is None:
        states[exit_name] = PassState(end=True, comment="Loop exit")

    return TranslationResult(
        states=states,
        metadata={
            "loop_node": True,
            "loop_mode": "condition",
            "condition": condition,
            "loop_body": loop_body,
            "done_next": done_next,
        },
    )


def _translate_merge(
    node: ClassifiedNode, context: TranslationContext
) -> TranslationResult:
    """
    Translate an n8n Merge node.

    A Merge node joins multiple upstream branches.  In Step Functions this
    requires a Parallel state wrapping the upstream branches so their outputs
    can be combined.  Here we emit a PassState placeholder; the engine's
    ``_apply_parallel_for_merges`` post-processing step detects merge metadata
    and replaces the fork-to-merge region with a proper Parallel state.
    """
    params = node.node.parameters
    merge_mode = str(params.get("mode", "append"))

    state = PassState(comment=f"Merge placeholder: {node.node.name}")
    return TranslationResult(
        states={node.node.name: state},
        metadata={
            "merge_node": True,
            "merge_mode": merge_mode,
        },
    )


_CALLBACK_RESOURCE = "arn:aws:states:::lambda:invoke.waitForTaskToken"
_DEFAULT_CALLBACK_TIMEOUT = 86400  # 24 hours


def _translate_wait(
    node: ClassifiedNode, context: TranslationContext
) -> TranslationResult:
    """
    Translate an n8n Wait node to a WaitState or callback TaskState.

    Supported wait modes and their ASL equivalents:

    - ``timeValue`` / ``unit``   → ``Seconds`` (converted to seconds)
    - ``dateTime``               → ``Timestamp``
    - ``secondsReference``       → ``SecondsPath``
    - ``dateTimeReference``      → ``TimestampPath``
    - ``n8nFormSubmission``      → callback TaskState (``.waitForTaskToken``)
    - ``webhook``                → callback TaskState (``.waitForTaskToken``)
    """
    params = node.node.parameters
    resume = params.get("resume", "timeInterval")

    if resume in ("n8nFormSubmission", "webhook"):
        return _translate_wait_callback(node, resume)

    seconds: int | None = None
    timestamp: str | None = None
    seconds_path: str | None = None
    timestamp_path: str | None = None

    if resume == "timeInterval":
        amount = int(params.get("amount", params.get("timeValue", 1)))
        unit = str(params.get("unit", "seconds")).lower()
        unit_to_seconds: dict[str, int] = {
            "seconds": 1,
            "minutes": 60,
            "hours": 3600,
            "days": 86400,
        }
        seconds = amount * unit_to_seconds.get(unit, 1)
    elif resume == "specificTime":
        timestamp = str(params.get("dateTime", ""))
    elif _is_expression(str(params.get("amount", ""))):
        seconds_path = _to_reference_path(str(params.get("amount", "")))
    elif _is_expression(str(params.get("dateTime", ""))):
        timestamp_path = _to_reference_path(str(params.get("dateTime", "")))
    else:
        seconds = int(params.get("amount", 1))

    state = WaitState(
        seconds=seconds,
        timestamp=timestamp if timestamp else None,
        seconds_path=seconds_path,
        timestamp_path=timestamp_path,
        comment=f"Wait: {node.node.name}",
    )
    return TranslationResult(states={node.node.name: state})


def _translate_wait_callback(
    node: ClassifiedNode, resume: str
) -> TranslationResult:
    """
    Translate a form-submission or webhook wait into a callback TaskState.

    Uses ``.waitForTaskToken`` so the state machine pauses until a Lambda
    function calls ``SendTaskSuccess`` with the submitted data.
    """
    params = node.node.parameters
    node_name = node.node.name
    safe_name = node_name.replace(" ", "_")

    is_form = resume == "n8nFormSubmission"
    handler_kind = "form" if is_form else "webhook"

    timeout = int(params.get("timeoutSeconds", _DEFAULT_CALLBACK_TIMEOUT))

    # --- Build the form/webhook config passed to the handler Lambda ----------
    callback_config: dict[str, object] = {"resumeType": resume}
    if is_form:
        callback_config["formFields"] = params.get("formFields", {})
        callback_config["formTitle"] = params.get("formTitle", node_name)
        callback_config["formDescription"] = params.get("formDescription", "")

    # --- ASL callback Task state ---------------------------------------------
    state = TaskState(
        resource=_CALLBACK_RESOURCE,
        arguments={
            "FunctionName": f"${{{safe_name}_{handler_kind}_handler}}",
            "Payload": {
                "taskToken.$": "$$.Task.Token",
                f"{handler_kind}Config": callback_config,
            },
        },
        timeout_seconds=timeout,
        comment=f"Wait ({handler_kind} callback): {node_name}",
    )
    apply_error_handling(state, node)

    # --- Lambda artifact for the handler -------------------------------------
    handler_code = _callback_handler_code(handler_kind)
    lambda_artifact = LambdaArtifact(
        function_name=f"{safe_name}_{handler_kind}_handler",
        runtime=LambdaRuntime.PYTHON,
        handler_code=handler_code,
        dependencies=["boto3"],
        directory_name=f"{safe_name}_{handler_kind}_handler",
    )

    # --- Trigger artifact (Lambda Function URL) ------------------------------
    trigger_artifact = TriggerArtifact(
        trigger_type=TriggerType.LAMBDA_FURL,
        config={
            "handler_kind": handler_kind,
            "source_node": node_name,
        },
        lambda_artifact=lambda_artifact,
    )

    return TranslationResult(
        states={node_name: state},
        lambda_artifacts=[lambda_artifact],
        trigger_artifacts=[trigger_artifact],
        metadata={
            "callback_node": True,
            "resume_type": resume,
            "timeout_seconds": timeout,
        },
    )


def _callback_handler_code(handler_kind: str) -> str:
    """Return the Python handler code for a callback Lambda."""
    return f'''\
"""Auto-generated {handler_kind} callback handler.

Receives a {handler_kind} submission via Lambda Function URL and calls
SendTaskSuccess to resume the waiting Step Functions execution.
"""

import json
import boto3

sfn = boto3.client("stepfunctions")


def handler(event, context):
    """Handle {handler_kind} submission and resume Step Functions execution."""
    # When invoked by Step Functions with .waitForTaskToken the task token
    # arrives in the payload.  When invoked via Function URL the token must
    # be stored/retrieved externally (e.g. DynamoDB mapping).
    body = event
    if "body" in event:
        # Lambda Function URL invocation
        raw = event["body"]
        body = json.loads(raw) if isinstance(raw, str) else raw

    task_token = body.get("taskToken") or event.get("taskToken")
    if not task_token:
        return {{
            "statusCode": 400,
            "body": json.dumps({{"error": "Missing taskToken"}}),
        }}

    # Extract the submitted data (everything except the token)
    submission = {{k: v for k, v in body.items() if k != "taskToken"}}

    sfn.send_task_success(
        taskToken=task_token,
        output=json.dumps(submission),
    )

    return {{
        "statusCode": 200,
        "body": json.dumps({{"message": "{handler_kind} submission received"}}),
    }}
'''


def _is_expression(value: str) -> bool:
    """Return True if the value looks like an n8n expression reference."""
    return value.startswith("{{") or value.startswith("=")


def _to_reference_path(value: str) -> str:
    """Convert an n8n expression to a JSONata reference path for WaitState."""
    stripped = value.strip()
    if stripped.startswith("{{") and stripped.endswith("}}"):
        inner = stripped[2:-2].strip()
        return inner.replace("$json", "$states.input")
    if stripped.startswith("="):
        return stripped[1:].strip().replace("$json", "$states.input")
    return stripped


def _translate_noop(
    node: ClassifiedNode, context: TranslationContext
) -> TranslationResult:
    """Translate an n8n NoOp node to a PassState."""
    state = PassState(comment=f"NoOp: {node.node.name}")
    return TranslationResult(states={node.node.name: state})


def _translate_execute_workflow(
    node: ClassifiedNode, context: TranslationContext
) -> TranslationResult:
    """
    Translate an n8n Execute Workflow node to a TaskState.

    Uses the ``startExecution.sync:2`` SDK integration so Step Functions waits
    for the child execution to complete before continuing.

    The child state machine ARN is emitted as a JSONata placeholder that
    references ``$states.context.sub_workflow_arns['<id>']``.  The Packager
    resolves this at deploy time — same-stack via a direct CDK reference, or
    cross-stack via an SSM Parameter lookup.
    """
    params = node.node.parameters
    workflow_id = params.get("workflowId", {})

    # workflowId may be a plain string or a dict with a "value" key
    if isinstance(workflow_id, dict):
        wf_id_value = workflow_id.get("value", "")
    else:
        wf_id_value = str(workflow_id)

    arguments: dict[str, object] = {
        "Input": "{% $states.input %}",
    }
    if wf_id_value:
        # Emit a JSONata expression referencing the context-injected ARN map.
        # The Packager populates sub_workflow_arns in the execution context at
        # deploy time so this resolves to a real state machine ARN.
        arguments["StateMachineArn"] = (
            "{% $states.context.sub_workflow_arns['"
            + wf_id_value
            + "'] %}"
        )

    state = TaskState(
        resource=_EXECUTE_WORKFLOW_RESOURCE,
        arguments=arguments,
        comment=f"Execute Workflow: {node.node.name}",
    )
    apply_error_handling(state, node)

    warnings: list[str] = [
        f"Execute Workflow node '{node.node.name}': the child workflow ARN "
        f"(id='{wf_id_value}') must be resolved by the Packager.  "
        "Same-stack: use a direct CDK StateMachine reference.  "
        "Cross-stack: use an SSM Parameter at "
        f"/phaeton/workflows/{wf_id_value}/arn.",
    ]

    metadata: dict[str, object] = {}
    if wf_id_value:
        metadata["sub_workflow_references"] = [wf_id_value]

    return TranslationResult(
        states={node.node.name: state},
        warnings=warnings,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, object] = {
    _TYPE_IF: _translate_if,
    _TYPE_SWITCH: _translate_switch,
    _TYPE_SPLIT_IN_BATCHES: _translate_split_in_batches,
    _TYPE_LOOP: _translate_loop,
    _TYPE_MERGE: _translate_merge,
    _TYPE_WAIT: _translate_wait,
    _TYPE_NOOP: _translate_noop,
    _TYPE_EXECUTE_WORKFLOW: _translate_execute_workflow,
}


# ---------------------------------------------------------------------------
# Public translator class
# ---------------------------------------------------------------------------


class FlowControlTranslator(BaseTranslator):
    """
    Translator for n8n flow control nodes.

    Handles IF, Switch, SplitInBatches, Loop, Merge, Wait, NoOp, and Execute
    Workflow nodes, converting each to an appropriate ASL state type.
    """

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True when the node is classified as FLOW_CONTROL."""
        return node.classification == NodeClassification.FLOW_CONTROL

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """
        Dispatch translation to the handler for this node type.

        Falls back to a PassState with a warning for unrecognised node types
        so that the overall translation can continue rather than failing hard.
        """
        handler = _DISPATCH.get(node.node.type)
        if handler is None:
            return self._translate_unknown(node)

        # All handler functions share the same signature
        return handler(node, context)  # type: ignore[operator]

    def _translate_unknown(self, node: ClassifiedNode) -> TranslationResult:
        """Produce a PassState placeholder for unrecognised flow control nodes."""
        state = PassState(comment=f"Unrecognised flow control: {node.node.type}")
        return TranslationResult(
            states={node.node.name: state},
            warnings=[
                f"FlowControlTranslator: no handler for node type '{node.node.type}' "
                f"(node '{node.node.name}').  Emitting a PassState placeholder."
            ],
        )
