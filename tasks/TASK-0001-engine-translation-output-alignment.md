# Engine Translation Output Alignment

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #1

## Overview

The translation engine defines a local `TranslationOutput` at `n8n-to-sfn/src/n8n_to_sfn/engine.py:53-60` that diverges from the canonical shared boundary model at `shared/phaeton-models/src/phaeton_models/translator_output.py:100-121` in two ways:

| Aspect | Engine (local) | Shared (boundary) |
|--------|---------------|-------------------|
| `state_machine` type | `StateMachine` (Pydantic model) | `dict[str, Any]` (serialized ASL) |
| `credential_artifacts` | **absent** | `list[CredentialArtifact]` |

JSON round-trip works for `state_machine` (Pydantic serializes to dict), but **credentials are silently dropped** because the engine never populates the field. Any credential-dependent workflow (OAuth, API keys, etc.) will pass through the adapter without credential metadata, causing the packager to generate SSM parameters with no corresponding credential specs.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0002 (shared PackagerInput parity requires correct TranslationOutput flowing through the adapter), TASK-0003 (frozen=True should be applied after model restructuring)

## Acceptance Criteria

1. The local `TranslationOutput` class in `engine.py` is removed.
2. The engine produces the shared `phaeton_models.translator_output.TranslationOutput` boundary model directly.
3. The `state_machine` field is serialized to `dict[str, Any]` by calling `sm.model_dump(by_alias=True)` at the handler boundary.
4. `CredentialArtifact` objects are collected during translation and populated in the `credential_artifacts` field.
5. The handler serialization via `model_dump(mode="json")` continues to work correctly.
6. Existing tests pass with the shared model substituted for the local model.
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/engine.py` — remove local `TranslationOutput`, import and use shared model
- `n8n-to-sfn/src/n8n_to_sfn/handler.py` — update handler to serialize `StateMachine` to dict at the boundary
- `n8n-to-sfn/tests/` — update tests that reference the local `TranslationOutput`

### Technical Approach

1. In `engine.py`, remove the local `TranslationOutput` class (lines 53-60).
2. Add import: `from phaeton_models.translator_output import TranslationOutput` (the shared boundary model).
3. In the engine's `translate()` method, collect `CredentialArtifact` objects during translation. When translators encounter credential-dependent nodes (OAuth, API key nodes), they should emit `CredentialArtifact` instances.
4. At the handler boundary (in `handler.py`), serialize the `StateMachine` Pydantic model to a dict using `sm.model_dump(by_alias=True)` before constructing the shared `TranslationOutput`.
5. Construct the shared `TranslationOutput` with all three components: serialized `state_machine` dict, `lambda_artifacts`, and `credential_artifacts`.
6. Verify `model_dump(mode="json")` still produces correct JSON for the API response.

### Testing Requirements

- Update unit tests in `n8n-to-sfn/tests/` that construct or assert on `TranslationOutput` to use the shared model.
- Add a test that verifies `credential_artifacts` are populated when translating a workflow with credential-dependent nodes.
- Add a test that verifies `state_machine` is a `dict[str, Any]` (not a Pydantic model) in the output.
- Verify round-trip serialization: construct → `model_dump(mode="json")` → deserialize → assert equality.
