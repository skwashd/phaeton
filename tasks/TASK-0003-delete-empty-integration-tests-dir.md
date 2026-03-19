# Delete Empty Integration Tests Directory

**Priority:** P0
**Effort:** XS
**Gap Analysis Ref:** Item #3

## Overview

The directory `src/phaeton_integration_tests/` at the repo root contains only an `__init__.py` file. All real integration tests live in `tests/integration/`. This empty package is confusing — it suggests there should be integration test code here, when in fact it serves no purpose. It may also be referenced in the root `pyproject.toml` as a package, wasting build/install time.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The directory `src/phaeton_integration_tests/` no longer exists.
2. No references to `phaeton_integration_tests` exist in the root `pyproject.toml`.
3. No references to `phaeton_integration_tests` exist anywhere in the codebase.
4. `uv run ruff check` passes at the repo root.

## Implementation Details

### Files to Modify

- `src/phaeton_integration_tests/` (delete entire directory)
- `pyproject.toml` (check for and remove references)

### Technical Approach

1. Delete `src/phaeton_integration_tests/__init__.py` and the `src/phaeton_integration_tests/` directory.

2. Check the root `pyproject.toml` for any references to `phaeton_integration_tests` in `[tool.setuptools.packages]`, `[project]`, or similar sections. Remove them.

3. Check if the `src/` directory at the repo root is now empty. If so, delete it as well.

4. Grep the codebase for any remaining references to `phaeton_integration_tests` and remove them.

### Testing Requirements

- Verify `tests/integration/` still exists and is unaffected.
- Run `uv run pytest tests/` at the repo root to confirm no test collection issues.
