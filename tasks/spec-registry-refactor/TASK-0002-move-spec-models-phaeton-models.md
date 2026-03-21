# Move Spec Models To Phaeton Models

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #2

## Overview

The spec-related Pydantic models (`ApiSpecEntry`, `ApiSpecIndex`, `SpecEndpoint`, `NodeApiMapping`) are currently defined in `n8n-release-parser/src/n8n_release_parser/models.py`. These models will be consumed by the new `spec-registry` component (TASK-0006) and potentially by the release-parser for reading index data. Leaving them in `n8n-release-parser` would force `spec-registry` to depend on the release-parser package, creating tight coupling between what should be independent services.

These are boundary contract types — they define the shape of the spec index JSON that is written to and read from S3. Moving them to `phaeton-models` avoids circular dependencies and keeps both services decoupled.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0006 (spec-registry imports spec models from phaeton-models), TASK-0007 (release-parser cleanup removes local spec models)

## Acceptance Criteria

1. `ApiSpecEntry`, `ApiSpecIndex`, `SpecEndpoint`, and `NodeApiMapping` exist in `phaeton_models.spec` as frozen Pydantic models.
2. All four models are re-exported from `phaeton_models.__init__`.
3. `n8n-release-parser` imports these models from `phaeton_models.spec` instead of defining them locally.
4. The local definitions are removed from `n8n-release-parser/src/n8n_release_parser/models.py`.
5. All imports in `spec_index.py`, `matcher.py`, and `cli.py` are updated.
6. `uv run pytest` passes in `shared/phaeton-models/`.
7. `uv run pytest` passes in `n8n-release-parser/`.
8. `uv run ruff check` passes in both packages.

## Implementation Details

### Files to Modify

- `shared/phaeton-models/src/phaeton_models/spec.py` (new)
- `shared/phaeton-models/src/phaeton_models/__init__.py`
- `n8n-release-parser/src/n8n_release_parser/models.py`
- `n8n-release-parser/src/n8n_release_parser/spec_index.py`
- `n8n-release-parser/src/n8n_release_parser/matcher.py`
- `n8n-release-parser/src/n8n_release_parser/cli.py`

### Technical Approach

1. Read `n8n-release-parser/src/n8n_release_parser/models.py` to identify the exact definitions of `ApiSpecEntry`, `ApiSpecIndex`, `SpecEndpoint`, and `NodeApiMapping`. Note their fields, validators, and any imports they require.

2. Create `shared/phaeton-models/src/phaeton_models/spec.py` with all four models. Ensure they use `frozen=True` (matching the project convention for Pydantic models). Preserve all field types, defaults, and validators exactly.

3. Add re-exports to `shared/phaeton-models/src/phaeton_models/__init__.py`.

4. In `n8n-release-parser/src/n8n_release_parser/models.py`, remove the four model class definitions. If other models in the file reference them (e.g., as field types), add an import from `phaeton_models.spec`.

5. Update imports in `spec_index.py` — this file likely uses `ApiSpecEntry`, `ApiSpecIndex`, and `SpecEndpoint` for building and saving the index. Change imports from `.models` to `phaeton_models.spec`.

6. Update imports in `matcher.py` — this file likely uses `NodeApiMapping` and `ApiSpecIndex`. Change imports similarly.

7. Update imports in `cli.py` — if it references any spec models directly, update those imports.

8. Check test files (`test_spec_index.py`, `test_matcher.py`) for direct imports of these models and update them.

### Testing Requirements

- Run existing `n8n-release-parser` tests — they should pass without modification since the models are identical.
- Verify `from phaeton_models.spec import ApiSpecEntry, ApiSpecIndex, SpecEndpoint, NodeApiMapping` works.
- Verify Pydantic serialization/deserialization round-trips for each model.
