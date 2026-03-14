# Http Request Node

**Priority:** P2
**Effort:** L
**Gap Analysis Ref:** Item #20

## Overview

The HTTP Request node (`n8n-nodes-base.httpRequest`) is the most commonly used node in n8n workflows. It requires translation to either API Gateway + Lambda or direct SDK `HttpInvoke` patterns. Supporting authentication modes (API key, OAuth2, bearer token) adds complexity. Without this translator, a large percentage of real-world n8n workflows cannot be converted.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0023 (SaaS integrations may reuse HTTP request patterns)

## Acceptance Criteria

1. A new translator class `HttpRequestTranslator` exists that handles `n8n-nodes-base.httpRequest` nodes.
2. The translator maps HTTP methods (GET, POST, PUT, DELETE, PATCH) to appropriate Step Functions states.
3. Simple HTTP requests (no auth) are translated to `TaskState` with `arn:aws:states:::http:invoke`.
4. API key authentication is supported via SSM parameter lookup for the key value.
5. Bearer token authentication is supported via SSM parameter lookup.
6. OAuth2 authentication is supported via credential artifacts and SSM parameters.
7. Request headers, query parameters, and body are correctly mapped from n8n parameters to the HTTP invoke configuration.
8. Response handling maps HTTP response data to the state output.
9. `uv run pytest` passes in `n8n-to-sfn/`.
10. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/http_request.py` (new)
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` (register new translator)
- `n8n-to-sfn/tests/test_http_request_translator.py` (new)

### Technical Approach

1. **HTTP Invoke state** (Step Functions native HTTP integration):
   ```json
   {
     "Type": "Task",
     "Resource": "arn:aws:states:::http:invoke",
     "Parameters": {
       "ApiEndpoint": "<url>",
       "Method": "<GET|POST|...>",
       "Headers": { ... },
       "RequestBody": { ... },
       "Authentication": {
         "ConnectionArn": "<EventBridge connection ARN>"
       }
     }
   }
   ```

2. **Lambda fallback** for complex cases:
   - If the HTTP request uses features not supported by the HTTP invoke integration (e.g., complex auth flows, response streaming), fall back to a Lambda function.
   - The Lambda function uses `axios` (Node.js) or `httpx` (Python) to make the request.

3. **Authentication mapping:**
   - `n8n auth type: "apiKey"` -> `CredentialArtifact` with SSM parameter, injected as header or query param.
   - `n8n auth type: "oAuth2"` -> `OAuthCredentialSpec` with token refresh.
   - `n8n auth type: "bearerToken"` -> `CredentialArtifact` with SSM parameter, injected as `Authorization: Bearer` header.

4. **Parameter mapping from n8n:**
   - URL: `node.parameters.url`
   - Method: `node.parameters.method` (default `GET`)
   - Headers: `node.parameters.headerParameters`
   - Query: `node.parameters.queryParameters`
   - Body: `node.parameters.bodyParameters` or `node.parameters.jsonBody`

### Testing Requirements

- Test simple GET request translation.
- Test POST request with JSON body.
- Test each authentication mode (API key, bearer token, OAuth2).
- Test with custom headers and query parameters.
- Validate generated ASL is valid.
