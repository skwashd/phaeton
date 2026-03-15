# Eventbridge Schedule Targets

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #5

## Overview

The `_wf_triggers()` static method in `cdk_writer.py` generates `events.Rule(...)` constructs for EventBridge schedule triggers but does not attach any targets. The generated code contains only a comment placeholder `# Target should reference the state machine`. The `aws_events_targets` module is imported in generated output but never used. The resulting EventBridge rules will exist in AWS and fire on schedule but invoke nothing.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0006, TASK-0007

## Acceptance Criteria

1. Generated CDK code for schedule triggers includes `targets=[events_targets.SfnStateMachine(state_machine)]` on every `events.Rule` construct.
2. The `state_machine` variable reference is correctly scoped in the generated CDK stack.
3. Generated CDK code passes `cdk synth` without errors (if CDK is available in the test environment).
4. The `aws_events_targets` import in generated code is actually used.
5. `uv run pytest` passes in `packager/`.
6. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`

### Technical Approach

1. In `_wf_triggers` (line 412), within the loop that generates schedule rules (lines 423-430):
   - Replace the comment `# Target should reference the state machine` with an actual `targets` parameter.
   - The generated code should emit:
     ```python
     rule.add_target(events_targets.SfnStateMachine(state_machine))
     ```
     or include `targets=[events_targets.SfnStateMachine(state_machine)]` directly in the `events.Rule(...)` constructor.
   - Ensure the `state_machine` CDK construct variable is accessible in the generated scope. It is typically defined earlier in the stack as the `sfn.StateMachine` construct.

2. Verify that the `_wf_triggers` method receives or can reference the state machine construct name. If not, update its signature or the calling context to pass the state machine variable name.

3. The `events_targets` import (`from aws_cdk import aws_events_targets as events_targets`) should already be present in generated output (line 206 of generated code); confirm it is emitted.

### Testing Requirements

- Update existing tests for `_wf_triggers` to verify the generated code includes a target.
- Add a test that parses the generated CDK code string and asserts `SfnStateMachine` appears.
- If snapshot/golden-file tests exist, update them to reflect the new target code.
