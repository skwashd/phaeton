# Observability Xray Instrumentation

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #10

## Overview

The generated CDK stack lacks comprehensive observability. AWS X-Ray must be enabled across the entire stack to provide distributed tracing through Step Functions, Lambda functions, and SDK calls. Without X-Ray instrumentation, debugging failures across the multi-service execution flow is impractical.

Missing observability:
- **Step Functions:** X-Ray tracing not enabled on state machines (`tracing_enabled=True`).
- **Lambda functions:** Active tracing not enabled, AWS SDK not instrumented with X-Ray SDK.
- **Dead Letter Queues:** No SQS DLQs on state machines or Lambda functions for failed execution capture.
- **CloudWatch Alarms:** No alarms for `ExecutionsFailed`, `ExecutionsTimedOut`, `ExecutionThrottled` metrics.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. Generated CDK code includes `tracing_enabled=True` on all `sfn.StateMachine` constructs.
2. Generated Lambda functions include `tracing=lambda_.Tracing.ACTIVE`.
3. Generated Lambda function code includes X-Ray SDK instrumentation for AWS SDK calls (e.g., `aws-xray-sdk` for Python, `aws-xray-sdk-core` for Node.js).
4. Generated CDK code creates SQS DLQ constructs and attaches them to state machines and Lambda functions.
5. Generated CDK code creates CloudWatch Alarms for `ExecutionsFailed`, `ExecutionsTimedOut`, and `ExecutionThrottled` metrics on each state machine.
6. `uv run pytest` passes in `packager/`.
7. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`

### Technical Approach

1. **Step Functions X-Ray tracing:**
   - In the state machine construct generation, add `tracing_enabled=True` parameter.
   - The `CDKWriter.write` method (line 27) generates the state machine construct; find and update that section.

2. **Lambda X-Ray tracing:**
   - In `_wf_lambda_functions`, add `tracing=lambda_.Tracing.ACTIVE` to each `lambda_.Function` construct.
   - For Python Lambdas, add `aws-xray-sdk` to the function's requirements/dependencies.
   - For Node.js Lambdas, add `aws-xray-sdk-core` to the function's `package.json` dependencies.

3. **Dead Letter Queues:**
   - Generate an `sqs.Queue` construct for the DLQ.
   - Attach to state machine via `sfn.StateMachine(..., dead_letter_queue=dlq)` (or the CDK equivalent for Step Functions).
   - Attach to Lambda functions via `lambda_.Function(..., dead_letter_queue=dlq)`.

4. **CloudWatch Alarms:**
   - After the state machine construct, generate `cloudwatch.Alarm` constructs:
     ```python
     state_machine.metric_failed().create_alarm(self, "FailedAlarm", ...)
     state_machine.metric_timed_out().create_alarm(self, "TimedOutAlarm", ...)
     state_machine.metric_throttled().create_alarm(self, "ThrottledAlarm", ...)
     ```

### Testing Requirements

- Update CDK writer tests to verify generated code includes X-Ray, DLQ, and alarm constructs.
- Test that generated Lambda functions include tracing configuration.
- Test that generated state machine includes `tracing_enabled=True`.
- Assert generated code includes all required CDK imports (`aws_sqs`, `aws_cloudwatch`).
