# CLAUDE.md

See [README.md](README.md) for project overview and [docs/adr/README.md](docs/adr/README.md) for architecture decision records.

## Repo structure

```
phaeton/end-to-end/
├── n8n-release-parser/      # Versioned n8n node catalog and API spec matching
├── workflow-analyzer/       # Workflow analysis and conversion feasibility reports
├── n8n-to-sfn/              # Translation engine: n8n workflows → ASL + Lambda artifacts
├── packager/                # CDK application generator from translation output
├── shared/phaeton-models/   # Shared Pydantic models and cross-component adapters
├── deployment/              # CDK deployment stacks for the Phaeton pipeline
├── ai-agent/                # AI agent fallback for complex node translation (Strands + Bedrock)
└── tests/                   # Root-level cross-component integration tests
```

## Language & tooling

- **Python:** >=3.14 for all components
- **Package manager:** uv
- **Build systems:** uv_build (most components), Hatchling (n8n-release-parser, deployment)
- **Linting/formatting:** ruff
- **Type checking:** ty
- **Testing:** pytest + coverage

## Commands

All commands run per-component — `cd` into the component directory first, then:

```bash
uv sync                                              # install dependencies
uv run pytest                                        # run all tests
uv run pytest tests/unit                             # unit tests only
uv run ruff check --fix .                            # lint (with auto-fix)
uv run ruff format .                                 # format
uv run ty check                                      # type check
uv run coverage run -m pytest && uv run coverage report -m  # coverage
```

## Linting rules

Ruff is configured in the root `pyproject.toml` with a shared rule set. Each component inherits these rules. Key points:

- **Selected rules:** B, D, E, F, G, I, N, S, W, ANN, BLE, C4, C90, DTZ, ERA, PLW, PT, RET, RUF, SIM, TRY, UP
- **Ignored:** D203, D211, D213 (docstring style conflicts), E501 (line length), F403/F405 (wildcard imports)
- Docstrings required on all public modules, classes, and functions (D rules).
- Type annotations required on all parameters and return values (ANN rules).
- `per-file-ignores`: test files (`test_*`) suppress only `S101` (assert) and `S108` (hardcoded tmp paths). All other rules apply.

## Code conventions

- **Never change linting rules** (ruff config, per-file-ignores) to suppress warnings. Always fix the actual code.
- **Test files follow production conventions:** `-> None` return annotations, docstrings on classes and methods, type annotations on all parameters.
- All Pydantic models use `frozen=True` (immutable value objects).
- **No `py.typed` marker files.** Do not create `py.typed` files. This project uses `ty` for type checking, not mypy/pyright. Always use modern type annotations (PEP 604 unions `X | Y`, `list[...]`/`dict[...]` builtins, etc.) directly in code.
- **Python 3 exception syntax only.** Always use parenthesized tuples for multi-exception `except` clauses: `except (ExcA, ExcB):`. Never use the Python 2 comma syntax `except ExcA, ExcB:`.
- **No CDK alpha constructs.** Generated CDK code must use stable `aws_cdk.aws_lambda` constructs (`lambda_.Function`, `lambda_.LayerVersion`) with explicit `cdk.BundlingOptions`, never `aws_cdk.aws_lambda_python_alpha` (`PythonFunction`, `PythonLayerVersion`).

## Dependency rules

- **phaeton-models is a leaf dependency.** It must NEVER depend on any service packages (n8n-to-sfn, packager, workflow-analyzer, etc.), not even as dev dependencies. This causes circular dependency resolution failures in uv.
- Adapters in phaeton-models must define boundary models within `phaeton_models` submodules, not import from external service packages.

## Integration tests

Root-level `tests/` contains cross-component tests with these subdirectories and markers:

- `tests/integration/` — `@pytest.mark.integration` (require AWS credentials)
- `tests/performance/` — `@pytest.mark.performance` (large workflow scaling)
- `tests/e2e/` — end-to-end pipeline tests
- `tests/contract/` — cross-component contract tests
- `tests/cdk_synth/` — CDK synthesis validation tests
