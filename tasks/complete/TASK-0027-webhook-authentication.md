# Webhook Authentication

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #27

## Overview

All webhook and callback handler Lambda Function URLs use `FunctionUrlAuthType.NONE` (in `cdk_writer.py` lines 324-336), making them publicly accessible without authentication. `AWS_IAM` auth is not appropriate since webhook callers are external services. Authentication must be implemented within the Lambda function handler itself -- e.g., HMAC signature verification, API key validation, or bearer token checking depending on the webhook source. The Function URL remains `NONE` auth, but the handler code must validate incoming requests.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. Generated webhook/callback Lambda handler code includes request authentication logic.
2. At minimum, API key validation is supported (key stored in SSM, compared against request header).
3. HMAC signature verification is supported for services that send signed webhooks (e.g., Slack, GitHub).
4. Unauthenticated requests return a 401/403 response.
5. Authentication configuration is driven by the webhook trigger's credential information.
6. A `CredentialArtifact` is generated for the webhook authentication secret.
7. `uv run pytest` passes in `packager/`.
8. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`
- `packager/src/n8n_to_sfn_packager/templates/` (Lambda handler templates, if they exist)
- `packager/tests/` (update/add tests)

### Technical Approach

1. **Handler-level authentication:**
   - The Function URL auth type remains `FunctionUrlAuthType.NONE` (external callers can't use IAM).
   - Authentication logic is added to the generated Lambda handler code.

2. **API key validation pattern:**
   ```python
   import boto3
   ssm = boto3.client("ssm")

   def handler(event, context):
       api_key = ssm.get_parameter(Name="/phaeton/webhooks/api-key", WithDecryption=True)
       request_key = event["headers"].get("x-api-key", "")
       if request_key != api_key["Parameter"]["Value"]:
           return {"statusCode": 401, "body": "Unauthorized"}
       # ... process webhook
   ```

3. **HMAC signature verification pattern:**
   ```python
   import hmac, hashlib
   def verify_signature(payload, signature, secret):
       expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
       return hmac.compare_digest(f"sha256={expected}", signature)
   ```

4. **CDK writer changes** (in `_wf_lambda_functions`, lines 324-336):
   - When generating webhook/callback handlers, check if authentication credentials are associated.
   - If credentials exist, inject the authentication logic into the generated handler code.
   - Add the SSM parameter path to the Lambda's environment variables.
   - Add SSM `GetParameter` permission to the Lambda's IAM role.

### Testing Requirements

- Test that generated webhook handler includes authentication logic when credentials are provided.
- Test API key validation with correct and incorrect keys.
- Test HMAC signature verification.
- Test that unauthenticated handlers are still generated when no credentials are associated.
