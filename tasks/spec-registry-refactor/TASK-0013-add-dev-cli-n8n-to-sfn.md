# Add Dev Cli To N8n To Sfn

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #13

## Overview

The translation engine (`n8n-to-sfn`) has no proper CLI — just a `__main__` block in `handler.py` that mixes concerns. A proper dev-only Typer CLI should exist for local testing: it reads a JSON file, validates it as a `WorkflowAnalysis`, calls `engine.translate()`, and writes the output.

The `__main__` block should be removed from `handler.py` to keep the handler a clean Lambda adapter.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0019 (Lambda code asset exclusions)

## Acceptance Criteria

1. `cli.py` exists with a Typer app providing a `translate` command.
2. The `translate` command reads a JSON file, validates as `WorkflowAnalysis`, calls the engine, and writes output.
3. The `__main__` block is removed from `handler.py`.
4. Typer is in the `dev` dependency group.
5. A `[project.scripts]` entry points to the CLI.
6. `uv run pytest` passes in `n8n-to-sfn/`.
7. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/cli.py` (new)
- `n8n-to-sfn/src/n8n_to_sfn/handler.py`
- `n8n-to-sfn/pyproject.toml`

### Technical Approach

1. **Create `cli.py`:**
   ```python
   """Dev-only CLI for the n8n-to-sfn translation engine."""
   import json
   from pathlib import Path
   import typer
   from n8n_to_sfn.engine import TranslationEngine
   # ... create engine, read input, translate, write output
   ```
   - `translate` command: accepts input JSON path and output path.
   - Validates input as `WorkflowAnalysis`.
   - Creates engine (with optional mock AI agent for local dev).
   - Writes `TranslationResult` JSON to output path.

2. **Remove `__main__` block** from `handler.py`. The handler should only contain the Lambda entry point.

3. **Update `pyproject.toml`:**
   - Add `typer` to `[dependency-groups] dev`.
   - Add `[project.scripts]` entry: `n8n-to-sfn = "n8n_to_sfn.cli:app"`.

### Testing Requirements

- Existing handler tests should still pass (no functional change to handler).
- Optionally add a CLI smoke test that invokes the Typer app with `--help`.
