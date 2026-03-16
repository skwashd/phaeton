# Lint Type Suppression Cleanup

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #10

## Overview

The codebase contains `# noqa:` and `# type: ignore` suppressions. Most are legitimate, but several should be fixed by addressing the underlying code issue rather than suppressing the warning.

### Fixable Suppressions

| File | Line | Suppression | Issue | Fix |
|------|------|-------------|-------|-----|
| `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py` | 252 | `# noqa: BLE001` | Blanket `except Exception` in AI agent fallback | Catch `(ConnectionError, TimeoutError, json.JSONDecodeError, ValueError)` |
| `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py` | 273 | `# noqa: BLE001` | Blanket `except Exception` in expression code builder | Catch `(ValueError, IndexError, KeyError)` |
| `deployment/stacks/orchestration_stack.py` | 28 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Type as `**kwargs: Any`, add `# noqa: ANN401` |
| `deployment/stacks/ai_agent_stack.py` | 14 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `deployment/stacks/translation_engine_stack.py` | 19 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `deployment/stacks/release_parser_stack.py` | 16 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `deployment/stacks/packager_stack.py` | 14 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `deployment/stacks/workflow_analyzer_stack.py` | 13 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `n8n-to-sfn/src/n8n_to_sfn/translators/expressions.py` | 230 | `# type: ignore[return-value]` | `_walk_and_translate` returns `JsonValue` but function declares `dict[str, JsonValue]` return | Use `cast()` or fix return type |
| `n8n-release-parser/src/n8n_release_parser/cache.py` | 55, 68 | `# noqa: TRY301` | Broad exception re-raise | Create new specific exceptions for the errors, catch them |
| `tests/integration/test_simple_workflow.py` | 129, 156, 164, 195 | `# type: ignore[attr-defined]` | boto3 Step Functions client methods untyped | Add `types-boto3` to root `pyproject.toml` dev dependencies |
| `tests/integration/conftest.py` | 215 | `# type: ignore[attr-defined]` | boto3 Step Functions client method untyped | Same fix — `types-boto3` provides PEP 484 stubs |

## Dependencies

- **Blocked by:** TASK-0004 (expression evaluator refactoring may change lines 252 and 273)
- **Blocks:** None

## Acceptance Criteria

1. All fixable suppressions listed above are resolved by fixing the underlying code.
2. No new `# noqa:` or `# type: ignore` suppressions are introduced.
3. The accepted suppressions listed in the gap analysis remain unchanged.
4. `uv run pytest` passes in all affected components.
5. `uv run ruff check` passes in all affected components.
6. `uv run ty check` passes in all affected components.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py`
- `n8n-to-sfn/src/n8n_to_sfn/translators/expressions.py`
- `deployment/stacks/orchestration_stack.py`
- `deployment/stacks/ai_agent_stack.py`
- `deployment/stacks/translation_engine_stack.py`
- `deployment/stacks/release_parser_stack.py`
- `deployment/stacks/packager_stack.py`
- `deployment/stacks/workflow_analyzer_stack.py`
- `n8n-release-parser/src/n8n_release_parser/cache.py`
- `tests/integration/test_simple_workflow.py`
- `tests/integration/conftest.py`
- `pyproject.toml` (root — add `types-boto3` dev dependency)

### Technical Approach

1. **BLE001 fixes (expression_evaluator.py):**
   - Line 252: Replace `except Exception` with `except (ConnectionError, TimeoutError, json.JSONDecodeError, ValueError)` and remove `# noqa: BLE001`.
   - Line 273: Replace `except Exception` with `except (ValueError, IndexError, KeyError)` and remove `# noqa: BLE001`.

2. **ANN003 fixes (deployment stacks):**
   - In each of the 6 stack files, change `**kwargs` to `**kwargs: Any` and replace `# noqa: ANN003` with `# noqa: ANN401`. Add `from typing import Any` if not present.

3. **Type ignore fix (expressions.py):**
   - Line 230: Either use `cast(dict[str, JsonValue], result)` or adjust the return type of the function to `JsonValue` if the function can legitimately return non-dict values.

4. **TRY301 fixes (cache.py):**
   - Lines 55, 68: Define specific exception classes (e.g., `CacheReadError`, `CacheWriteError`) in the cache module. Catch specific exceptions instead of using bare re-raises.

5. **boto3 type stubs:**
   - Add `types-boto3[stepfunctions]` to the root `pyproject.toml` dev dependencies. This provides PEP 484 stubs that resolve the `# type: ignore[attr-defined]` suppressions.
   - Remove the `# type: ignore[attr-defined]` comments from `tests/integration/test_simple_workflow.py` and `tests/integration/conftest.py`.

### Testing Requirements

- Run `uv run ruff check` in each affected component to verify no new violations.
- Run `uv run ty check` in each affected component to verify type ignore removals.
- Run `uv run pytest` in each affected component to verify no regressions.
