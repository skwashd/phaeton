# Eventbridge Oauth Rotation Targets

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #6

## Overview

The `_wf_oauth_rotation()` static method in `cdk_writer.py` generates EventBridge schedule rules for OAuth token refresh but leaves a comment placeholder (`# Target: oauth_refresh Lambda for {cred_name}`) instead of attaching a Lambda target. No `targets.LambdaFunction(...)` call is ever emitted, so the rotation schedule fires into the void. OAuth tokens will expire and never be refreshed, breaking any workflow that uses OAuth-authenticated services.

## Dependencies

- **Blocked by:** TASK-0005 (same pattern, implement schedule targets first)
- **Blocks:** TASK-0007

## Acceptance Criteria

1. Generated CDK code for OAuth rotation rules includes `targets=[events_targets.LambdaFunction(oauth_refresh_lambda)]` on every `events.Rule` construct.
2. The OAuth refresh Lambda function construct is defined in the generated CDK stack and referenced correctly.
3. Each OAuth credential produces a rotation rule that targets its corresponding Lambda function.
4. The `cred_name` extracted from `oauth.credential_spec.parameter_path` (last segment) is used to name the rule and Lambda function.
5. `uv run pytest` passes in `packager/`.
6. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`

### Technical Approach

1. In `_wf_oauth_rotation` (line 434), within the loop (lines 444-453):
   - Replace the comment `# Target: oauth_refresh Lambda for {cred_name}` with an actual target attachment.
   - The generated code should emit:
     ```python
     rule.add_target(events_targets.LambdaFunction(oauth_refresh_fn))
     ```
   - The `oauth_refresh_fn` Lambda construct should be defined earlier in the generated code, either as part of the `_wf_lambda_functions` output (for `LambdaFunctionType.OAUTH_REFRESH` functions) or created inline.

2. Ensure the Lambda function for OAuth refresh:
   - Has the correct runtime and handler.
   - Has IAM permissions to read/write the SSM parameter (the token path).
   - Has the SSM parameter path and token endpoint URL passed as environment variables.

3. The `refresh_schedule_expression` from `OAuthCredentialSpec` (default `"rate(50 minutes)"`) should be used as the schedule expression for the rule.

### Testing Requirements

- Update existing tests for `_wf_oauth_rotation` to verify the generated code includes Lambda targets.
- Add a test with multiple OAuth credentials to verify each gets its own rule and Lambda target.
- Assert the generated code references the correct Lambda function variable for each credential.
