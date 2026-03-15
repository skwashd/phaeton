# ADR-002: Pydantic v2 for All Data Models

**Status:** Accepted
**Date:** 2025-06-01

## Context

With four independent components exchanging structured data, the pipeline needs a reliable way to validate data at component boundaries. Manually validating dictionaries is error-prone and makes contract violations hard to detect. The project also needs serialization to and from JSON for workflow definitions, analysis reports, and ASL output.

## Decision

Use Pydantic v2 `BaseModel` for all data models across the entire pipeline, including:

- **n8n workflow models** — canonical representation of n8n workflow JSON (`N8nWorkflow`, `N8nNode`).
- **Boundary contracts** — models defining the input and output of each component (`WorkflowAnalysis`, `TranslationOutput`, `PackagerInput`).
- **Internal models** — ASL state definitions, Lambda artifacts, trigger configurations, and credential specifications.
- **Enums** — `StrEnum` subclasses for classifications (`NodeClassification`, `LambdaRuntime`, `TriggerType`).

Pydantic v2-specific features used throughout:
- `model_config = ConfigDict(frozen=True)` for immutable value objects.
- `Field()` with constraints for validation rules.
- `field_validator` for custom validation logic.
- Native `| None` union syntax for optional fields.

## Consequences

### Positive
- Contract violations are caught at model construction time with clear error messages, rather than surfacing as runtime `KeyError` or `AttributeError` deep in the pipeline.
- JSON serialization and deserialization are handled automatically via `model_dump()` and `model_validate()`.
- Frozen models prevent accidental mutation of shared data structures passed between pipeline stages.
- Type checkers (mypy, pyright) can validate model field access statically.

### Negative
- All components depend on Pydantic v2, which is a significant runtime dependency.
- Pydantic v2 has breaking API changes from v1, so any upstream libraries still on v1 require careful version management.
- Boundary models occasionally diverge between components (e.g., `TriggerType` enums differ between the translation engine and packager), requiring adapter functions.

### Neutral
- The `phaeton-models` shared package centralizes boundary model definitions but must remain a leaf dependency with no imports from service packages.
- Adapter modules in `phaeton-models/adapters/` handle the mapping between component-specific enum values (e.g., `LAMBDA_FURL` → `WEBHOOK`).
