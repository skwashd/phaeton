# CLAUDE.md

See the [top-level CLAUDE.md](../CLAUDE.md) for repo-wide commands, linting rules, and conventions.

See [README.md](README.md) for project overview and architecture.

## Quick reference

- **Build system:** uv_build
- **Source layout:** `src/workflow_analyzer/`
- **Lambda handler:** `workflow_analyzer.handler:handler`
- **Dev CLI entry point:** `workflow_analyzer.cli:app` (Typer — dev/testing only, not deployed)

## Component purpose

Analyzes n8n workflow JSON exports and produces conversion feasibility reports for AWS Step Functions migration. Classifies nodes, detects cross-node dependencies, evaluates expressions, and generates JSON/Markdown reports.

## Key modules

- `handler.py` — Lambda entry point. Accepts workflow JSON, runs analysis, returns `ConversionReport`.
- `analyzer.py` — Core `WorkflowAnalyzer` orchestrator.
- `classifier/` — Node classification: `node_classifier.py`, `payload_analyzer.py`, `registry.py`.
- `expressions/` — Expression classification: `expression_classifier.py`.
- `graph/` — Workflow graph analysis: `graph_builder.py`, `cross_node_detector.py`.
- `parser/` — Workflow parsing: `workflow_parser.py`, `accessors.py`.
- `report/` — Report generation: `report_generator.py`, `json_renderer.py`, `markdown_renderer.py`.
- `models/` — Pydantic models and exceptions. All models use `frozen=True`.
- `cli.py` — Dev-only Typer CLI for local testing. Not bundled in Lambda deployments.

## Code conventions

- The Lambda handler (`handler.py`) is the primary interface for this component.
- The CLI (`cli.py`) is a dev/testing adapter only and is not included in Lambda deployments. Typer is a dev dependency.
