# Shared Packager Input Parity

**Priority:** P0
**Effort:** M
**Gap Analysis Ref:** Item #2

## Overview

The shared `PackagerInput` boundary model at `shared/phaeton-models/src/phaeton_models/packager_input.py:196-217` has 6 fields, while the packager's local model at `packager/src/n8n_to_sfn_packager/models/inputs.py:346-389` has 9 fields. The missing fields are:

| Field | Shared model | Packager local model |
|-------|-------------|---------------------|
| `oauth_credentials` | absent | `list[OAuthCredentialSpec]` |
| `sub_workflows` | absent | `list[SubWorkflowReference]` |
| `vpc_config` | absent | `VpcConfig \| None` |

The adapter function at `deployment/functions/adapter/handler.py:92-96` produces `phaeton_models.packager_input.PackagerInput`, which structurally cannot carry VPC config, OAuth credentials, or sub-workflow references. The packager handler at `packager/src/n8n_to_sfn_packager/handler.py:48` validates against its local `PackagerInput`, so the missing fields default silently — **VPC networking, OAuth token rotation, and sub-workflow references are unreachable through the orchestration pipeline**.

These fields are actively used by packager writers: `oauth_credentials` drives SSM parameter generation and EventBridge-scheduled token rotation Lambdas; `vpc_config` generates security groups and attaches VPC config to Lambda functions; `sub_workflows` populates CDK context with cross-stack ARN placeholders.

## Dependencies

- **Blocked by:** TASK-0001 (TranslationOutput must be aligned first so credential artifacts flow correctly into the adapter)
- **Blocks:** TASK-0003 (frozen=True should be applied after model restructuring), TASK-0006 (webhook auth config needs shared model parity)

## Acceptance Criteria

1. The shared `phaeton_models.packager_input.PackagerInput` model includes `oauth_credentials`, `sub_workflows`, and `vpc_config` fields.
2. Supporting types (`VpcConfig`, `OAuthCredentialSpec`, `SubWorkflowReference`, `WebhookAuthConfig`) are defined in `phaeton_models` submodules.
3. The packager's local `PackagerInput` is eliminated; the packager imports from `phaeton_models` instead.
4. The adapter at `deployment/functions/adapter/handler.py` correctly populates all fields when constructing `PackagerInput`.
5. The translation engine (or adapter enrichment step) detects and produces OAuth, VPC, and sub-workflow artifacts.
6. Packager writers (`cdk_writer.py`, `ssm_writer.py`, etc.) work correctly with the shared model.
7. `uv run pytest` passes in `shared/phaeton-models/`, `packager/`, and `deployment/`.
8. `uv run ruff check` passes in all three components.

## Implementation Details

### Files to Modify

- `shared/phaeton-models/src/phaeton_models/packager_input.py` — extend with missing fields and types
- `packager/src/n8n_to_sfn_packager/models/inputs.py` — remove local `PackagerInput`, import from shared
- `packager/src/n8n_to_sfn_packager/handler.py` — update import path
- `packager/src/n8n_to_sfn_packager/writers/` — update imports if needed
- `deployment/functions/adapter/handler.py` — populate new fields in adapter
- `shared/phaeton-models/tests/` — add tests for new model fields
- `packager/tests/` — update tests for new import paths

### Technical Approach

1. **Move types to shared model:** Copy `VpcConfig`, `OAuthCredentialSpec`, `SubWorkflowReference`, and `WebhookAuthConfig` type definitions from `packager/src/n8n_to_sfn_packager/models/inputs.py` into appropriate `phaeton_models` submodules. These must be standalone definitions (no imports from packager internals) per the dependency rules.

2. **Extend shared `PackagerInput`:** Add the three missing fields to `phaeton_models.packager_input.PackagerInput`:
   ```python
   oauth_credentials: list[OAuthCredentialSpec] = []
   sub_workflows: list[SubWorkflowReference] = []
   vpc_config: VpcConfig | None = None
   ```

3. **Eliminate local `PackagerInput`:** Update the packager to import `PackagerInput` from `phaeton_models` instead of defining it locally. Remove the local model class. Ensure all packager writers and the handler use the shared import.

4. **Update the adapter:** In `deployment/functions/adapter/handler.py:92-96`, populate the new fields. The adapter may need an enrichment step that extracts OAuth credentials, VPC config, and sub-workflow references from the translator output or workflow metadata.

5. **Update the translation engine or adapter:** Extend the pipeline so that OAuth credential specs, VPC configuration, and sub-workflow references are detected and carried through. This may involve the engine emitting these artifacts or a post-translation enrichment step in the adapter.

### Testing Requirements

- `shared/phaeton-models/tests/test_packager_input.py` — test that new fields serialize/deserialize correctly, test default values, test Pydantic validation.
- `packager/tests/` — update existing tests to use the shared model import path. Verify all writers work with the shared model.
- `deployment/tests/` — test that the adapter produces a complete `PackagerInput` with all fields populated.
- Contract test: construct a `PackagerInput` with all fields, pass it through the packager handler, and verify no fields are silently dropped.
