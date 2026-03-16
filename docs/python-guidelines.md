# Python Project Guidelines

This document summarises the Python standards that apply to all Python projects.

## Tools

Use the following tools as appropriate:

* Python version: 3.14 - current latest and stable version
* AWS Infrastructure: `aws-cdk`
* Code formatting: `ruff`
* Linting: `ruff`
* Package management: `uv` - DO NOT USE `pip`. ALWAYS use `uv sync`, `uv run` etc
* Testing: `pytest`
* Test coverage reporting: `coverage` - DO NOT USE `pytest-cov`!
* Type checker: `ty`

## Specific use cases

These tools and libraries are only required if they're applicable to the use
case.

* CLI apps: `typer` DO NOT USE `click`
* HTTP client: `httpx` DO NOT USE `requests`
* Lambda function logging, tracing, event schemas: `aws-lambda-powertools`
* Models: `pydantic` (v2)
* Types for AWS boto3: `types-boto3`


## Configuration

### Dependencies

ALWAYS use exact version constraints. To ensure you're using the latest version
of a package, invoke `uv add --bounds exact <package-name>`. This will add the
dependency to `pyproject.toml`. Use the `--dev` flag for a dev dependency.

### Dev Dependencies

ALWAYS specify dev dependencies using a `[dependency-groups]`, like so:

[dependency-groups]
dev = [
...
]

NEVER use `[project.optional-dependencies]`.

### Linting

Use this configuration for `ruff` linting and formatting.

```toml
[tool.ruff.lint]
# Rules listed at https://github.com/charliermarsh/ruff#supported-rules
select = ["B", "D", "E", "F", "G", "I", "N", "S", "W", "ANN" ,"BLE", "C4", "C90", "DTZ", "ERA", "PLW", "PT", "RET", "RUF", "SIM", "TRY", "UP"]
ignore = ["D203", "D211", "D212", "E501", "F403", "F405"]

# Allow autofix for all enabled rules (when `--fix`) is provided.
fixable = ["B", "D", "E", "F", "G", "I", "N", "S", "W", "ANN" ,"BLE", "C4", "C90", "DTZ", "ERA", "PLW", "PT", "RET", "RUF", "SIM", "TRY", "UP"]
unfixable = []

[tool.ruff.lint.per-file-ignores]
"test_*" = ["S101", "S108"]
```
