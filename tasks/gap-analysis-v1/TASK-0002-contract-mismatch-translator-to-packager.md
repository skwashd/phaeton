# Contract Mismatch Translator To Packager

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #2

## Overview

Component 3 (Translation Engine / n8n-to-sfn) outputs `TranslationResult` and `TranslationOutput` with uppercase enum values for `LambdaRuntime` (`PYTHON`, `NODEJS`) and `TriggerType` (`EVENTBRIDGE_SCHEDULE`, `LAMBDA_FURL`, `MANUAL`). Component 4 (Packager) expects lowercase/different enum values for `LambdaRuntime` (`python`, `nodejs`) and `TriggerType` (`schedule`, `webhook`, `manual`, `app_event`). No mapping layer exists between these enums, so the packager will reject or misinterpret every artifact from the translator.

## Dependencies

- **Blocked by:** TASK-0003 (shared `phaeton-models` package must exist first)
- **Blocks:** TASK-0007, TASK-0031, TASK-0032

## Acceptance Criteria

1. An adapter function or mapping exists that converts Translation Engine enum values to Packager enum values.
2. `LambdaRuntime.PYTHON` -> `LambdaRuntime("python")` and `LambdaRuntime.NODEJS` -> `LambdaRuntime("nodejs")`.
3. `TriggerType.EVENTBRIDGE_SCHEDULE` -> `TriggerType("schedule")`, `TriggerType.LAMBDA_FURL` -> `TriggerType("webhook")`, `TriggerType.MANUAL` -> `TriggerType("manual")`.
4. `TranslationResult` fields (`lambda_artifacts`, `trigger_artifacts`, `credential_artifacts`) are mapped into `PackagerInput` fields (`lambda_functions`, `triggers`, `credentials`).
5. The adapter handles the structural differences between `LambdaArtifact` (engine) and `LambdaFunctionSpec` (packager), and between `TriggerArtifact` (engine) and `TriggerSpec` (packager).
6. `uv run pytest` passes with tests covering every enum mapping.
7. `uv run ruff check` passes with no violations.

## Implementation Details

### Files to Modify

- `shared/phaeton-models/src/phaeton_models/adapters/translator_to_packager.py` (new)
- `shared/phaeton-models/tests/test_adapter_translator_to_packager.py` (new)

### Technical Approach

1. Create a mapping function `convert_output_to_packager_input(output: TranslationOutput, workflow_name: str) -> PackagerInput`:
   - Map `LambdaRuntime` by value: `{"PYTHON": "python", "NODEJS": "nodejs"}`.
   - Map `TriggerType` by value: `{"EVENTBRIDGE_SCHEDULE": "schedule", "LAMBDA_FURL": "webhook", "MANUAL": "manual"}`.
   - Convert each `LambdaArtifact` to a `LambdaFunctionSpec`, mapping `runtime` enum values.
   - Convert each `TriggerArtifact` to a `TriggerSpec`, mapping `trigger_type` enum values.
   - Convert each `CredentialArtifact` to a `CredentialSpec`.
   - Build `StateMachineDefinition` from `output.state_machine`.
   - Build `WorkflowMetadata` from the workflow name and conversion report.
   - Build `ConversionReport` (packager model) from `output.conversion_report`.

2. The adapter should live in `phaeton-models` (the shared package from TASK-0003) since it sits at the boundary between components. It imports `TranslationOutput` and related models from `n8n-to-sfn`, and `PackagerInput` and related models from `packager`. Both are already dependencies of `phaeton-models`' consumers, so the adapter avoids introducing new cross-component dependencies.

3. Engine enums are in `n8n_to_sfn/translators/base.py`:
   - `LambdaRuntime`: `PYTHON = "PYTHON"`, `NODEJS = "NODEJS"` (line 20)
   - `TriggerType`: `EVENTBRIDGE_SCHEDULE = "EVENTBRIDGE_SCHEDULE"`, `LAMBDA_FURL = "LAMBDA_FURL"`, `MANUAL = "MANUAL"` (line 37)

4. Packager enums are in `packager/src/n8n_to_sfn_packager/models/inputs.py`:
   - `LambdaRuntime`: `NODEJS = "nodejs"`, `PYTHON = "python"` (line 33)
   - `TriggerType`: `SCHEDULE = "schedule"`, `WEBHOOK = "webhook"`, `MANUAL = "manual"`, `APP_EVENT = "app_event"` (line 40)

### Testing Requirements

- `shared/phaeton-models/tests/test_adapter_translator_to_packager.py`
- Test each enum mapping individually.
- Test full `TranslationOutput` -> `PackagerInput` conversion with representative data.
- Test that unknown enum values raise a clear error.
- Verify Pydantic validation succeeds on the output `PackagerInput`.
