# Form Trigger Resumable Workflows

**Priority:** P2
**Effort:** L
**Gap Analysis Ref:** Item #26

## Overview

The Form trigger (`n8n-nodes-base.formTrigger`) creates workflows that pause for human input. Step Functions supports this via callback patterns (`.waitForTaskToken`), but the current Wait translator (`_translate_wait` in `flow_control.py` lines 339-375) sets `seconds = 0` for form submissions and webhooks -- producing a degenerate WaitState that completes immediately rather than pausing for human input.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The Form trigger produces a Step Functions callback pattern using `.waitForTaskToken`.
2. A Lambda function URL is generated to receive the form submission.
3. The Lambda handler calls `SendTaskSuccess` with the form data when the user submits.
4. The state machine pauses at the callback state until the form is submitted.
5. A timeout is configurable for how long the workflow waits for human input.
6. The Wait translator handles `"n8nFormSubmission"` and `"webhook"` resume types with proper callback infrastructure.
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py`
- `n8n-to-sfn/tests/test_form_trigger.py` (new)

### Technical Approach

1. **Callback pattern in ASL:**
   ```json
   {
     "Type": "Task",
     "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
     "Parameters": {
       "FunctionName": "${FormHandlerLambda}",
       "Payload": {
         "taskToken.$": "$$.Task.Token",
         "formConfig": { ... }
       }
     },
     "TimeoutSeconds": 86400
   }
   ```

2. **Modify `_translate_wait`** (line 339):
   - For `resume == "n8nFormSubmission"`:
     - Create a `TaskState` with `.waitForTaskToken` resource instead of a `WaitState` with 0 seconds.
     - Generate a `LambdaArtifact` for the form handler.
     - Generate a `TriggerArtifact` with `trigger_type=TriggerType.LAMBDA_FURL` for the form submission endpoint.
   - For `resume == "webhook"`:
     - Similar pattern: `.waitForTaskToken` with a webhook handler Lambda.

3. **Form handler Lambda:**
   - Serves an HTML form or accepts form POST data.
   - Extracts the task token from the request or a pre-stored mapping.
   - Calls `sfn.send_task_success(taskToken=token, output=form_data)`.

4. **Timeout handling:**
   - Default timeout: 24 hours (86400 seconds).
   - Configurable via n8n node parameters if available.
   - `TimeoutSeconds` on the Task state handles automatic expiration.

### Testing Requirements

- Test form trigger translation produces a callback Task state.
- Test webhook trigger translation produces a callback Task state.
- Test that a Lambda artifact is generated for the form handler.
- Test timeout configuration.
- Validate the generated ASL is valid.
