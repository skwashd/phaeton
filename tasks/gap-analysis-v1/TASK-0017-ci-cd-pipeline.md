# Ci Cd Pipeline

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #17

## Overview

There are no GitHub Actions workflows and no automated quality gates beyond what individual component test suites provide. Each component uses `ruff` and `pytest` locally but there is no unified GitHub Actions pipeline that runs linting, type checking, and tests across all components on every push. CI/CD should be implemented using GitHub Actions with per-component workflows and a unified gate.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A `.github/workflows/` directory exists with CI workflow definitions.
2. Each component (`workflow-analyzer`, `n8n-to-sfn`, `packager`, `n8n-release-parser`) has quality gates that run on every push and pull request.
3. Quality gates include: `uv run ruff check`, `uv run ty check`, `uv run pytest` with coverage.
4. A unified workflow runs all component quality gates and fails if any component fails.
5. The pipeline uses `uv` for dependency management and test execution.
6. Python version matches `requires-python` from each component's `pyproject.toml` (>= 3.14).
7. Test results and coverage reports are uploaded as artifacts.
8. The pipeline completes in a reasonable time (< 10 minutes for unit tests).

## Implementation Details

### Files to Modify

- `.github/workflows/ci.yml` (new)
- `.github/workflows/component-test.yml` (new, reusable workflow)

### Technical Approach

1. **Reusable component workflow** (`.github/workflows/component-test.yml`):
   ```yaml
   on:
     workflow_call:
       inputs:
         component:
           required: true
           type: string
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v4
         - run: uv run ruff check
           working-directory: ${{ inputs.component }}
         - run: uv run ty check
           working-directory: ${{ inputs.component }}
         - run: uv run pytest --cov
           working-directory: ${{ inputs.component }}
   ```

2. **Unified CI workflow** (`.github/workflows/ci.yml`):
   - Triggers on push to `main` and all pull requests.
   - Calls the reusable workflow for each component.
   - All components must pass for the unified gate to succeed.

3. **Path-based triggers:**
   - Use `paths` filters to only run component tests when that component's files change.
   - Always run all tests on pushes to `main`.

4. **Coverage reporting:**
   - Use `pytest-cov` to generate coverage reports.
   - Upload as GitHub Actions artifacts.

### Testing Requirements

- Verify the workflow YAML syntax is valid (use `actionlint` if available).
- Test the workflow locally using `act` if possible.
- Ensure each component's `uv run pytest` passes independently before adding to CI.
