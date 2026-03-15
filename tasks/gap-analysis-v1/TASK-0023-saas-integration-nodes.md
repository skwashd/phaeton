# Saas Integration Nodes

**Priority:** P2
**Effort:** XL
**Gap Analysis Ref:** Item #23

## Overview

Nodes for Slack, Gmail, Google Sheets, Notion, Airtable, and dozens of other SaaS services are not supported. The PicoFun API strategy (wrapping each integration behind an API call) may address this at scale, but the PicoFun infrastructure itself does not exist yet. This is the largest coverage gap and affects the majority of real-world n8n workflows.

## Dependencies

- **Blocked by:** TASK-0020 (HTTP Request node provides the foundation for SaaS API calls)
- **Blocks:** None

## Acceptance Criteria

1. A framework exists for adding SaaS integration translators using a common pattern.
2. At minimum, translators exist for the top 5 most-used n8n SaaS nodes: Slack, Gmail, Google Sheets, Notion, Airtable.
3. Each SaaS translator maps n8n operations to HTTP API calls via the HTTP Request pattern or Lambda functions.
4. Authentication for each SaaS service is handled via `CredentialArtifact` and SSM parameters.
5. Operation-specific parameters (e.g., Slack channel, message text) are correctly mapped.
6. The Release Parser's node metadata (from `n8n-release-parser`) can be used to auto-generate translator skeletons.
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/saas/` (new directory)
- `n8n-to-sfn/src/n8n_to_sfn/translators/saas/__init__.py`
- `n8n-to-sfn/src/n8n_to_sfn/translators/saas/slack.py`
- `n8n-to-sfn/src/n8n_to_sfn/translators/saas/gmail.py`
- `n8n-to-sfn/src/n8n_to_sfn/translators/saas/google_sheets.py`
- `n8n-to-sfn/src/n8n_to_sfn/translators/saas/notion.py`
- `n8n-to-sfn/src/n8n_to_sfn/translators/saas/airtable.py`
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` (register translators)

### Technical Approach

1. **Base SaaS translator pattern:**
   - Each SaaS translator extends `BaseTranslator` and translates n8n operations to HTTP API calls.
   - Common pattern: Lambda function that wraps the SaaS API call with credential retrieval from SSM.
   - The Lambda reads the API key/OAuth token from SSM, makes the API call, and returns the result.

2. **Translator skeleton generator:**
   - Use `NodeTypeEntry` metadata from the Release Parser to auto-generate translator skeletons.
   - Each skeleton includes the node type, supported operations, and parameter mappings.

3. **Example: Slack translator:**
   - `n8n-nodes-base.slack` node type.
   - Operations: `message:post`, `message:update`, `channel:get`, `channel:getAll`, etc.
   - Maps to Slack Web API endpoints (e.g., `https://slack.com/api/chat.postMessage`).
   - Uses OAuth token from SSM parameter.

4. **PicoFun integration (future):**
   - When PicoFun infrastructure exists, SaaS translators can delegate to PicoFun API clients.
   - The `LambdaFunctionType.PICOFUN_API_CLIENT` enum value (from `inputs.py` line 22) is already defined for this purpose.

### Testing Requirements

- Test each SaaS translator with representative n8n node parameters.
- Test authentication credential extraction.
- Test operation mapping for each supported operation.
- Mock HTTP calls to verify correct API endpoints and payloads.
