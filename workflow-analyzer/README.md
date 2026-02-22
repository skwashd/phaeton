# Workflow Analyzer

Analyzes n8n workflow JSON exports and produces conversion feasibility reports for AWS Step Functions migration. Classifies nodes, analyzes expressions, builds dependency graphs, and generates structured reports to guide automated and manual conversion.

## Installation

```bash
uv sync
```

## Usage

Analyze a workflow and generate reports:

```bash
uv run workflow-analyzer path/to/workflow.json -o output/
```

Options:

- `--output-dir`, `-o`: Directory to write reports (default: current directory)
- `--format`, `-f`: Report formats — `json`, `md`, or both (default: both)
- `--payload-limit`: Step Functions payload limit in KiB (default: 256)

## Development

Run tests:

```bash
uv run pytest
```

Run linting and formatting:

```bash
uv run ruff check --fix .
uv run ruff format .
```

Run type checking:

```bash
uv run ty check
```

Run test coverage:

```bash
uv run coverage run -m pytest
uv run coverage report -m
```
