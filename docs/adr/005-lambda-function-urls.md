# ADR-005: Lambda Function URLs for Webhooks

**Status:** Accepted
**Date:** 2025-06-01

## Context

n8n webhook nodes require public HTTP endpoints that receive incoming requests and trigger workflow execution. When translating these to AWS, the pipeline needs to generate infrastructure that exposes an HTTPS endpoint, receives the request payload, and starts a Step Functions execution.

Two main options were considered:
- **API Gateway** (REST or HTTP API) — the traditional AWS approach for exposing Lambda functions over HTTP, offering custom domains, request validation, rate limiting, and usage plans.
- **Lambda Function URLs** — a lightweight alternative that assigns a dedicated HTTPS endpoint directly to a Lambda function, with no additional infrastructure.

## Decision

Use Lambda Function URLs (`add_function_url()` on the CDK Lambda construct) instead of API Gateway for webhook endpoints. The generated CDK code configures:

- `FunctionUrlAuthType.NONE` for public webhook access.
- A Lambda handler that extracts the request body, headers, and query parameters, wraps them in a `webhook_event` object, and calls `sfn.start_execution()` to trigger the state machine.

The webhook trigger is represented as a `TriggerArtifact` with `trigger_type = LAMBDA_FURL` in the translation output and mapped to `TriggerType.WEBHOOK` in the packager input.

## Consequences

### Positive
- Simpler infrastructure — no API Gateway resource, stage, or deployment to manage.
- Lower cost — Function URLs have no per-request charge beyond the Lambda invocation itself.
- Faster CDK synthesis — fewer constructs to synthesize and deploy.
- Each webhook gets its own isolated URL, avoiding routing complexity.

### Negative
- Function URLs use randomly assigned AWS domains (e.g., `https://xxxx.lambda-url.us-east-1.on.aws`), which are not human-friendly. Custom domain support is deferred to a future task.
- No built-in request validation, rate limiting, or usage plans — these would need to be implemented in the Lambda handler if required.
- `AuthType.NONE` means the endpoint is publicly accessible with no authentication. Webhook authentication (e.g., HMAC signature verification) must be implemented in the handler code.

### Neutral
- Custom domain mapping via CloudFront or API Gateway can be layered on top of Function URLs later without changing the underlying Lambda architecture.
- The webhook handler template is generated as a Lambda artifact, so authentication logic can be added to the template as webhook authentication support is implemented.
