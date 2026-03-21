# Remove Spec Ownership From Release Parser

**Priority:** P0
**Effort:** M
**Gap Analysis Ref:** Item #7

## Overview

After the spec-registry component is created (TASK-0006) and spec models are in phaeton-models (TASK-0002), the `n8n-release-parser` should no longer own spec-related code. The release-parser becomes a pure catalog producer: fetch n8n releases, parse node metadata, diff versions, build catalogs.

This task removes `spec_index.py`, `matcher.py`, the `build-index` and `match` CLI commands, and any remaining spec model definitions from the release-parser. Associated tests are deleted (they've been moved to spec-registry in TASK-0006).

## Dependencies

- **Blocked by:** TASK-0002 (spec models moved to phaeton-models), TASK-0006 (spec-registry exists with the moved code)
- **Blocks:** TASK-0010 (ports-and-adapters refactor of release-parser builds on the cleaned codebase)

## Acceptance Criteria

1. `n8n-release-parser/src/n8n_release_parser/spec_index.py` no longer exists.
2. `n8n-release-parser/src/n8n_release_parser/matcher.py` no longer exists.
3. The `build-index` and `match` CLI commands are removed from `cli.py`.
4. No remaining imports of `spec_index` or `matcher` exist in the release-parser package.
5. `models.py` contains no spec-related model definitions (they're in phaeton-models).
6. `n8n-release-parser/tests/test_spec_index.py` no longer exists.
7. `n8n-release-parser/tests/test_matcher.py` no longer exists.
8. `uv run pytest` passes in `n8n-release-parser/`.
9. `uv run ruff check` passes in `n8n-release-parser/`.

## Implementation Details

### Files to Modify

- `n8n-release-parser/src/n8n_release_parser/spec_index.py` (delete)
- `n8n-release-parser/src/n8n_release_parser/matcher.py` (delete)
- `n8n-release-parser/src/n8n_release_parser/cli.py` (remove spec commands)
- `n8n-release-parser/src/n8n_release_parser/models.py` (remove any remaining spec model imports/re-exports)
- `n8n-release-parser/tests/test_spec_index.py` (delete)
- `n8n-release-parser/tests/test_matcher.py` (delete)

### Technical Approach

1. Delete `spec_index.py` and `matcher.py` source files.

2. In `cli.py`, remove the `build-index` and `match` Typer commands and any imports they require from `spec_index` or `matcher`. Remove imports of spec models if they were used as CLI parameter types.

3. In `models.py`, verify that `ApiSpecEntry`, `ApiSpecIndex`, `SpecEndpoint`, and `NodeApiMapping` definitions have been removed (done in TASK-0002). Remove any remaining re-exports or references to these classes.

4. Check `__init__.py` for any re-exports of spec-related symbols and remove them.

5. Delete test files `test_spec_index.py` and `test_matcher.py`.

6. Grep the entire `n8n-release-parser/` directory for any remaining references to `spec_index`, `matcher`, `ApiSpecEntry`, `ApiSpecIndex`, `SpecEndpoint`, `NodeApiMapping`, `build_spec_index`, `match_all_nodes` and clean up.

7. Check `pyproject.toml` for any dependencies that were only needed by spec code (e.g., if `pyyaml` was only used for spec parsing). Remove them if no longer needed.

### Testing Requirements

- Run the full `n8n-release-parser` test suite to confirm no breakage.
- Verify that remaining CLI commands (fetch, diff, build-catalog, etc.) still work.
- Confirm no import errors when importing the package.
