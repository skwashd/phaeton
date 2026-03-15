# Fix Python Syntax Error Iam Writer

**Priority:** P0
**Effort:** XS
**Gap Analysis Ref:** Item #4

## Overview

`iam_writer.py` line 211 contains Python 2 exception syntax that causes a `SyntaxError` in Python 3, preventing the entire `iam_writer` module from being imported. Any code path that touches `IAMPolicyGenerator` will crash immediately. This affects all packager operations that generate IAM policies for SDK-integrated state machines.

The bug: `except ValueError, IndexError:` should be `except (ValueError, IndexError):`.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0009

## Acceptance Criteria

1. `iam_writer.py` line 211 uses correct Python 3 syntax: `except (ValueError, IndexError):`.
2. The `iam_writer` module can be imported without errors: `python -c "from n8n_to_sfn_packager.writers.iam_writer import IAMPolicyGenerator"` succeeds.
3. `uv run pytest` passes in `packager/`.
4. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/iam_writer.py`

### Technical Approach

1. Change line 211 from:
   ```python
   except ValueError, IndexError:
   ```
   to:
   ```python
   except (ValueError, IndexError):
   ```

2. This is a one-line fix. The `except` clause is inside the `_collect_sdk_actions` method (line 199) of the `IAMPolicyGenerator` class (line 33).

### Testing Requirements

- Existing tests should pass once the syntax error is fixed.
- Add a smoke test if none exists: import `IAMPolicyGenerator` and call `_collect_sdk_actions` with a resource string that triggers the except clause.
