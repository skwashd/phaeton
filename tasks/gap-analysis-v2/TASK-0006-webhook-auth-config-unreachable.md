# Webhook Auth Config Unreachable

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #6

## Overview

Lambda Function URLs for webhook/callback handlers use `FunctionUrlAuthType.NONE` at `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py:564`. This is correct — `AWS_IAM` auth is inappropriate for external webhook callers, so authentication must be enforced within the Lambda handler code itself. The packager supports this via `webhook_auth` in the local `LambdaFunctionSpec`, which can generate HMAC, API key, or bearer token validation in the handler.

However, the shared `phaeton_models.packager_input.LambdaFunctionSpec` has no `webhook_auth` field, so this authentication configuration is unreachable through the orchestration pipeline. When the source n8n workflow has webhook authentication configured, it cannot flow through to the generated handler.

This issue is resolved by TASK-0002 — once `WebhookAuthConfig` and the `webhook_auth` field are promoted to the shared model, the adapter can carry authentication config through the pipeline. This task adds the warning behavior when no auth is configured.

## Dependencies

- **Blocked by:** TASK-0002 (shared PackagerInput must include `WebhookAuthConfig` first)
- **Blocks:** None

## Acceptance Criteria

1. After TASK-0002 promotes `WebhookAuthConfig` to the shared model, the `webhook_auth` field flows through the orchestration pipeline.
2. The packager emits a warning (not an error) when a webhook handler has no auth configured, surfacing the decision for user review.
3. The warning appears in the packager's conversion report or log output.
4. Webhook handlers with auth configured correctly generate authentication validation code.
5. `uv run pytest` passes in `packager/`.
6. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py` — add warning for unauthenticated webhooks
- `packager/src/n8n_to_sfn_packager/writers/lambda_writer.py` — verify auth code generation works with shared model

### Technical Approach

1. **Add warning emission:** In `cdk_writer.py`, when generating a Lambda Function URL with `FunctionUrlAuthType.NONE`, check if the corresponding `LambdaFunctionSpec` has `webhook_auth` configured. If not, emit a warning to the conversion report:
   ```python
   if func_spec.is_webhook and not func_spec.webhook_auth:
       warnings.append(
           f"Webhook handler '{func_spec.function_name}' has no authentication "
           f"configured. The Function URL will be publicly accessible."
       )
   ```

2. **Verify auth flow:** Confirm that when `webhook_auth` is present in the shared model (after TASK-0002), the packager's `lambda_writer.py` generates the correct authentication validation code in the handler (HMAC, API key, or bearer token checks).

3. **Conversion report integration:** Ensure the warning surfaces in the packager's output report so pipeline consumers (e.g., the deployment adapter) can expose it to users.

### Testing Requirements

- `packager/tests/test_cdk_writer.py` — test that a webhook handler without auth generates a warning in the report.
- `packager/tests/test_cdk_writer.py` — test that a webhook handler with auth does not generate a warning.
- `packager/tests/test_lambda_writer.py` — test that auth validation code is generated when `webhook_auth` is present.
