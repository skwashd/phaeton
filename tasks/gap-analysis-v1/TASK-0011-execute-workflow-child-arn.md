# Execute Workflow Child Arn

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #11

## Overview

The `_translate_execute_workflow` handler in `flow_control.py` emits a `TaskState` with a Jinja-style placeholder for the child state machine ARN:

```python
"StateMachineArn": "{{ WorkflowArn['<workflow-id>'] }}"
```

This is not valid ASL and will fail at deploy time. The ARN must resolve to an actual state machine ARN, either via CDK context variables (same-stack) or SSM Parameters (cross-stack).

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The `_translate_execute_workflow` function (line 415 in `flow_control.py`) emits a valid ASL `TaskState` with a resolvable `StateMachineArn`.
2. For same-stack references, the ARN uses a CDK context variable pattern that resolves at synth time.
3. For cross-stack references, the ARN uses an SSM Parameter lookup pattern.
4. The `TranslationResult` includes metadata indicating the child workflow reference for downstream resolution by the Packager.
5. `uv run pytest` passes in `n8n-to-sfn/`.
6. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py`
- `n8n-to-sfn/tests/` (update/add tests for execute workflow translation)

### Technical Approach

1. In `_translate_execute_workflow` (line 415):
   - Extract the `workflowId` from `node.node.parameters` (handles dict or plain string, already done in current code).
   - Instead of emitting `"{{ WorkflowArn['id'] }}"`, emit a well-known placeholder pattern that the Packager can resolve:
     ```python
     "StateMachineArn.$": "{% $states.context.sub_workflow_arns['" + workflow_id + "'] %}"
     ```
   - Add the workflow ID to `TranslationResult.metadata` under a `sub_workflow_references` key so the Packager knows which child workflows need resolution.

2. The Packager should later resolve these references using:
   - **Same-stack:** `sfn.StateMachine.from_state_machine_arn()` or direct CDK reference.
   - **Cross-stack:** `ssm.StringParameter.value_for_string_parameter(self, f"/phaeton/workflows/{workflow_id}/arn")`.

3. Update the `_EXECUTE_WORKFLOW_RESOURCE` constant (line 47) if needed: `"arn:aws:states:::states:startExecution.sync:2"`.

### Testing Requirements

- Test `_translate_execute_workflow` with a workflow ID produces a valid, resolvable ARN pattern.
- Test that `TranslationResult.metadata` includes the sub-workflow reference.
- Test both dict-style and string-style `workflowId` parameters.
