# CLAUDE.md

See the [top-level CLAUDE.md](../CLAUDE.md) for repo-wide commands, linting rules, and conventions.

See [README.md](README.md) for project overview and architecture.

## Quick reference

- **Build system:** uv_build
- **Source layout:** `src/n8n_to_sfn/`
- **Lambda handler:** `n8n_to_sfn.handler:handler`
- **Dev CLI entry point:** `n8n_to_sfn.cli:app` (Typer — dev/testing only, not deployed)

## Component purpose

Translation engine that converts n8n workflows into AWS Step Functions ASL definitions and supporting Lambda artifacts. Accepts a `WorkflowAnalysis` payload and produces a `TranslationOutput` with state machine definitions, Lambda code, and a conversion report.

## Key modules

- `handler.py` — Lambda entry point. Validates `WorkflowAnalysis`, creates engine with all translators, returns `TranslationOutput`.
- `engine.py` — Core `TranslationEngine` orchestrator. Dispatches nodes to registered translators.
- `errors.py` — Translation error hierarchy.
- `items_adapter.py` — Adapts n8n item semantics to Step Functions data flow.
- `validator.py` — ASL schema validation.
- `ai_agent/` — AI agent integration for fallback translation:
  - `client.py` — `AIAgentClient` that invokes node-translator and expression-translator Lambdas.
  - `fallback.py` — Fallback logic when rule-based translators cannot handle a node.
- `models/` — Pydantic models (`asl.py`, `n8n.py`). All models use `frozen=True`.
- `translators/` — Node-type-specific translators:
  - `base.py` — Abstract base translator.
  - `flow_control.py`, `aws_service.py`, `http_request.py`, `code_node.py`, `database.py`, `set_node.py`, `triggers.py`, `picofun.py` — Rule-based translators.
  - `expressions.py`, `expression_evaluator.py`, `variables.py` — Expression handling.
  - `saas/` — SaaS-specific translators (Slack, Gmail, Google Sheets, Notion, Airtable).
- `cli.py` — Dev-only Typer CLI for local testing. Not bundled in Lambda deployments.

## Code conventions

- The Lambda handler (`handler.py`) is the primary interface for this component.
- The CLI (`cli.py`) is a dev/testing adapter only and is not included in Lambda deployments. Typer is a dev dependency.
- New node translators should extend the base translator in `translators/base.py` and be registered in `handler.py:create_default_engine()`.
- The AI agent client is optional — the engine falls back gracefully when `NODE_TRANSLATOR_FUNCTION_NAME` and `EXPRESSION_TRANSLATOR_FUNCTION_NAME` environment variables are not set.
